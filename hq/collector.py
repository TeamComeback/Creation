#!/usr/bin/env python3
"""Team Comeback HQ collector.

Pulls every project's public data, runs the reminder agents and the
system watchdog, and writes snapshot.json, findings.json and shipping.json
next to itself (or to argv[1]).

Source of truth: hq/collector.py in TeamComeback/Creation. The "HQ data"
GitHub Action runs it three times a day and publishes the output to the
hq-data branch, so the HQ's numbers no longer depend on a Claude session
being allowed to execute code. It can still be run by hand:

Run:  python3 -I collector.py [out_dir]
"""
import json, re, sys, os, urllib.request
from datetime import datetime, timezone, timedelta, date

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
NOW = datetime.now(timezone.utc)
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # very old Python or no tz database
    ET = timezone(timedelta(hours=-5))
GH_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
FEED_LOG = []   # one entry per source fetched: the watchdog reports on these

SRC = {
    "curiosity": "https://teamcomeback.github.io/Curiosity/data/dashboard.json",
    "curiosity_health": "https://teamcomeback.github.io/Curiosity/data/health.json",
    "ft_data": "https://teamcomeback.github.io/Fantasy-Tracker/data.json",
    "ft_page": "https://teamcomeback.github.io/Fantasy-Tracker/",
    "ingenuity": "https://teamcomeback.github.io/Ingenuity/data/stats/manifest.json",
    "jobs": "https://creation-lc6a.onrender.com/api/jobs?limit=500",
    "pv_state": "https://teamcomeback.github.io/Perseverance/data/state.json",
    "pv_manual": "https://teamcomeback.github.io/Perseverance/data/manual.json",
    "pv_budget": "https://teamcomeback.github.io/Perseverance/data/budget.json",
    "pv_history": "https://teamcomeback.github.io/Perseverance/data/history.json",
}

# Facts that live only in conversation history, not in any feed. The
# Memory Auditor ages these and asks for a refresh when they go stale.
STATIC = {
    "ingenuity": {"as_of": "2026-11-09", "graded": 701, "closing_lines": 0, "interval_cov": 82, "interval_target": 80,
                  "engine": "v2.7", "backtest_done": True, "stats_paused": True},
    "balldontlie": {"as_of": "2026-10-22", "draft": "2026-10-18", "team": "Team Comeback", "pick": 6,
                    "strategy": "Volume Blitz (punt FG% and FT%)", "newsletter_live": False, "teams": 10},
    "justbaked": {"as_of": "2026-08-21", "stage": "Final pre-launch", "owner_parked": "2026-11-13",
                  "note": "Runs on Square's website; changes need a computer. Owner unsure how to automate sales yet.",
                  "open_items": ["Charity names and links", "Social media URLs", "Premium package contents",
                                 "Burn Heart Cake price"]},
    "screener": {"as_of": "2026-07-18", "stage": "Packaged, not deployed", "blocker": "Polygon.io key needs MacBook"},
}
# What older notes say, checked against live data.
CLAIMS = [
    {"id": "claim-curiosity-stakes", "business": "curiosity",
     "said": "Each firm starts with $1,000 and races to $10,000",
     "check": lambda s: (s["curiosity"]["start"], s["curiosity"]["goal"]) == (1000, 10000),
     "live": lambda s: f"Live race: ${s['curiosity']['start']:,.0f} start, ${s['curiosity']['goal']:,.0f} goal"},
]


# When a site is unreachable (a locked-down cloud environment blocks *.github.io),
# read the same file from a local clone of the repo instead. The Pages sites
# publish straight from each repo, so the clone holds the same data.
LOCAL = {
    "https://teamcomeback.github.io/Curiosity/": "curiosity",
    "https://teamcomeback.github.io/Fantasy-Tracker/": "fantasy-tracker",
    "https://teamcomeback.github.io/Ingenuity/": "ingenuity",
    "https://teamcomeback.github.io/Perseverance/": "perseverance/docs",
}


def _clone_dir(name):
    roots = [os.getcwd(), os.path.dirname(os.getcwd()), os.path.expanduser("~"), "/home/user", "/home/claude", "/workspace", "/repos"]
    roots += [p for p in os.environ.get("HQ_REPO_ROOTS", "").split(":") if p]
    for r in roots:
        try:
            for d in os.listdir(r):
                if d.lower() == name and os.path.isdir(os.path.join(r, d, ".git")):
                    return os.path.join(r, d)
        except OSError:
            pass
    return None


