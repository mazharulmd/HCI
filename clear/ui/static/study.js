// Shared helpers for the study pages (start, consent, demographics, debrief).
"use strict";
const STUDY = (() => {
  const params = new URLSearchParams(location.search);
  const pidRaw = params.get("pid") || "";
  const pid = /^[A-Za-z0-9_-]{1,32}$/.test(pidRaw) ? pidRaw : null;
  const cfg = window.STUDY_CONFIG || {};
  async function post(path, payload) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                   body: JSON.stringify({ pid, t: Date.now(), ...payload }) });
    if (!r.ok) throw new Error(`server answered ${r.status}`);
    return r.json();
  }
  function log(payload) { return post("/api/log", payload); }
  // Fill <span data-cfg="key"> elements from study_config.js.
  function fillConfig(root = document) {
    for (const n of root.querySelectorAll("[data-cfg]")) n.textContent = String(cfg[n.dataset.cfg] ?? "");
    for (const n of root.querySelectorAll("[data-pid]")) n.textContent = pid || "";
  }
  function placeholders() {
    return Object.entries(cfg).filter(([, v]) => typeof v === "string" && v.includes("[")).map(([k]) => k);
  }
  function fail(msg) {
    const m = document.getElementById("msg");
    if (m) m.textContent = msg;
  }
  return { params, pid, cfg, post, log, fillConfig, placeholders, fail };
})();
