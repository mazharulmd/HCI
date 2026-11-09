"""Interactive review UI and API for the local prototype."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .core import as_public_dict, make_decision, risk_assessment
from .scenarios import SCENARIOS, get_scenario

app = FastAPI(title="Trust Boundary Lab", version="0.1.0")

class Review(BaseModel):
    scenario_id: str
    choice: str

@app.get("/api/scenarios")
def scenarios():
    return [as_public_dict(s) for s in SCENARIOS]

@app.get("/api/scenarios/{scenario_id}")
def scenario(scenario_id: str):
    try:
        s = get_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(404, "Unknown scenario") from exc
    return {**as_public_dict(s), "risk": risk_assessment(s)}

@app.post("/api/review")
def review(body: Review):
    if body.choice not in {"approve", "reject"}:
        raise HTTPException(400, "choice must be approve or reject")
    try:
        s = get_scenario(body.scenario_id)
    except KeyError as exc:
        raise HTTPException(404, "Unknown scenario") from exc
    return make_decision(s, "combined", body.choice)

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trust Boundary Lab</title><style>
*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#f3f6fa;color:#172235}header{background:#102a43;color:white;padding:1rem max(calc((100vw - 1100px)/2),1rem)}main{max-width:1100px;margin:1.5rem auto;padding:0 1rem;display:grid;grid-template-columns:280px 1fr;gap:1rem}.panel{background:white;border:1px solid #d6e0ea;border-radius:10px;padding:1rem}.row{padding:.7rem;border-bottom:1px solid #e5ebf0;cursor:pointer}.row:hover,.row.active{background:#eaf3ff}.badge{display:inline-block;padding:.2rem .6rem;border-radius:1rem;font-weight:700}.high{background:#ffe0df;color:#9b2424}.moderate{background:#fff0c2;color:#725400}.low{background:#dcf5e6;color:#17663b}.label{font-size:.8rem;text-transform:uppercase;color:#526579;letter-spacing:.04em}.excerpt{background:#f6f8fb;padding:1rem;border-left:4px solid #db8b32;overflow-wrap:anywhere}.actions{display:flex;gap:.7rem}button{border:0;border-radius:6px;padding:.7rem 1rem;font-weight:700;cursor:pointer}.approve{background:#17663b;color:white}.reject{background:#9b2424;color:white}#result{margin-top:1rem;font-weight:700} @media(max-width:700px){main{grid-template-columns:1fr}}</style></head><body><header><h1>Trust Boundary Lab</h1><p>Review what the agent wants to do before a simulated tool call runs.</p></header><main><nav class="panel" id="list" aria-label="Scenarios">Loading…</nav><section class="panel" id="detail"><h2>Choose a scenario</h2></section></main><script>
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let current=null;async function load(){let xs=await(await fetch('/api/scenarios')).json();document.querySelector('#list').innerHTML='<h2>Scenarios</h2>'+xs.map(x=>`<div class="row" data-id="${esc(x.id)}">${esc(x.title)}${x.attack?' <b>• attack</b>':''}</div>`).join('');document.querySelectorAll('.row').forEach(x=>x.onclick=()=>show(x.dataset.id))}async function show(id){current=await(await fetch('/api/scenarios/'+encodeURIComponent(id)).json());document.querySelectorAll('.row').forEach(x=>x.classList.toggle('active',x.dataset.id===id));let s=current,r=s.risk;document.querySelector('#detail').innerHTML=`<h2>${esc(s.title)}</h2><p><span class="label">User request</span><br>${esc(s.user_request)}</p><p><span class="label">Source</span><br>${esc(s.source)} · ${esc(s.source_trust)}</p><div class="excerpt"><span class="label">Source content</span><br>${esc(s.source_excerpt)}</div><p><span class="label">Proposed tool call</span><br><b>${esc(s.tool)}</b> — ${esc(s.action)}</p><p><span class="label">Permission</span> ${esc(s.permission)}</p><h3>Risk assessment <span class="badge ${esc(r.level)}">${esc(r.level)} · ${r.score}/100</span></h3><ul>${r.reasons.map(x=>`<li>${esc(x)}</li>`).join('')||'<li>No elevated risk indicators found.</li>'}</ul><p><b>Pattern:</b> show source provenance, request scope, risk reasons, then require an explicit choice.</p><div class="actions"><button class="approve" onclick="decide('approve')">Approve simulated call</button><button class="reject" onclick="decide('reject')">Reject call</button></div><div id="result" role="status" aria-live="polite"></div>`}async function decide(choice){let r=await(await fetch('/api/review',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({scenario_id:current.id,choice})})).json();document.querySelector('#result').textContent=`${r.decision.toUpperCase()} — ${r.tool_executed?'simulated tool call executed':'tool call blocked'}; attack success: ${r.attack_success}.`}</script></body></html>"""