def _local(url, kind):
    for prefix, name in LOCAL.items():
        if url.startswith(prefix):
            sub_dir = ""
            if "/" in name:
                name, sub_dir = name.split("/", 1)
            root = _clone_dir(name)
            if not root:
                return None
            root = os.path.join(root, sub_dir)
            rel = url[len(prefix):].split("?")[0] or "index.html"
            path = os.path.join(root, rel)
            if not os.path.isfile(path):
                return None
            raw = open(path, encoding="utf-8", errors="replace").read()
            return json.loads(raw) if kind == "json" else raw
    return None


def get(url, kind="json", tries=2):
    err = ""
    for attempt in range(tries):
        try:
            hdr = {"User-Agent": "TeamComebackHQ/2"}
            if GH_TOKEN and url.startswith("https://api.github.com/"):
                hdr["Authorization"] = "Bearer " + GH_TOKEN
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=60 if "onrender.com" in url else 40) as r:
                raw = r.read().decode("utf-8", "replace")
            out = json.loads(raw) if kind == "json" else raw
            FEED_LOG.append({"url": url, "ok": True, "via": "web"})
            return out
        except Exception as e:  # noqa: BLE001
            err = str(e)[:160]
    try:
        alt = _local(url, kind)
        if alt is not None:
            FEED_LOG.append({"url": url, "ok": True, "via": "clone"})
            return alt
    except Exception:
        pass
    FEED_LOG.append({"url": url, "ok": False, "via": "none", "error": err})
    return {"__error": err}


def age_days(ts):
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=ET)
        return round((NOW - t).total_seconds() / 86400, 1)
    except Exception:
        try:
            return (NOW.date() - date.fromisoformat(ts[:10])).days
        except Exception:
            return None


def fresh(days, half_life):
    """100 when brand new, 50 at half_life days, falls toward 0."""
    if days is None:
        return 0
    return round(100 * 0.5 ** (max(days, 0) / half_life))


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, round(x)))


findings = []


def find(fid, agent, business, severity, title, detail, action=""):
    findings.append({"id": fid, "agent": agent, "business": business, "severity": severity,
                     "title": title, "detail": detail, "action": action})


snap = {"updated": NOW.astimezone(ET).isoformat(timespec="minutes"), "businesses": {}}
B = snap["businesses"]

# ---------------- Curiosity Capital (AI trading race) ----------------
d = get(SRC["curiosity"])
h = get(SRC["curiosity_health"])
if "__error" in d:
    B["curiosity"] = {"error": d["__error"]}
    find("src-curiosity", "staleness", "curiosity", "high", "Trading race feed is unreachable",
         d["__error"], "Open the Curiosity repo and check the last Actions run.")
