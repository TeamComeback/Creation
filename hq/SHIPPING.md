# HQ shipping run: runbook

The shipping run is the only part of the HQ that can change the TeamComeback repos. It runs in the
HQ setup chat at about 9:05 AM and 8:05 PM Eastern. This file is its memory: if the chat's workspace
is ever reset, everything needed to resume is here.

## 0. Recover the workspace if needed
Clones live under `/home/claude/<repo lowercased>` (creation, curiosity, fantasy-tracker, ingenuity,
perseverance). If one is missing, call `add_repo {owner: "TeamComeback", repo, access: "push"}` and clone it
there. Then `source /home/claude/creation/hq/ship.sh`.

## 1. Find the work
Query the HQ backlog (artifact https://claude.ai/artifact/XL1xVMpYxmKSq6R2XurA6V, collection `backlog`,
status in approved / undo_requested / in_progress / blocked). Skip anything already `shipped` in
`hq-shipping-log.json`. Items with business `hq` that change `hq/collector.py` or this folder are yours;
HQ page changes belong to the upkeep run.

## 2. Autonomy levels
- **Act, then tell**: repairs to things that are broken (crashes, failing automation, dead feeds, wrong
  data) only if question `q9` in the HQ is answered yes; tests, docs, and this folder always.
- **Approved first**: anything that changes how a company behaves. Ship only `approved` items.
- **Owner only**: real money, accounts, keys and secrets, paid services, deleting data, making anything
  public. Never do these; write `owner_action` instead.

## 3. Ship
`git pull` main, branch `hq/<short-name>`, follow the item's plan, add a small test where one fits, delete
`__pycache__`, then `ship <Repo> <branch> "<title>" "<body>"`. Rules that never bend: Curiosity and
Perseverance are paper money only; Perseverance's $5 minimum bet is fixed; Ingenuity's v2.7 engine stays
intact. If a change cannot be verified, mark it `blocked` with a note instead of shipping it.

## 4. Report
Unattended runs cannot write to the HQ database. Append to `hq-shipping-log.json` on Creation main:
items `{id, status, repo, link, commit, note, owner_action, at}` and one run entry
`{id: "r<UTC compact>ship", time (Eastern ISO), summary, tokens, by_company}`. Commit message must end with
`[skip render]`. The upkeep run copies this into the HQ.

## 5. Watch the other half
Read the newest docs in the HQ `runs` collection. If the last upkeep run (id not ending in `ship`) is older
than 14 hours, or the last three all have `ok: false`, tell the owner in one sentence.
On Sundays, also save a backup: list every HQ collection and commit the JSON to the `hq-data` branch under
`backup/`.

## 6. Keep the chain alive
Schedule the next two slots (14:05 and 01:05 UTC while Eastern is UTC-5; 13:05 and 00:05 UTC from
March 8 2027), skipping any slot that already has a pending shipping run. If this run arrived late, skip
the missed slots.
