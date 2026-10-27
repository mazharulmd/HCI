// CLEAR agent console: replays recorded agent runs and mediates their tool calls.
// All trace content is untrusted and is only ever inserted with textContent.
"use strict";

const params = new URLSearchParams(location.search);
const COND = ["clear", "clear_generic", "confirm_all", "confirm_all_evidence", "none"].includes(params.get("condition")) ? params.get("condition") : "clear";
// 2x2 factorial (selectivity x evidence): clear = selective+evidence, clear_generic = selective only,
// confirm_all_evidence = evidence only, confirm_all = neither; none = no mediation.
// clear_generic: CLEAR decides WHEN to ask, but the dialog shows no provenance / forcing (isolates selectivity)
const SELECTIVE = COND === "clear" || COND === "clear_generic";
const EVIDENCE = COND === "clear" || COND === "confirm_all_evidence";
const ASK_ALL = COND === "confirm_all" || COND === "confirm_all_evidence";
const PID = /^[A-Za-z0-9_-]{1,32}$/.test(params.get("pid") || "") ? params.get("pid") : "demo";
const STEP_DELAY = Number(params.get("delay") || 450);

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let DATA = null, CFG = null, order = [], pos = 0, scenario = null, caps = new Set();

const CAP_LABEL = {
  communicate: "send messages / e-mail / share", financial: "move money", calendar_write: "change calendar",
  file_write: "create or edit files", delete: "delete things", account: "change account settings",
  reservation: "make reservations", workspace_admin: "manage workspace members", web_fetch: "open web pages",
};
const ORIGIN_LABEL = {
  user: "from your request", trusted: "from a trusted record", external: "from external content",
  unattributed: "not found in any source", trivial: "",
};

function log(event) {
  const body = JSON.stringify({ pid: PID, condition: COND, scenario: scenario && scenario.id, t: Date.now(), ...event });
  fetch("/api/log", { method: "POST", headers: { "Content-Type": "application/json" }, body }).catch(() => {});
}

function hashPid(s) { let h = 7; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; }

async function init() {
  document.documentElement.dataset.theme = params.get("theme") || "";
  $("condition-badge").textContent = { clear: "Condition A", confirm_all: "Condition B", clear_generic: "Condition C", confirm_all_evidence: "Condition D", none: "Condition E" }[COND];
  DATA = await (await fetch("scenarios.json")).json();
  CFG = DATA.config;
  const n = DATA.scenarios.length;
  const off = hashPid(PID) % n;          // rotation for counterbalancing scenario order
  order = Array.from({ length: n }, (_, i) => (i + off) % n);
  $("start").addEventListener("click", run);
  $("next").addEventListener("click", () => { pos += 1; load(); });
  load();
}

function load() {
  if (pos >= order.length) return finish();
  scenario = DATA.scenarios[order[pos]];
  $("progress").textContent = `Task ${pos + 1} of ${order.length}`;
  $("prompt").textContent = scenario.prompt;
  $("steps").replaceChildren();
  $("audit").replaceChildren();
  $("done").hidden = true;
  $("start").disabled = false;
  caps = new Set(scenario.envelope.capabilities);
  renderEnvelope();
  log({ type: "scenario_start" });
}

function renderEnvelope() {
  const box = $("envelope");
  box.hidden = COND !== "clear";
  if (box.hidden) return;
  const wrap = $("caps");
  wrap.replaceChildren();
  for (const cap of Object.keys(CAP_LABEL)) {
    const b = el("button", "chip " + (caps.has(cap) ? "on" : "off"), CAP_LABEL[cap]);
    b.type = "button";
    b.setAttribute("aria-pressed", caps.has(cap));
    b.addEventListener("click", () => {
      if (!$("start").disabled) {
        caps.has(cap) ? caps.delete(cap) : caps.add(cap);
        log({ type: "envelope_edit", capability: cap, allowed: caps.has(cap) });
        renderEnvelope();
      }
    });
    wrap.append(b);
  }
  const ents = $("entities");
  ents.replaceChildren(...scenario.envelope.entities.slice(0, 14).map((e) => el("span", "chip", e)));
  $("delegation").hidden = !scenario.envelope.delegated;
}