else:
    race = d.get("race", {})
    start = race.get("start_balance") or d.get("start_balance") or 0
    goal = race.get("goal") or 0
    agents = []
    for a in d.get("agents", []):
        agents.append({k: a.get(k) for k in ("id", "name", "equity", "status", "progress_pct", "open", "closed",
                                              "win_rate", "max_dd_pct", "competing", "exhibition", "risk_adj")}
                      | {"ret_pct": round((a["equity"] / start - 1) * 100, 2) if start else None,
                         "note": (a.get("notes") or [{}])[0].get("note", "")[:240]})
    racing = [a for a in agents if a["competing"]]
    spy = next((a for a in agents if a["id"] == "baseline"), None)
    leader = max(racing, key=lambda a: a["equity"]) if racing else None
    curve = []
    for row in d.get("equity_curve", [])[-30:]:
        vals = [v for k, v in row["agents"].items() if any(r["id"] == k for r in racing)]
        curve.append({"date": row["date"], "racing": round(sum(vals), 2),
                      "leader": row["agents"].get(leader["id"]) if leader else None,
                      "spy": row["agents"].get("baseline")})
    pool_start = start * len(racing)
    pool_now = sum(a["equity"] for a in racing)
    pool_ret = round((pool_now / pool_start - 1) * 100, 2) if pool_start else 0
    spy_ret = spy["ret_pct"] if spy else 0
    upd_age = age_days(d.get("updated"))
    health_ok = isinstance(h, dict) and h.get("ok") is True
    checks_bad = [c["name"] for c in (h.get("checks") or []) if not c.get("ok")] if isinstance(h, dict) else []
    regime = d.get("regime", {})
    radar = (d.get("radar") or {}).get("now", {})
    days_to_goal = None
    rec = get(SRC["curiosity"].replace("dashboard", "recaps"))
    if isinstance(rec, list) and rec and leader:
        f = rec[-1].get("firms", {}).get(leader["id"], {})
        days_to_goal = f.get("days_to_goal")
    eff = clamp(0.5 * 100 + 0.5 * fresh(upd_age, 2)) if health_ok else clamp(0.5 * 40 + 0.5 * fresh(upd_age, 2))
    # Profitability: racing pool return vs SPY, 50 = matching SPY, +/-1% edge = +/-5 points.
    prof = clamp(50 + (pool_ret - spy_ret) * 5)
    B["curiosity"] = {
        "start": start, "goal": goal, "updated": d.get("updated"), "age_days": upd_age,
        "pool_now": round(pool_now, 2), "pool_start": pool_start, "pool_ret": pool_ret, "spy_ret": spy_ret,
        "edge": round(pool_ret - spy_ret, 2), "leader": leader and {"name": leader["name"], "equity": leader["equity"],
                                                                     "ret_pct": leader["ret_pct"], "progress_pct": leader["progress_pct"],
                                                                     "days_to_goal": days_to_goal},
        "agents": agents, "curve": curve, "health_ok": health_ok, "health_bad": checks_bad,
        "regime": {"trend": regime.get("spy_trend"), "vs200": regime.get("spy_vs_sma200_pct"),
                   "radar": radar.get("score"), "tier": radar.get("tier")},
        "brain": d.get("brain"), "compliance": d.get("compliance_today"),
        "efficiency": eff, "profitability": prof, "automation": "Full: GitHub Actions trade, plan and recap on schedule",
    }
    if upd_age is not None and upd_age > 3:
        find("stale-curiosity", "staleness", "curiosity", "high", "Trading race hasn't updated in %.0f days" % upd_age,
             "Last dashboard write was %s." % d.get("updated"), "Check the Curiosity Actions tab for a failed workflow.")
    if not health_ok:
        find("health-curiosity", "overseer", "curiosity", "high", "Trading health check failing",
             ", ".join(checks_bad) or "health.json reports not ok", "Fix the failing check before the next session.")
    for a in racing:
        if (a["max_dd_pct"] or 0) >= 25:
            find(f"dd-{a['id']}", "overseer", "curiosity", "med",
                 f"{a['name']} is in a {a['max_dd_pct']:.0f}% drawdown",
                 f"Equity ${a['equity']:,.2f} ({a['ret_pct']:+.1f}%). The race rules fail an agent below $10, so this "
                 f"is still alive, but it is dragging the pool.",
                 "Review its thesis and position sizing in the Curiosity journal.")
    idle = [a for a in racing if (a["open"] or 0) == 0 and (a["closed"] or 0) == 0]
    for a in idle:
        find(f"idle-{a['id']}", "overseer", "curiosity", "low", f"{a['name']} hasn't placed a trade yet",
             "Zero open and zero closed positions since the race started.",
             "Check whether its entry rules can fire in the current regime.")

# ---------------- Fantasy Tracker (NFL season-long parlays) ----------------
fd = get(SRC["ft_data"])
fp = get(SRC["ft_page"], "text")
if "__error" in fd or isinstance(fp, dict):
    B["nfl"] = {"error": (fd.get("__error") if isinstance(fd, dict) else "") or "page unreachable"}
    find("src-nfl", "staleness", "nfl", "high", "Fantasy Tracker feed is unreachable", str(B["nfl"]["error"]), "")
