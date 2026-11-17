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
git commit -q -m "Weekly update $(date +%Y-%m-%d)"
git push -q "$REMOTE" "HEAD:$BRANCH"
echo "pushed to $REMOTE/$BRANCH"