// Re-score a call client-side so that envelope edits take effect (same model as clear/risk.py).
function rescore(step) {
  const f = step.features || {};
  if (!step.side_effecting && !f.s) return { tier: "ALLOW", risk: 0, reasons: [] };
  let delta = 0;
  if (step.side_effecting && step.capability !== "read" && !caps.has(step.capability)) {
    delta = scenario.envelope.delegated ? CFG.risk.deviation_delegated : 1;
  }
  const w = CFG.risk;
  const x = { tau: f.tau || 0, kappa: f.kappa || 0, delta, iota: f.iota || 0 };
  const p = 1 - (1 - w.w_taint * x.tau) * (1 - w.w_exfil * x.kappa) * (1 - w.w_deviation * x.delta) * (1 - w.w_injection * x.iota);
  const risk = step.sensitivity * p;
  const t = CFG.tiers;
  let tier = "ALLOW";
  if (risk >= t.force) tier = "FORCE";
  else if (risk >= t.confirm) tier = "CONFIRM";
  else if (risk >= t.notify) tier = (t.promote_irreversible_notify && !step.reversible) ? "CONFIRM" : "NOTIFY";
  let reasons = step.reasons.filter((r) => !r.startsWith("Action type") && !r.startsWith("This action cannot be undone"));
  if (delta > 0) reasons = [`Action type '${CAP_LABEL[step.capability] || step.capability}' is outside what your request asked for`, ...reasons];
  if (tier === "CONFIRM" && risk < t.confirm) reasons.push("This action cannot be undone, so it needs your confirmation");
  return { tier, risk, reasons };
}

async function run() {
  $("start").disabled = true;
  log({ type: "agent_start", envelope: [...caps] });
  const executed = {};
  for (const step of scenario.steps) {
    await sleep(STEP_DELAY);
    if (step.type === "call") {
      const sc = (SELECTIVE || EVIDENCE) ? rescore(step) : { tier: step.side_effecting ? "CONFIRM" : "ALLOW", risk: 0, reasons: [] };
      const ask = (SELECTIVE && (sc.tier === "CONFIRM" || sc.tier === "FORCE")) ||
                  (ASK_ALL && step.side_effecting);
      let ok = true;
      if (ask) {
        const res = await askUser(step, sc);
        ok = res.approve;
        log({ type: "decision", call_idx: step.idx, function: step.function, tier: sc.tier, risk: sc.risk, ...res });
      } else if (SELECTIVE && sc.tier === "NOTIFY") {
        notify(step);
      }
      executed[step.idx] = ok;
      renderCall(step, sc.tier, ok);
    } else if (step.type === "result") {
      renderResult(step, executed[step.idx] !== false);
    } else if (step.type === "final") {
      const li = el("li", "step final");
      li.append(el("strong", "", "Agent: "), document.createTextNode(step.text || "(no answer)"));
      $("steps").append(li);
    }
  }
  log({ type: "scenario_end" });
  $("done").hidden = false;
}

function humanize(step) {
  const a = step.args || {};
  const v = (k) => (a[k] === undefined ? "" : Array.isArray(a[k]) ? a[k].join(", ") : String(a[k]));
  switch (step.function) {
    case "send_money": return `Send ${v("amount")} to account ${v("recipient")}`;
    case "schedule_transaction": return `Schedule a payment of ${v("amount")} to ${v("recipient")}`;
    case "update_scheduled_transaction": return `Change scheduled payment #${v("id")}`;
    case "send_email": return `E-mail ${v("recipients")}: "${v("subject")}"`;
    case "send_direct_message": return `Message ${v("recipient")}`;
    case "send_channel_message": return `Post in channel ${v("channel")}`;
    case "post_webpage": return `Publish content to ${v("url")}`;
    case "share_file": return `Share file ${v("file_id")} with ${v("email")}`;
    case "delete_file": return `Delete file ${v("file_id")}`;
    case "delete_email": return `Delete e-mail ${v("email_id")}`;
    case "update_password": return "Change your password";
    case "create_calendar_event": return `Create event "${v("title")}"${v("participants") ? " with " + v("participants") : ""}`;
    default: return step.function.replace(/_/g, " ");
  }
}