else:
    blk = fp[fp.find("const PARLAYS"):]
    blk = blk[:blk.find("];") + 2]
    slips = []
    for p in re.finditer(r'id:"(\w+)", name:"([^"]+)", stake:"\$([\d.]+)", payout:"\$([\d.,]+)"', blk):
        slips.append({"key": p.group(1), "name": p.group(2), "stake": float(p.group(3)),
                      "payout": float(p.group(4).replace(",", "")), "pos": p.start(), "legs": []})
    through = fd.get("throughWeek") or 0
    for m in re.finditer(r'\{id:"(\w+)",who:"([^"]+)",team:"(\w+)",pos:"(\w+)",color:"([^"]+)",stat:"([^"]+)",'
                         r'line:([\d.]+),dir:"(\w+)"', blk):
        slip = [s for s in slips if s["pos"] < m.start()][-1]
        lid = m.group(1)
        L = fd.get("legs", {}).get(lid, {})
        wk = {int(k): v for k, v in L.get("weeks", {}).items() if int(k) <= through}
        byes = sum(1 for v in wk.values() if v.get("opp") == "BYE")
        played = sum(1 for v in wk.values() if v.get("opp") != "BYE" and v.get("inj") != "O" and v.get("val") is not None)
        cur = sum((v.get("val") or 0) for v in wk.values())
        rem = 17 - (len(wk) - byes)
        line = float(m.group(7))
        over = m.group(8) == "over"
        rate = cur / played if played else 0
        need = (line - cur) / rem if rem > 0 else 0
        settled = L.get("settled")
        if not settled and over and cur > line:
            settled = "win*"
        if settled:
            state = "won" if settled.startswith("win") else "lost"
        elif over and (line <= 1 or ("yards" in m.group(6) and line <= 15)):
            state = "needs a play"
        elif over:
            ratio = rate / need if need > 0 else 9
            state = "ahead" if ratio >= 1.1 else "on pace" if ratio >= 0.9 else "behind" if ratio >= 0.6 else "far behind"
        else:
            ratio = need / rate if rate else 9
            state = "ahead" if ratio >= 1.1 else "on pace" if ratio >= 0.9 else "behind"
        slip["legs"].append({"id": lid, "who": m.group(2), "team": m.group(3), "color": m.group(5),
                             "stat": m.group(6), "line": line, "dir": m.group(8), "cur": round(cur, 1),
                             "played": played, "rem": rem, "rate": round(rate, 2), "need": round(need, 2),
                             "inj": L.get("inj", ""), "state": state, "settled": settled})
    stake = sum(s["stake"] for s in slips)
    pay = sum(s["payout"] for s in slips)
    for s in slips:
        s.pop("pos")
        live = [l for l in s["legs"] if l["state"] not in ("won",)]
        s["alive"] = not any(l["state"] == "lost" for l in s["legs"])
        s["weak"] = [l["who"] for l in live if l["state"] in ("far behind", "behind")]
        ok = sum(1 if l["state"] in ("won", "ahead", "on pace") else 0.5 if l["state"] == "needs a play" else 0 for l in s["legs"])
        s["health"] = round(100 * ok / len(s["legs"])) if s["legs"] else 0
    upd_age = age_days(fd.get("updated"))
    best = max(slips, key=lambda s: s["health"]) if slips else None
    eff = clamp(0.5 * 55 + 0.5 * fresh(upd_age, 5))  # manual weekly stat entry = partial automation
    prof = clamp(sum(s["health"] for s in slips) / len(slips)) if slips else 0
    B["nfl"] = {"updated": fd.get("updated"), "through_week": through, "age_days": upd_age, "stake": round(stake, 2),
                "payout": round(pay, 2), "slips": slips, "efficiency": eff, "profitability": prof,
                "automation": "Partial: weekly stats entered by hand, site publishes from data.json"}
    if upd_age is not None and upd_age > 8:
        find("stale-nfl", "deadline", "nfl", "high", "NFL slips are a week behind",
             f"Data runs through Week {through}, last updated {fd.get('updated')}.", "Enter last week's stat lines.")
    for s in slips:
        for l in s["legs"]:
            if l["settled"] == "win*":
                pass  # the tracker already shows a cleared over leg as Cashed; nothing to settle by hand
            elif l["state"] == "far behind":
                find(f"pace-{l['id']}", "overseer", "nfl", "med", f"{l['who']} is far behind pace on {s['name']}",
                     f"Producing {l['rate']:g}/game, needs {l['need']:g}/game over {l['rem']} games for {l['dir']} {l['line']:g} {l['stat']}.",
                     "Watch usage and injury news. One more miss likely sinks this slip.")
            elif l["state"] == "needs a play":
                find(f"play-{l['id']}", "overseer", "nfl", "low", f"{l['who']} still needs one play on {s['name']}",
                     f"{l['cur']:g} of {l['line']:g} {l['stat']} with {l['rem']} games left. A single trick play or carry clears it.",
                     "Nothing to do but watch. It's a coin flip each week, not a pace problem.")
            if l["inj"] in ("O", "D", "IR") and not l["settled"]:
                find(f"inj-{l['id']}", "overseer", "nfl", "med", f"{l['who']} injury designation: {l['inj']}",
                     f"Leg on {s['name']} ({l['stat']}).", "Check practice reports before the weekend.")

# ---------------- Ingenuity (MLB totals research) ----------------
ig = get(SRC["ingenuity"])
st = STATIC["ingenuity"]
if "__error" in ig:
    B["ingenuity"] = {"error": ig["__error"]}
    find("src-ingenuity", "staleness", "ingenuity", "high", "Ingenuity stats feed is unreachable", ig["__error"], "")
