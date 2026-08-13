"""
FastAPI entrypoint.

Endpoints
    GET  /                      triage board (phone-first)
    GET  /api/jobs              scored jobs as JSON
    POST /api/jobs/{key}/status saved | applied | dismissed
    POST /api/scan              run a scan now (also the cron target)
    POST /api/digest            send the email digest
    GET  /health                uptime ping

The board is deliberately a triage tool, not an analytics dashboard: the only
questions it answers are "what is worth my time this morning" and "what did I
already deal with".
"""

from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

import scanner, store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="TX Job Scanner", version="1.0")
CRON_TOKEN = os.getenv("CRON_TOKEN", "")


@app.on_event("startup")
def _startup() -> None:
    store.init_db()


@app.get("/health")
def health() -> dict:
    return {"ok": True, **store.stats()}


@app.get("/api/jobs")
def api_jobs(status: str | None = None, metro: str | None = None,
             track: str | None = None, limit: int = 100) -> JSONResponse:
    return JSONResponse(store.get_jobs(status=status, metro=metro, track=track, limit=limit))


@app.post("/api/jobs/{key}/status")
def api_set_status(key: str, status: str) -> dict:
    try:
        store.set_status(key, status)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "key": key, "status": status}


@app.post("/api/scan")
def api_scan(background: BackgroundTasks, token: str = "") -> dict:
    """Cron target. Set CRON_TOKEN so a stranger can't burn your API quota."""
    if CRON_TOKEN and token != CRON_TOKEN:
        raise HTTPException(401, "bad token")
    result = scanner.run_scan()
    background.add_task(scanner.send_digest)
    return result


