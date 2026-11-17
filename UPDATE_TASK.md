# 每周动态更新流程

Project folder `/Users/mikey/Workspace/LUCION Workspace/医药赛道研究库`. Run every step from that folder.

## 1. Read the current state
- `config.json`: `lookback_days`.
- `data/updates.json`: `last_run` and existing `items`. The search window runs from `last_run` (or today minus `lookback_days` when null) to today.
- `site/api/companies.json`: the 48 company names.
- `site/api/routes.json`: each route's `targets`. Targets that are not among the 48 companies are also watched (skip entries such as 国内暂无检索到合适标的 and 暂不建议布局).

## 2. Search
For each watched entity, search the web for events dated inside the window. Group several entities per query where that keeps results clear. Record only these event types:
- 融资 (new rounds, IPO filings and listings, placements)
- BD 与授权 (out-licensing, NewCo, M&A, option exercises, deal terminations)
- 临床 (first patient dosed, data readouts, IND/NDA/BLA acceptance or approval, trial holds)
- 监管与政策 (export control, BIOSECURE, outbound investment rules, NMPA/FDA guidance that names the track)
- 团队 (founder, CEO or CSO changes)

Track-level policy events use `entity_type: "track"` with the exact track name from `api/tracks.json`.

## 3. Verify before writing
- Each item needs a source URL you opened, and the event date must fall inside the window. Use the human-readable page URL, never an API or JSON endpoint.
- Evidence grade: A for regulators, exchange filings and peer-reviewed papers; B for company announcements and authoritative media; C for trade media and databases. Never record D-level material such as company self-reported claims without a disclosure.
- Skip duplicates: an existing item with the same `source_url`, or the same entity and event.
- If the company name matches a different company, skip it.

## 4. Write items to `data/updates.json`
```json
{"id":"2026-11-24-艾博生物-诺华交易交割","date":"2026-11-24","found_at":"2026-11-24","type":"BD 与授权",
 "entity_type":"company","entity":"艾博生物","title":"与诺华的 mRNA 编码 TCE 授权交易完成交割",
 "summary":"首付款 5.75 亿美元到账，交割条件包括监管审批。","source_name":"公司公告","source_url":"https://...","evidence":"B"}
```
Language rules for `title` and `summary`: Chinese, plain research style, no colons or dashes, ranges written with 至, a half-width space between Chinese and Latin letters or digits, clinical phases in Roman numerals (I 期, II 期), keep every amount, date, target and company name, and no marketing words.

Append the new items, set `last_run` to today's date (YYYY-MM-DD) even when nothing new was found, and keep the file valid JSON.

## 4b. Update pipelines
For every new 临床 or BD 与授权 item about a company, also update that company's entry in `data/pipelines.json`. Move an asset's `stage` when the event proves it (allowed values are 临床前, IND, 临床, I 期, II 期, III 期, 申报上市, 已上市, 未披露), add a new asset when one is disclosed, update `partner` after a licensing deal, and put the event in `stage_note`. Set `source` to `动态 YYYY-MM-DD` for anything you change. Never lower a stage without a source that says so, and never edit rows marked `"source": "报告"` except to advance them.

## 5. Rebuild and deploy
Run `./tools/deploy.sh`. It rebuilds the site (validating update items and skipping any that lack required fields), then commits `site/`, `data/` and `config.json` and pushes to the GitHub remote, which redeploys GitHub Pages. If it prints `skip invalid update item`, fix the item and run it again. If it prints that there is no git remote, the site was rebuilt locally only; say so in the report.

## 6. Report
Finish with a short summary: the window searched, the number of new items by type, one line per new item (date, entity, title), anything you could not verify, and whether the push to GitHub succeeded. Never edit `source/report.docx`, never push anything except through `tools/deploy.sh`, and never edit the report text or any score.