else:
    gen_age = age_days(ig.get("generatedAt"))
    rows = sum(x.get("rows", 0) for x in ig.get("datasets", []))
    eff = clamp(0.5 * 85 + 0.5 * fresh(gen_age, 2))
    # Research phase: profitability tracks how close interval coverage sits to target and closing-line capture.
    cov_gap = abs(st["interval_cov"] - st["interval_target"])
    clv = 100 * st["closing_lines"] / st["graded"] if st["graded"] else 0
    prof = clamp(0.6 * (100 - cov_gap * 10) + 0.4 * clv)
    B["ingenuity"] = {"generated": ig.get("generatedAt"), "data_through": ig.get("dataThrough"), "age_days": gen_age,
                      "datasets": [{"label": x.get("label"), "rows": x.get("rows")} for x in ig.get("datasets", [])],
                      "rows": rows, "season": ig.get("season"), **{k: v for k, v in st.items()},
                      "efficiency": eff, "profitability": prof,
                      "automation": "High: daily GitHub Action publishes Savant and MLB stats; graded games logged on device"}
    offseason = bool(ig.get("dataThrough")) and (NOW.date() - date.fromisoformat(ig["dataThrough"])).days > 14
    if gen_age is not None and gen_age > 2 and not offseason:   # paused on purpose in the offseason (q2)
        find("stale-ingenuity", "staleness", "ingenuity", "med", "Ingenuity daily stats Action looks stalled",
             f"Manifest generated {ig.get('generatedAt')}.", "Check the Ingenuity Actions tab.")
    if ig.get("dataThrough") and (NOW.date() - date.fromisoformat(ig["dataThrough"])).days > 14:
        if not st.get("backtest_done"):
          find("offseason-ingenuity", "deadline", "ingenuity", "med", "Regular season is over: time for the offseason backtest",
             f"Stats run through {ig['dataThrough']}. You planned a calibration change backtested on the full season.",
             "Freeze the 2026 dataset, then backtest the calibration change against all graded games.")
        if not st.get("stats_paused"):
          find("action-ingenuity", "efficiency", "ingenuity", "low", "Daily stats Action is still running in the offseason",
             "No new games until spring, so each run spends Actions minutes for nothing.",
             "Pause the workflow's schedule until spring training.")
    if st["closing_lines"] == 0:
        find("clv-ingenuity", "overseer", "ingenuity", "high", f"0 of {st['graded']} closing lines captured",
             "Without closing lines you can't measure closing-line value, the clearest test of whether the model has an edge.",
             "Automate a closing-line grab 60-90 min before first pitch next season.")

# ---------------- Career Ops (job scanner) ----------------
jb = get(SRC["jobs"])
if isinstance(jb, dict) and "__error" in jb:
    B["jobs"] = {"error": jb["__error"], "efficiency": 20, "profitability": 0, "count": None,
                 "automation": "Daily scan via cron-job.org; Render free tier"}
    find("src-jobs", "staleness", "jobs", "high", "Job board is unreachable", jb["__error"],
         "Open creation-lc6a.onrender.com to wake it, then check cron-job.org history.")
else:
    jobs = jb if isinstance(jb, list) else jb.get("jobs", [])
    top = sorted(jobs, key=lambda j: j.get("score", 0), reverse=True)[:5]
    B["jobs"] = {"count": len(jobs), "top": [{k: j.get(k) for k in ("title", "company", "location", "score", "track", "url")} for j in top],
                 "efficiency": clamp(0.5 * 70 + 0.5 * (100 if jobs else 0)),
                 "profitability": clamp(min(len([j for j in jobs if (j.get('score') or 0) >= 70]), 10) * 10),
                 "automation": "Daily scan 10:00 AM via cron-job.org; Render free tier (sleeps, /tmp resets)"}
    if not jobs:
        find("empty-jobs", "staleness", "jobs", "high", "Job board is empty",
             "The board answers but holds 0 jobs. On Render's free tier the SQLite file in /tmp is wiped on every restart, "
             "so matches vanish after the service sleeps.",
             "Move storage to a free hosted database or write matches to the repo so they survive restarts.")

# ---------------- Perseverance (paper betting agent, $100 -> $1,000) ----------------
pv = get(SRC["pv_state"])
if "__error" in pv:
    B["perseverance"] = {"error": pv["__error"]}
    find("src-perseverance", "staleness", "perseverance", "high", "Betting agent feed is unreachable",
         pv["__error"], "Open the Perseverance repo and check the last Agent run in Actions.")