@app.post("/api/digest")
def api_digest(token: str = "") -> dict:
    if CRON_TOKEN and token != CRON_TOKEN:
        raise HTTPException(401, "bad token")
    return scanner.send_digest()


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>TX Job Board</title>
<style>
  :root{
    --ink:#10202E; --paper:#F2F4F6; --card:#FFFFFF; --line:#DDE3E8;
    --navy:#1F3864; --signal:#C25E00; --muted:#5B6B7A; --good:#1E6B4F;
    --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
       -webkit-font-smoothing:antialiased;padding-bottom:40px}
  header{position:sticky;top:0;z-index:10;background:var(--ink);color:#fff;
         padding:14px 16px calc(14px + env(safe-area-inset-top)) 16px}
  h1{margin:0;font-size:17px;font-weight:650;letter-spacing:.2px}
  .sub{font-family:var(--mono);font-size:11px;color:#8FA3B5;margin-top:3px;letter-spacing:.4px}
  .bar{display:flex;gap:6px;overflow-x:auto;padding:10px 16px;background:var(--ink);
       scrollbar-width:none}
  .bar::-webkit-scrollbar{display:none}
  .chip{flex:0 0 auto;border:1px solid #2E4457;background:transparent;color:#C6D4E0;
        font-family:var(--mono);font-size:11px;letter-spacing:.5px;text-transform:uppercase;
        padding:6px 11px;border-radius:2px;cursor:pointer}
  .chip[aria-pressed="true"]{background:#fff;color:var(--ink);border-color:#fff}
  main{padding:14px 12px;max-width:680px;margin:0 auto}
  .card{position:relative;background:var(--card);border:1px solid var(--line);
        border-radius:3px;padding:13px 14px 13px 20px;margin-bottom:10px}
  /* signature: a priority stripe on the card edge, height = fit score */
  .stripe{position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--line)}
  .stripe i{position:absolute;left:0;bottom:0;width:100%;background:var(--navy);display:block}
  .card.hot .stripe i{background:var(--signal)}
  .eyebrow{font-family:var(--mono);font-size:10px;letter-spacing:.9px;text-transform:uppercase;
           color:var(--muted);display:flex;gap:8px;align-items:center}
  .score{color:var(--ink);font-weight:600}
  .title{display:block;font-size:16px;font-weight:640;line-height:1.25;margin:5px 0 3px;
         color:var(--navy);text-decoration:none}
  .meta{font-size:13px;color:var(--ink)}
  .pay{font-family:var(--mono);font-size:12px;color:var(--good);margin-top:3px}
  ul{margin:8px 0 0;padding-left:16px}
  li{font-size:12.5px;color:var(--muted);line-height:1.45}
  li.flag{color:var(--signal)}
  .acts{display:flex;gap:6px;margin-top:11px}
  .acts button{flex:1;font-family:var(--mono);font-size:11px;letter-spacing:.5px;
        text-transform:uppercase;padding:8px 0;border:1px solid var(--line);
        background:#fff;color:var(--muted);border-radius:2px;cursor:pointer}
  .acts button:active{background:var(--paper)}
  .acts button:focus-visible{outline:2px solid var(--navy);outline-offset:1px}
  .empty{text-align:center;color:var(--muted);font-size:14px;padding:48px 20px}
  .empty b{display:block;color:var(--ink);font-size:15px;margin-bottom:6px}
  @media (prefers-reduced-motion:no-preference){
    .card{transition:opacity .18s ease}
  }
</style></head>
<body>
<header>
  <h1>Texas Job Board</h1>
  <div class="sub" id="stamp">loading</div>
</header>
<div class="bar" id="filters">
  <button class="chip" data-f="status" data-v="new" aria-pressed="true">New</button>
  <button class="chip" data-f="status" data-v="saved" aria-pressed="false">Saved</button>
  <button class="chip" data-f="status" data-v="applied" aria-pressed="false">Applied</button>
  <button class="chip" data-f="metro" data-v="san_antonio" aria-pressed="false">San Antonio</button>
  <button class="chip" data-f="metro" data-v="dallas" aria-pressed="false">Dallas</button>
  <button class="chip" data-f="track" data-v="direct" aria-pressed="false">Direct</button>
  <button class="chip" data-f="track" data-v="stretch" aria-pressed="false">Stretch</button>
  <button class="chip" data-f="track" data-v="growth" aria-pressed="false">Growth</button>
</div>
<main id="list"></main>

<script>
const state = {status:'new', metro:'', track:''};

function money(n){ return '$' + Math.round(n).toLocaleString(); }

function card(j){
  const hot = j.score >= 60 ? ' hot' : '';
  const pay = j.salary_max ? money(j.salary_max) + ' max'
            : j.salary_min ? 'from ' + money(j.salary_min) : '';
  const reasons = (j.reasons||[]).slice(0,3).map(r=>`<li>${r}</li>`).join('');
  const flags   = (j.flags||[]).slice(0,2).map(f=>`<li class="flag">${f}</li>`).join('');
  return `<article class="card${hot}" data-key="${j.key}">
    <span class="stripe"><i style="height:${Math.max(6, j.score)}%"></i></span>
    <div class="eyebrow">
      <span class="score">${Math.round(j.score)}</span>
      <span>${j.track}</span><span>${(j.metro||'').replace('_',' ')}</span>
    </div>
    <a class="title" href="${j.url}" target="_blank" rel="noopener">${j.title}</a>
    <div class="meta">${j.company}${j.location ? ' &middot; ' + j.location : ''}</div>
    ${pay ? `<div class="pay">${pay}</div>` : ''}
    <ul>${reasons}${flags}</ul>
    <div class="acts">
      <button onclick="mark('${j.key}','saved')">Save</button>
      <button onclick="mark('${j.key}','applied')">Applied</button>
      <button onclick="mark('${j.key}','dismissed')">Dismiss</button>
    </div>
  </article>`;
}

async function load(){
  const p = new URLSearchParams();
  Object.entries(state).forEach(([k,v]) => v && p.set(k,v));
  const res = await fetch('/api/jobs?' + p);
  const jobs = await res.json();
  const list = document.getElementById('list');
  list.innerHTML = jobs.length
    ? jobs.map(card).join('')
    : `<div class="empty"><b>Nothing here yet.</b>Run a scan, or widen the filters.</div>`;
  document.getElementById('stamp').textContent =
    jobs.length + ' listings · ' + new Date().toLocaleDateString();
}

async function mark(key, status){
  await fetch(`/api/jobs/${encodeURIComponent(key)}/status?status=${status}`, {method:'POST'});
  const el = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
  if (el){ el.style.opacity = '0'; setTimeout(load, 180); }
}

document.getElementById('filters').addEventListener('click', e => {
  const b = e.target.closest('.chip'); if(!b) return;
  const {f, v} = b.dataset;
  state[f] = (state[f] === v) ? '' : v;
  document.querySelectorAll(`.chip[data-f="${f}"]`).forEach(c =>
    c.setAttribute('aria-pressed', String(c.dataset.v === state[f])));
  load();
});

load();
</script>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def board() -> str:
    return PAGE
