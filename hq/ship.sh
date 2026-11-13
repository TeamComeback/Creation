#!/usr/bin/env bash
# Shipping helper for HQ shipping runs.
#   source hq/ship.sh
#   ship <Repo> <branch> "<title>" "<body>"     (run inside the repo clone, on <branch>, with changes staged or tracked)
# Commits, pushes the branch, opens a PR through the REST API and squash-merges it.
ship () {
  local repo=$1 br=$2 title="$3" body="$4" n out
  local model="${HQ_MODEL:-Claude}" sess="${HQ_SESSION:-https://claude.ai/code/session_017EfgvjSKRPvPLxQUzWTyVR}"
  git -c user.name="Team Comeback HQ" -c user.email="noreply@anthropic.com" commit -qam "$title

$body

Co-Authored-By: $model <noreply@anthropic.com>
Claude-Session: $sess" || return 1
  git push -q -u origin "$br" 2>&1 | grep -v "^remote:"
  n=$(gh api "repos/TeamComeback/$repo/pulls" -X POST -f base=main -f head="$br" -f title="$title" -f body="$body

Approved in Team Comeback HQ.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

$sess" --jq .number) || return 1
  for try in 1 2; do
    out=$(gh api "repos/TeamComeback/$repo/pulls/$n/merge" -X PUT -f merge_method=squash --jq '.sha[0:7]' 2>&1) && { echo "$repo PR $n $out"; return 0; }
    sleep 5   # "base branch was modified": retry once
  done
  echo "merge failed for $repo PR $n: $out"; return 1
}