else:
    pm = get(SRC["pv_manual"]); pb = get(SRC["pv_budget"]); ph = get(SRC["pv_history"])
    pm = pm if isinstance(pm, dict) and "__error" not in pm else {}
    pb = pb if isinstance(pb, dict) and "__error" not in pb else {}
    ph = ph if isinstance(ph, list) else []
    bk = pv.get("book", {})
    st = pv.get("stats", {})
    mst = pm.get("stats", {})
    bets = bk.get("bets", [])

    def bet_line(b):
        legs = b.get("legs") or [{}]
        l = legs[0]
        if len(legs) > 1:
            what = f"{len(legs)}-leg parlay"
        else:
            pt = l.get("point")
            what = l.get("outcome", "") + ("" if pt is None else (f" {pt:+g}" if l.get("market") == "spreads" else f" {pt:g}"))
        dec = b.get("dec") or 2
        am = round((dec - 1) * 100) if dec >= 2 else -round(100 / (dec - 1))
        game = f"{l.get('away', '')} @ {l.get('home', '')}".strip(" @")
        return {"what": what, "odds": am, "book": l.get("book"), "game": game, "stake": b.get("stake"),
                "profit": b.get("profit"), "status": b.get("status"), "playbook": b.get("playbook"),
                "ev": b.get("ev"), "start": l.get("commence")}

    open_b = [b for b in bets if b.get("status") == "open"]
    done_b = [b for b in bets if b.get("status") not in ("open",)]
    upd_age = age_days(pv.get("updated"))
    first_ts = (ph[0]["ts"] if ph else pv.get("updated"))
    live_days = age_days(first_ts) or 0
    curve = [{"ts": p["ts"], "agent": p["a"], "you": p["m"]} for p in ph[-40:]]
    journal = [{"ts": j["ts"], "kind": j["kind"], "text": j["text"][:260]} for j in pv.get("journal", [])[-6:]]
    rem, monthly = pb.get("remaining"), pb.get("monthly") or 500
    roi = st.get("roi") or 0
    eff = clamp(0.5 * 90 + 0.5 * fresh(upd_age, 1))
    prof = clamp(50 + roi * 200)
    B["perseverance"] = {
        "updated": pv.get("updated"), "age_days": upd_age, "start": bk.get("start", 100), "goal": bk.get("goal", 1000),
        "run": bk.get("run", 1), "agent": {k: st.get(k) for k in ("equity", "bets", "won", "lost", "push", "roi", "clv", "open", "profit", "staked")},
        "you": {k: mst.get(k) for k in ("equity", "bets", "won", "lost", "push", "roi", "open", "profit")},
        "params": pv.get("params", {}), "paused": pv.get("paused", []), "weights": pv.get("weights", {}),
        "strategist_on": bool(pv.get("strategist")), "credits": rem, "credits_monthly": monthly,
        "per_scan": pb.get("allowance"), "open_bets": [bet_line(b) for b in open_b][-8:],
        "recent": [bet_line(b) for b in done_b][-6:][::-1], "journal": journal, "curve": curve,
        "runs": bk.get("runs", []), "efficiency": eff, "profitability": prof,
        "automation": "Full: GitHub Actions scan 3x daily, grade overnight and self-tune; your bets log through GitHub issues",
    }
    if upd_age is not None and upd_age > 1:
        find("stale-perseverance", "staleness", "perseverance", "high",
             "Betting agent hasn't run in %.0f day%s" % (upd_age, "" if upd_age < 1.5 else "s"),
             f"Scans run about 11am, 4pm and 7:30pm, but the last update was {pv.get('updated')}.",
             "Open the Perseverance Actions tab and check the last Agent run.")
    if rem is not None and rem < 60 and NOW.day < 25:
        find("credits-perseverance", "efficiency", "perseverance", "med", f"Only {rem} odds credits left this month",
             f"The agent spreads what's left across the remaining scans and stops at the 25-credit floor, so scans get thin until the reset.",
             "Fine to ride it out. A paid Odds API tier would let it cover more sports per scan.")
    stuck = [b for b in open_b if any(l.get("commence") and (age_days(l["commence"]) or 0) > 2 for l in b.get("legs", []))]
    if stuck:
        find("ungraded-perseverance", "settlement", "perseverance", "med", f"{len(stuck)} paper bet{'s' if len(stuck) > 1 else ''} should be graded by now",
             "Games started more than 2 days ago but the bets are still open: " + "; ".join(bet_line(b)["what"] for b in stuck[:3]) + ".",
             "Check the overnight grading run; bets void automatically after 4 days with no final score.")
    if not bets and live_days >= 2:
        find("dry-perseverance", "overseer", "perseverance", "low", "Betting agent hasn't placed a bet in 2 days",
             "Nothing on the board cleared its minimum edge. It lowers the bar after 3 empty scans in a row.",
             "Nothing needed yet. If it stays dry, consider a lower starting edge.")
    if (st.get("equity") or 100) < 50:
        find("dd-perseverance", "overseer", "perseverance", "med", f"Betting agent is down to ${st.get('equity'):.2f}",
             f"Run #{bk.get('run', 1)} started at $100. The $5 minimum bet means about {int((st.get('equity') or 0) // 5)} bets of runway left.",
             "Review which playbook is losing in its journal.")
    if not pv.get("strategist") and live_days >= 1:
        find("strategist-perseverance", "efficiency", "perseverance", "low", "Overnight strategist is off",
             "Without an Anthropic API key the agent still tunes itself, but nobody reviews the bigger picture each night.",
             "Optional: add an ANTHROPIC_API_KEY secret to the Perseverance repo.")

