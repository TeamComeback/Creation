# Florida Job Scanner

A daily job scanner for the Tampa Bay, Jacksonville, Orlando and Tallahassee markets,
scored against your
resume. Runs itself on a schedule, emails you a ranked digest, and gives you a
phone-sized board to triage what it found.

Built to run entirely in the cloud — nothing installs on your work PC.

---

## What it does

Every weekday morning it queries job APIs across three tracks:

| Track | What it looks for | Why |
|---|---|---|
| **Direct** | AR specialist, cash application, billing, finance associate, banker, will call | Your resume already wins these |
| **Stretch** | BSA/AML analyst, fraud, KYC, credit analyst, treasury ops, revenue cycle | One credible step up — your banking history gets you screened in, and the pay ceiling is higher |
| **Growth** | Healthcare revenue cycle, GRC/compliance, supply chain, claims, insurance ops | Sectors projected to expand in these metros that your transferable skills reach |

Each posting gets a 0–100 fit score from four inputs — skill keyword overlap with
your background, title match, pay against your floor, and whether the employer sits
in a growing part of the metro. Phrases like "CPA required" or "10+ years" subtract.
Anything under 35 never reaches you.

Pay is cost-of-living adjusted before scoring, because $58K in Jacksonville is not
$58K in Albany. Tampa Bay and Orlando are indexed at 0.99, Jacksonville at 0.94,
Tallahassee at 0.90.

## Setup

**1. Get the API keys** (both have free tiers, ~10 minutes total)

- **Adzuna** — [developer.adzuna.com](https://developer.adzuna.com). Register, copy
  your app ID and key. Best salary data of any free source, which matters since pay
  is a scored input.
- **JSearch** — [RapidAPI](https://rapidapi.com), subscribe to the free JSearch plan.
  It indexes Google for Jobs, which reaches Indeed, LinkedIn, Glassdoor and
  ZipRecruiter through a legitimate API rather than scraping them.

You can start with just Adzuna. Missing keys are skipped, not fatal.

**2. Set up the digest email**

Gmail requires an App Password (2FA on → App Passwords → generate). Your normal
password will not authenticate.

**3. Deploy**

Every file sits at the root — no subfolders — so you can upload straight from
Safari on a phone: on the empty repo page tap **uploading an existing file**,
select all the files, commit. Then in Render: **New → Blueprint** → pick the repo.
`render.yaml` provisions the web service, a 1 GB disk so the database survives
redeploys, and a weekday cron at 6:30am Central.

Do not upload the zip itself — Render reads files, not archives.

Fill in the environment variables from `.env.example` in the Render dashboard.
Set `SCAN_URL` on the cron service to `https://your-app.onrender.com/api/scan?token=YOUR_CRON_TOKEN`.

Same pattern works on Railway or Fly.io if you prefer.

**4. Verify before trusting it**

```bash
python smoke_test.py
```

Runs the scoring engine against mock postings with no network and no keys. You
should see an AML analyst role at the top and a "CPA required, 10+ years" director
role scored to zero. If the ranking looks wrong to you, that's a tuning problem —
see below.

## Using it

- **`/`** — the triage board. Filter by status, metro, or track; save, mark applied,
  or dismiss. Built for a phone.
- **`/api/scan?token=…`** — run a scan on demand.
- **`/health`** — counts and last scan result.

## Tuning

Everything you'd want to change lives in `job_profile.py`. You should not need to
touch the scoring code.

- **Add or drop target roles** → `SEARCH_TRACKS`
- **Change what counts as a skill match** → `SKILL_KEYWORDS` (the number is the
  point value; "will call" and "cash application" are weighted highest because
  they're the least common things on your resume)
- **Add employers you want to work for** → `SECTOR_BONUS`. Sysco is weighted 10 —
  an internal transfer beats an external hire every time.
- **Move the money targets** → `SALARY_FLOOR` / `SALARY_TARGET` / `SALARY_STRETCH`
- **Drop a metro or add Austin** → `METROS`

## Scan behavior

`POST /api/scan` returns immediately and runs the scan in the background, so a
cold free-tier start can't outlast a scheduler's request timeout and get logged
as a failed run. The counts land in `/health` under `last_scan`. Add
`?wait=true` to block and get `found` / `kept` / `new` / `purged` back in the
response — that's the one to use from `/docs` when you want to watch it work.

Postings not seen in a scan for 14 days are deleted, so dead links stop
outranking live ones. Anything you marked **saved** or **applied** is kept no
matter how old — that's your record, not the scanner's. Change the window with
`STALE_AFTER_DAYS`.

Age is scored, not just stored: under 48 hours is worth +10, under a week +5,
over three weeks −8. A posting whose source didn't report a date is neutral.

## Known limitations

- **The Greenhouse and Lever slugs in `source_boards.py` are unverified.**
  Open `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` in a browser; if you
  get JSON, the slug is good. Delete what 404s. Bad slugs are logged and skipped.
- **Raymond James, Publix, and Florida Blue run on Workday**, whose endpoints are per-tenant and
  unstable. They're the three biggest employers on your target list, so set up email
  alerts on their careers pages directly as a backstop.
- **No LinkedIn scraping.** It violates their terms and gets accounts restricted.
  JSearch reaches LinkedIn postings legitimately.
- **Free-tier quota is the real constraint.** A scan costs metros × tracks ×
  `QUERIES_PER_RUN` calls. With four metros the default is 2, which keeps a scan at
  24 calls (~720/month daily) against Adzuna's ~1,000/month free tier. Queries
  rotate by day, so every query is still covered every five days. Adding a metro
  or raising this number means checking that math first.
- **Render's free web tier sleeps.** First load after idle takes ~30 seconds. The
  cron still fires regardless.