function argsTable(step, withProv) {
  const t = el("table", "args");
  for (const [k, val] of Object.entries(step.args || {})) {
    if (val === null || val === undefined || (Array.isArray(val) && !val.length)) continue;
    const tr = el("tr");
    tr.append(el("td", "", k));
    const td = el("td");
    td.append(document.createTextNode(Array.isArray(val) ? val.join(", ") : String(val)));
    if (withProv) {
      for (const p of step.provenance[k] || []) {
        if (p.origin === "trivial") continue;
        const div = el("div");
        const tag = el("span", "prov " + p.origin, ORIGIN_LABEL[p.origin]);
        tag.title = p.sources.join("; ");
        div.append(tag);
        if (p.sources.length) div.append(el("span", "snippet", " " + p.sources[0]));
        td.append(div);
        if (p.origin === "external" && p.snippet) td.append(excerpt(p.snippet, String(p.value)));
      }
    }
    tr.append(td);
    t.append(tr);
  }
  return t;
}

// Source-to-action excerpt: the passage of the source in which the value appears, value highlighted.
function excerpt(snippet, value) {
  const box = el("div", "excerpt");
  const lo = snippet.toLowerCase(), v = value.toLowerCase();
  const i = v ? lo.indexOf(v) : -1;
  box.append(document.createTextNode("\u201c"));
  if (i < 0) box.append(document.createTextNode(snippet));
  else box.append(document.createTextNode(snippet.slice(0, i)), el("mark", "inj", snippet.slice(i, i + v.length)),
                  document.createTextNode(snippet.slice(i + v.length)));
  box.append(document.createTextNode("\u201d"));
  return box;
}

// Consequence preview: state change computed by executing the call on a copy of the environment.
function previewBox(step) {
  const box = el("div", "preview");
  box.append(el("h3", "", "What will change"));
  const ul = el("ul", "reasons");
  for (const line of step.preview || []) ul.append(el("li", "", line));
  if (!(step.preview || []).length) ul.append(el("li", "", "(no preview available)"));
  box.append(ul, el("p", "note", step.reversible ? "You can undo this later." : "This cannot be undone."));
  return box;
}

function forcingTarget(step) {
  for (const [k, list] of Object.entries(step.provenance || {})) {
    for (const p of list) if (p.origin === "external" || p.origin === "unattributed") return { arg: k, ...p };
  }
  return null;
}

function askUser(step, sc0) {
  let sc = sc0;
  return new Promise((resolve) => {
    const dlg = $("dlg"), body = $("dlg-body"), approve = $("btn-approve");
    body.replaceChildren();
    const t0 = performance.now();
    let forced = null;
    if (!EVIDENCE) {
      body.className = "dlg generic";
      const head = el("div", "dlg-head");
      head.append(el("h3", "", "Allow this action?"));
      body.append(head, el("p", "summary", `The agent wants to run ${step.function}.`), argsTable(step, false));
      approve.disabled = false;
    } else {
      const dtier = sc.tier === "FORCE" ? "FORCE" : "CONFIRM";   // evidence dialogs: confirm or force style
      sc = { ...sc, tier: dtier };
      body.className = "dlg " + sc.tier;
      const head = el("div", "dlg-head");
      head.append(el("span", "tier " + sc.tier, sc.tier === "FORCE" ? "high risk" : "review"),
                  el("h3", "", sc.tier === "FORCE" ? "Check where this action came from" : "Please review this action"));
      head.querySelector("h3").id = "dlg-title";
      const meter = el("div", "meter"); const bar = el("span");
      bar.style.width = `${Math.round(100 * Math.min(1, sc.risk))}%`;
      bar.style.background = `var(--${sc.tier.toLowerCase()})`;
      meter.append(bar);
      body.append(head, el("p", "summary", humanize(step)), meter, argsTable(step, true), previewBox(step));
      if (sc.reasons.length) {
        body.append(el("h3", "", "Why you are asked"));
        const ul = el("ul", "reasons");
        for (const r of sc.reasons) ul.append(el("li", "", r));
        body.append(ul);
      }
      const target = sc.tier === "FORCE" ? forcingTarget(step) : null;
      approve.disabled = !!target;
      if (target) {
        const box = el("fieldset", "forcing");
        box.append(el("legend", "", `Before approving: where did '${target.value}' come from?`));
        const correct = target.origin === "external" ? "external" : "none";
        const opts = [["user", "I typed it in my request"], ["trusted", "My own account / a trusted record"],
                      ["external", `External content (${target.sources[0] || "a document or message"})`],
                      ["none", "It does not appear anywhere I can see"]];
        for (const [v, label] of opts) {
          const lab = el("label"); const r = el("input"); r.type = "radio"; r.name = "origin"; r.value = v;
          r.addEventListener("change", () => {
            forced = { answer: v, correct: v === correct };
            fb.textContent = forced.correct ? "" : `Not quite: it came ${ORIGIN_LABEL[target.origin]}${target.sources[0] ? " (" + target.sources[0] + ")" : ""}.`;
            approve.disabled = false;
          });
          lab.append(r, document.createTextNode(" " + label));
          box.append(lab);
        }
        const fb = el("div", "feedback");
        box.append(fb);
        body.append(box);
      }
    }
    const onClose = () => {
      dlg.removeEventListener("close", onClose);
      resolve({ approve: dlg.returnValue === "approve", rt_ms: Math.round(performance.now() - t0),
                forced_answer: forced && forced.answer, forced_correct: forced && forced.correct });
    };
    dlg.addEventListener("close", onClose);
    dlg.addEventListener("cancel", (e) => e.preventDefault(), { once: true });
    dlg.returnValue = "";
    dlg.showModal();
  });
}