# ---------------- Ball Don't Lie (league newsletter) ----------------
bd = STATIC["balldontlie"]
first_mon = date(2026, 10, 26)
B["balldontlie"] = {**bd, "next_issue": first_mon.isoformat(), "efficiency": 30 if not bd["newsletter_live"] else 70,
                    "profitability": 40, "automation": "None yet: newsletter page not built"}
if not bd["newsletter_live"]:
    find("bdl-issue1", "deadline", "balldontlie", "med", "Week 1 newsletter isn't built yet",
         "The draft was Oct 18 and the season is underway. The Dan storyline is ready to open with.",
         f"Publish issue 1 by Mon {first_mon.strftime('%b %d')}.")

# ---------------- JustBaked (client) ----------------
jbk = STATIC["justbaked"]
a = age_days(jbk["as_of"])
B["justbaked"] = {**jbk, "age_days": a, "efficiency": clamp(0.5 * 60 + 0.5 * fresh(a, 30)), "profitability": 35,
                  "automation": "Netlify forms take orders; site handed off for self-editing"}
if a and a > 45 and not jbk.get("owner_parked"):   # owner answered q8 on Nov 13: parked, needs a computer
    find("stale-justbaked", "memory", "justbaked", "med", f"JustBaked launch has been parked {a:.0f} days",
         "Four pre-launch items were open: " + ", ".join(jbk["open_items"]) + ".",
         "Ask Alyiza for the four missing items and ship the site.")

# ---------------- Screener (tooling) ----------------
sc = STATIC["screener"]
a = age_days(sc["as_of"])
B["screener"] = {**sc, "age_days": a, "efficiency": 15, "profitability": 20,
                 "automation": "None: never deployed"}
if a and a > 60:
    find("stale-screener", "memory", "screener", "low", "Stock screener has sat undeployed for %.0f days" % a,
         "Curiosity's agents now scan a 7,000-symbol universe on their own, which covers most of what the screener was for.",
         "Decide: deploy it, fold its charts into Curiosity, or archive it.")

# ---------------- Memory Auditor: old notes vs live data ----------------
for c in CLAIMS:
    try:
        if not c["check"](B):
            find(c["id"], "memory", c["business"], "low", "Old note is out of date",
                 f"Notes say: {c['said']}. {c['live'](B)}.", "Confirm the new numbers so future work uses them.")
    except Exception:
        pass

# ---------------- Stage of each venture (not every idea earns money yet) ----------------
STAGE = {"curiosity": ("Testing", "Paper money: proving a strategy before real capital"),
         "jobs": ("Pipeline", "Feeds the day job search"),
         "nfl": ("Live bets", "Real money on three PrizePicks slips"),
         "ingenuity": ("Research", "Offseason: model work before next season"),
         "justbaked": ("Needs a computer", "Runs on Square's website; parked by you Nov 13 until there's a plan for automating sales"),
         "balldontlie": ("Community", "League content, no revenue"),
         "screener": ("Parked", "Built, never deployed"),
         "perseverance": ("Testing", "Paper money: racing $100 to $1,000")}
for k, (stg, why) in STAGE.items():
    if k in B:
        B[k]["stage"], B[k]["stage_note"] = stg, why

# ---------------- Roll-up ----------------
sev = {"high": 0, "med": 1, "low": 2}
findings.sort(key=lambda f: sev[f["severity"]])
snap["counts"] = {s: sum(1 for f in findings if f["severity"] == s) for s in sev}

# ---------------- Shipping log ----------------
# The shipping run (which has repo push access but can't write to the HQ while
# unattended) appends what it shipped to hq-shipping-log.json in the Creation repo.
# The autopilot applies these entries to the HQ backlog. See autopilot.md step 4.
SHIP_LOG = "https://raw.githubusercontent.com/TeamComeback/Creation/main/hq-shipping-log.json"
ship = get(SHIP_LOG)
if isinstance(ship, dict) and "__error" in ship:
    ship = get("https://api.github.com/repos/TeamComeback/Creation/contents/hq-shipping-log.json")
    if isinstance(ship, dict) and ship.get("content"):
        import base64
        try:
            ship = json.loads(base64.b64decode(ship["content"]).decode())
        except Exception as e:  # noqa: BLE001
            ship = {"__error": str(e)[:160]}
if not isinstance(ship, dict) or "__error" in ship:
    if isinstance(ship, dict):
        find("src-shiplog", "staleness", "hq", "low", "Shipping log is unreachable", ship.get("__error", ""),
             "Check that hq-shipping-log.json exists in TeamComeback/Creation.")
    ship = {"items": [], "runs": []}
json.dump(ship, open(os.path.join(OUT, "shipping.json"), "w"), indent=1)


