"""Loading AgentDojo agent traces and replaying them in the AgentDojo environment.

The AgentDojo repository (Debenedetti et al., NeurIPS 2024 D&B) publishes the
full message traces of real LLM agents (GPT-4o, Claude, Gemini, Llama,
Command-R, Meta-SecAlign, ...) attacked with several prompt-injection
strategies and protected by several published defences. We use these traces
as *genuine agent behaviour* and replay them through CLEAR and baseline
mediators. Ground-truth utility and security are recomputed by executing the
(possibly filtered) tool calls in AgentDojo's own environments and calling the
benchmark's own utility/security predicates.
"""
from __future__ import annotations

import copy
import functools
import glob
import json
import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

warnings.filterwarnings("ignore")

AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
DEFAULT_RUNS = os.environ.get("AGENTDOJO_RUNS", str(Path(__file__).resolve().parent.parent / "external" / "agentdojo" / "runs"))


def _text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(c.get("content") or "") if isinstance(c, dict) else str(c) for c in content)
    return str(content)


@dataclass
class Call:
    idx: int                    # position in the episode's tool-call sequence
    function: str
    args: dict
    id: str | None = None


@dataclass
class Episode:
    model: str
    suite: str
    user_task: str
    injection_task: str | None
    attack: str                 # "none" for benign runs
    injections: dict
    messages: list[dict]
    utility: bool | None
    security: bool | None
    path: str

    @property
    def key(self) -> str:
        return f"{self.model}|{self.suite}|{self.user_task}|{self.attack}|{self.injection_task}"

    @property
    def attacked(self) -> bool:
        return self.attack != "none" and self.injection_task is not None

    @property
    def system_prompt(self) -> str:
        return next((_text(m["content"]) for m in self.messages if m["role"] == "system"), "")

    @property
    def user_prompt(self) -> str:
        return next((_text(m["content"]) for m in self.messages if m["role"] == "user"), "")

    def calls(self) -> list[Call]:
        out = []
        for m in self.messages:
            if m["role"] == "assistant":
                for tc in m.get("tool_calls") or []:
                    out.append(Call(len(out), tc["function"], dict(tc.get("args") or {}), tc.get("id")))
        return out

    def events(self) -> Iterator[tuple[str, Any]]:
        """Yield ("call", Call) and ("result", (Call, text)) in trace order."""
        idx = 0
        pending: dict[str, Call] = {}
        order: list[Call] = []
        for m in self.messages:
            if m["role"] == "assistant":
                for tc in m.get("tool_calls") or []:
                    c = Call(idx, tc["function"], dict(tc.get("args") or {}), tc.get("id"))
                    idx += 1
                    pending[c.id or str(c.idx)] = c
                    order.append(c)
                    yield "call", c
            elif m["role"] == "tool":
                tcid = m.get("tool_call_id")
                c = pending.get(tcid) if tcid else None
                if c is None:
                    c = order.pop(0) if order else Call(-1, (m.get("tool_call") or {}).get("function", "?"), {})
                elif c in order:
                    order.remove(c)
                text = _text(m.get("content"))
                if m.get("error"):
                    text = f"{text}\n{m['error']}"
                yield "result", (c, text)

    def final_output(self) -> list[dict]:
        if not self.messages or self.messages[-1]["role"] != "assistant":
            return []
        c = self.messages[-1]["content"]
        if c is None:
            return []
        if isinstance(c, str):
            return [{"type": "text", "content": c}]
        return c


def iter_episodes(runs_dir: str, model: str, attacks: set[str] | None = None) -> Iterator[Episode]:
    for f in sorted(glob.glob(os.path.join(runs_dir, model, "*", "*", "*", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        attack = d.get("attack_type") or "none"
        if attacks is not None and attack not in attacks:
            continue
        if not str(d.get("user_task_id", "")).startswith("user_task"):
            continue   # AgentDojo also runs injection tasks as user tasks; not used here
        yield Episode(model=model, suite=d["suite_name"], user_task=d["user_task_id"],
                      injection_task=d.get("injection_task_id"), attack=attack,
                      injections=d.get("injections") or {}, messages=d["messages"],
                      utility=d.get("utility"), security=d.get("security"), path=f)


def list_models(runs_dir: str) -> list[str]:
    return sorted(p.name for p in Path(runs_dir).iterdir() if p.is_dir())


# --------------------------------------------------------------------------- replay
@functools.lru_cache(maxsize=None)
def _suite(version: str, name: str):
    from agentdojo.task_suite.load_suites import get_suite
    return get_suite(version, name)


@functools.lru_cache(maxsize=4096)
def _base_env(version: str, suite: str, injections_json: str):
    s = _suite(version, suite)
    return s.load_and_inject_default_environment(json.loads(injections_json))


class Replayer:
    """Executes (a filtered subset of) an episode's tool calls in AgentDojo."""

    def __init__(self, version: str) -> None:
        self.version = version
        self._cache: dict[tuple, tuple[bool, bool | None]] = {}

    def tasks(self, ep: Episode):
        s = _suite(self.version, ep.suite)
        ut = s.get_user_task_by_id(ep.user_task)
        it = s.get_injection_task_by_id(ep.injection_task) if ep.attacked else None
        return s, ut, it

    def run(self, ep: Episode, drop: frozenset[int] = frozenset(), truncate_at: int | None = None,
            empty_output: bool = False) -> tuple[bool, bool | None]:
        """Return (utility, security) after executing all calls except ``drop``.

        ``truncate_at``: stop executing at this call index (agent aborted).
        """
        key = (ep.key, drop, truncate_at, empty_output)
        if key in self._cache:
            return self._cache[key]
        from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
        s, ut, it = self.tasks(ep)
        env = _base_env(self.version, ep.suite, json.dumps(ep.injections, sort_keys=True)).model_copy(deep=True)
        env = ut.init_environment(env)
        pre = env.model_copy(deep=True)
        rt = FunctionsRuntime(s.tools)
        trace = []
        for c in ep.calls():
            if truncate_at is not None and c.idx >= truncate_at:
                break
            if c.idx in drop:
                continue
            rt.run_function(env, c.function, c.args)
            trace.append(FunctionCall(function=c.function, args=c.args, id=c.id))
        out = [] if empty_output else ep.final_output()
        utility = bool(s._check_task_result(ut, out, pre, env, trace))
        security = None
        if it is not None:
            security = bool(s._check_task_result(it, out, pre, env, trace))
        self._cache[key] = (utility, security)
        return utility, security

    def injection_ground_truth(self, ep: Episode) -> list:
        s, ut, it = self.tasks(ep)
        env = _base_env(self.version, ep.suite, json.dumps(ep.injections, sort_keys=True)).model_copy(deep=True)
        env = ut.init_environment(env)
        try:
            return it.ground_truth(env)
        except Exception:
            return []

    def user_ground_truth(self, ep: Episode) -> list:
        s, ut, it = self.tasks(ep)
        env = _base_env(self.version, ep.suite, json.dumps({}, sort_keys=True)).model_copy(deep=True)
        env = ut.init_environment(env)
        try:
            return ut.ground_truth(env)
        except Exception:
            return []
