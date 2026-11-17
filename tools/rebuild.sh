#!/bin/zsh
# Rebuild the site and API from source/report.docx + data/updates.json.
set -e
cd "$(dirname "$0")/.."
mkdir -p build
python3 -I tools/parse.py source/report.docx build/tree.json > /dev/null
python3 -I tools/build.py build/tree.json build/data.json > /dev/null
python3 -I tools/render.py
