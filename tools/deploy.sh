#!/bin/zsh
# Rebuild the site, then commit and push so GitHub Pages redeploys.
# Does nothing beyond the rebuild when the folder is not a git repo or has no remote yet.
set -e
cd "$(dirname "$0")/.."
./tools/rebuild.sh
if [ ! -d .git ]; then echo "not a git repo: skipped push"; exit 0; fi
REMOTE=$(python3 -c "import json;print(json.load(open('config.json')).get('deploy',{}).get('remote','origin'))")
BRANCH=$(python3 -c "import json;print(json.load(open('config.json')).get('deploy',{}).get('branch','main'))")
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then echo "no git remote '$REMOTE': skipped push"; exit 0; fi
git add site data config.json
if git diff --cached --quiet; then echo "nothing changed: skipped push"; exit 0; fi
git commit -q -m "Weekly update $(date +%Y-%m-%d)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
# never wait for a password prompt in an unattended run: fail fast if the stored token is missing or expired
if ! GIT_TERMINAL_PROMPT=0 git push -q "$REMOTE" "HEAD:$BRANCH"; then
  echo "PUSH FAILED: the GitHub token in the keychain is missing or expired. The commit is saved locally; renew the token and run: git push $REMOTE $BRANCH"
  exit 2
fi
echo "pushed to $REMOTE/$BRANCH; GitHub Pages redeploys in 1 to 2 minutes"