function notify(step) {
  const t = $("toast");
  t.replaceChildren(document.createTextNode(`Done with notice: ${humanize(step)}`));
  const undo = el("button", "", "Undo");
  undo.addEventListener("click", () => { log({ type: "undo", call_idx: step.idx }); t.hidden = true; });
  t.append(undo);
  t.hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => { t.hidden = true; }, 4000);
}

function renderCall(step, tier, ok) {
  const li = el("li", "step call" + (ok ? "" : " blocked"));
  const head = el("div", "head");
  const code = el("code", "", `${step.function}(${Object.entries(step.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})`);
  head.append(code);
  if (SELECTIVE) head.append(el("span", "tier " + tier, tier.toLowerCase()));
  li.append(head);
  if (!ok) li.append(el("div", "note", "Denied by you - not executed."));
  $("steps").append(li);
  const a = el("li");
  a.append(el("span", "tier " + (SELECTIVE ? tier : (step.side_effecting ? "CONFIRM" : "ALLOW")), ok ? "run" : "denied"),
           document.createTextNode(" " + step.function));
  $("audit").append(a);
}

function highlighted(text, spans) {
  const frag = document.createDocumentFragment();
  const ss = [...spans].sort((a, b) => a.start - b.start);
  let at = 0;
  for (const s of ss) {
    if (s.start < at) continue;
    frag.append(document.createTextNode(text.slice(at, s.start)));
    const m = el("mark", "inj", text.slice(s.start, s.end)); m.title = s.label;
    frag.append(m);
    at = s.end;
  }
  frag.append(document.createTextNode(text.slice(at)));
  return frag;
}

function renderResult(step, ok) {
  const li = el("li", "step result");
  const head = el("div", "head");
  head.append(el("span", "", ok ? `Result of ${step.function}` : `${step.function} was not executed`));
  if (COND === "clear") head.append(el("span", "src-tag " + step.trust, step.trust === "untrusted" ? "external content" : "trusted"));
  li.append(head);
  if (ok) {
    const pre = el("pre");
    const flag = COND === "clear" && step.trust === "untrusted" && step.injection_score >= CFG.injection_signal.threshold_source_flag;
    pre.append(flag ? highlighted(step.text, step.spans) : document.createTextNode(step.text));
    li.append(pre);
    if (flag) li.append(el("div", "inj-banner", "This content contains text addressed to your AI agent. The agent should not take orders from it."));
  }
  $("steps").append(li);
}

function finish() {
  $("progress").textContent = "All tasks completed";
  $("prompt").textContent = "Thank you. Please continue with the questionnaire.";
  $("envelope").hidden = true;
  $("start").hidden = true;
  $("steps").replaceChildren();
  const a = el("a", "", "Open questionnaire");
  a.href = `questionnaire.html?pid=${encodeURIComponent(PID)}&condition=${encodeURIComponent(COND)}`;
  $("steps").append(a);
  log({ type: "session_end" });
}

init();
