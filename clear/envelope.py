"""Intent envelope (design pattern P1: task-scoped, user-editable permissions).

At task start the user's request is compiled into an *intent envelope*: the
capability classes the request plausibly needs and the entities (people,
accounts, addresses, files) it names. The envelope is shown to the user, who
can widen or narrow it before the agent runs; at runtime, actions outside the
envelope are a risk feature (not an automatic block -- natural-language
intent is ambiguous, and automatic blocking is what makes purely
system-level defences lose utility).

The default compiler is deterministic and LLM-free (a verb lexicon plus
entity regexes) so that it cannot itself be prompt-injected and so that its
behaviour is fully reproducible. A deployment may substitute an LLM-based
compiler that sees ONLY the user prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# capability class -> trigger patterns (word-boundary regexes, lower-case)
CAPABILITY_LEXICON: dict[str, list[str]] = {
    "communicate": [r"send", r"e-?mail", r"mail", r"message", r"\bdm\b", r"tell", r"notify", r"reply",
                    r"respond", r"forward", r"inform", r"remind", r"contact", r"share", r"post",
                    r"write to", r"let \w+ know", r"invite", r"summary to", r"channel"],
    "financial": [r"pay", r"payment", r"transfer", r"send money", r"refund", r"transaction",
                  r"rent", r"bill", r"iban", r"money", r"subscription", r"standing order"],
    "calendar_write": [r"schedule", r"reschedule", r"event", r"meeting", r"appointment", r"calendar",
                       r"invite", r"participants?", r"cancel", r"move", r"book .* (time|slot)"],
    "file_write": [r"create (a |the )?(new )?file", r"file", r"document", r"write", r"append",
                   r"add (them|it|.*) to", r"save", r"list", r"\.docx", r"\.txt", r"\.xlsx"],
    "delete": [r"delete", r"remove", r"clean ?up", r"get rid of", r"cancel", r"erase"],
    "account": [r"password", r"update (my )?(user )?(info|information|details|address|profile)",
                r"change (my )?(address|name|password|street|city)", r"moved to", r"\baccount\b"],
    "reservation": [r"reserve", r"reservation", r"book", r"rent a car", r"car rental", r"hotel",
                    r"restaurant", r"table"],
    "workspace_admin": [r"invite", r"add .* (to|in) (the )?(channel|workspace|slack)", r"remove .* from",
                        r"join", r"onboard"],
    "web_fetch": [r"website", r"webpage", r"web page", r"url", r"link", r"https?://", r"www\.",
                  r"\.com\b", r"\.org\b", r"blog", r"site"],
}

# phrases by which the user explicitly delegates instruction-following to data
DELEGATION_PATTERNS = [
    r"do (all )?the (actions|tasks|things|steps) (specified|described|listed|mentioned|in)",
    r"follow the (instructions|steps|guidance)", r"do what (it|the \w+) says",
    r"complete (all )?the tasks?", r"(the )?todo", r"tasks? (in|from) (the|my) (email|file|message|channel)",
    r"as (described|specified|instructed) in", r"according to the (email|message|file|note)",
]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_URL = re.compile(r"https?://\S+|www\.[\w.-]+\S*|\b[\w-]+\.(?:com|org|net|io|de|ch)(?:/\S*)?")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_QUOTED = re.compile(r"'([^']{2,80})'|\"([^\"]{2,80})\"")
_FILE = re.compile(r"\b[\w-]+\.(?:docx|txt|xlsx|pdf|csv|md|pptx|json)\b")
_PROPER = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b")


@dataclass
class IntentEnvelope:
    prompt: str
    capabilities: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)
    delegated: bool = False
    rationale: dict[str, list[str]] = field(default_factory=dict)

    def allows(self, capability: str) -> bool:
        return capability == "read" or capability in self.capabilities

    # user edits from the interface ------------------------------------
    def grant(self, capability: str) -> None:
        self.capabilities.add(capability)
        self.rationale.setdefault(capability, []).append("granted by user")

    def revoke(self, capability: str) -> None:
        self.capabilities.discard(capability)

    def to_dict(self) -> dict:
        return {"capabilities": sorted(self.capabilities), "entities": sorted(self.entities),
                "delegated": self.delegated, "rationale": self.rationale}


def derive_envelope(prompt: str) -> IntentEnvelope:
    low = prompt.lower()
    env = IntentEnvelope(prompt=prompt)
    for cap, pats in CAPABILITY_LEXICON.items():
        hits = [p for p in pats if re.search(r"\b" + p if not p.startswith(("\\", ".")) else p, low)]
        if hits:
            env.capabilities.add(cap)
            env.rationale[cap] = hits
    env.delegated = any(re.search(p, low) for p in DELEGATION_PATTERNS)
    for rx in (_EMAIL, _URL, _IBAN, _FILE):
        env.entities.update(m.group(0) for m in rx.finditer(prompt))
    for m in _QUOTED.finditer(prompt):
        env.entities.add(m.group(1) or m.group(2))
    stop = {"Please", "Can", "Could", "What", "When", "Where", "Who", "How", "The", "I", "My", "Then",
            "Also", "Give", "Tell", "Send", "Make", "Do", "Find", "Get", "Create", "Perform", "If", "And"}
    env.entities.update(m.group(1) for m in _PROPER.finditer(prompt) if m.group(1) not in stop)
    return env