# ---------------- System Watchdog: is the HQ itself healthy? ----------------
# Survivability: every moving part gets a heartbeat. Anything that stops is a
# flag the owner sees, instead of a silence nobody notices.
def hours_since(ts):
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=ET)
        return round((NOW - t).total_seconds() / 3600, 1)
    except Exception:
        return None


health = {"checked": NOW.astimezone(ET).isoformat(timespec="minutes"),
          "mode": "action" if os.environ.get("GITHUB_ACTIONS") else "local"}

# 1. Shipping heartbeat: runs twice a day (about 9:05 AM and 8:05 PM Eastern).
ship_runs = sorted((r for r in ship.get("runs", []) if hours_since(r.get("time")) is not None), key=lambda r: hours_since(r["time"]))
last_ship = ship_runs[0] if ship_runs else None
ship_age = hours_since(last_ship["time"]) if last_ship else None
health["shipping"] = {"last": last_ship and last_ship["time"], "age_hours": ship_age,
                      "ok": ship_age is not None and ship_age <= 15,
                      "summary": (last_ship or {}).get("summary", "")[:160]}
if not health["shipping"]["ok"]:
    find("hq-shipping-stalled", "watchdog", "hq", "high",
         "Shipping runs have stopped" if ship_age is None else f"No shipping run in {ship_age:.0f} hours",
         "Approved changes are built by a twice-daily run in the HQ setup chat. It has missed at least one slot, "
         "so anything you approve will sit until it resumes.",
         "Open the HQ setup chat and send: resume shipping")

# 2. Feeds: which sources answered, and which fell back to a clone or failed.
NAMES = {"Curiosity": "Curiosity", "Fantasy-Tracker": "Fantasy Tracker", "Ingenuity": "Ingenuity",
         "Perseverance": "Perseverance", "onrender.com": "Job board", "hq-shipping-log": "Shipping log"}
feeds = {}
for f in FEED_LOG:
    name = next((v for k, v in NAMES.items() if k in f["url"]), None)
    if not name:
        continue
    cur = feeds.setdefault(name, {"name": name, "ok": True, "via": f["via"], "error": ""})
    if not f["ok"]:
        cur.update(ok=False, via="none", error=f.get("error", ""))
health["feeds"] = list(feeds.values())

# 3. Automation: the latest run of every scheduled workflow in every repo.
REPOS = {"Curiosity": "curiosity", "Fantasy-Tracker": "nfl", "Ingenuity": "ingenuity", "Creation": "jobs",
         "Perseverance": "perseverance"}
flows = []
for repo, biz in REPOS.items():
    r = get(f"https://api.github.com/repos/TeamComeback/{repo}/actions/runs?per_page=40", tries=1)
    if not isinstance(r, dict) or "__error" in r:
        flows.append({"repo": repo, "business": biz, "name": "(could not check)", "ok": None})
        continue
    seen = set()
    for run in r.get("workflow_runs", []):
        nm = run.get("name") or ""
        if nm in seen or run.get("status") != "completed" or nm.startswith("pages build"):
            continue
        seen.add(nm)
        bad = run.get("conclusion") in ("failure", "timed_out", "startup_failure")
        flows.append({"repo": repo, "business": biz, "name": nm, "ok": not bad, "conclusion": run.get("conclusion"),
                      "at": run.get("updated_at"), "url": run.get("html_url")})
        if bad:
            find(f"wf-{repo.lower()}-{re.sub(r'[^a-z0-9]+', '-', nm.lower()).strip('-')}", "watchdog", biz, "med",
                 f"{repo}: the \"{nm}\" automation failed on its last run",
                 f"Last run ended {run.get('conclusion')} at {run.get('updated_at')}.",
                 "Have the company agent read the failed run's log and repair it.")
health["workflows"] = flows
health["ok"] = bool(health["shipping"]["ok"] and all(f["ok"] for f in health["feeds"])
                    and all(w["ok"] is not False for w in flows))
snap["health"] = health

findings.sort(key=lambda f: sev[f["severity"]])
snap["counts"] = {s: sum(1 for f in findings if f["severity"] == s) for s in sev}

json.dump(snap, open(os.path.join(OUT, "snapshot.json"), "w"), indent=1, default=str)
json.dump(findings, open(os.path.join(OUT, "findings.json"), "w"), indent=1)
print(f"findings {len(findings)} {snap['counts']} | health ok={health['ok']} | shipping {ship_age}h | "
      f"feeds down: {[f['name'] for f in health['feeds'] if not f['ok']]} | "
      f"failing automation: {[w['repo'] + '/' + w['name'] for w in flows if w['ok'] is False]}")
for k, b in B.items():
    print(k, b.get("stage", ""), b.get("error", ""))
