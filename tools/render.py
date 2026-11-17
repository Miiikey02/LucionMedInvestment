"""Render site/index.html and site/api/*.json from build/data.json + data/updates.json.

Usage: python3 tools/render.py   (run from the project root, or via tools/rebuild.sh)
"""
import json, os, datetime, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

data = json.load(open(P('build', 'data.json')))
upd_path = P('data', 'updates.json')
updates = json.load(open(upd_path)) if os.path.exists(upd_path) else {'last_run': None, 'items': []}

# validate updates so a bad weekly run can't break the page
REQ = ('id', 'date', 'type', 'entity_type', 'entity', 'title', 'source_url')
good = []
for u in updates.get('items', []):
    if all(u.get(k) for k in REQ) and re.match(r'^\d{4}-\d{2}-\d{2}$', u['date']) \
            and u['entity_type'] in ('company', 'route', 'track'):
        good.append(u)
    else:
        print('skip invalid update item:', u.get('id'))
updates['items'] = sorted(good, key=lambda u: u['date'], reverse=True)

now = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
data['meta'] = {'generated_at': now, 'report_as_of': '2026-11-17'}
data['updates'] = updates

# pipelines: data/pipelines.json keyed by company name
pp = P('data', 'pipelines.json')
pipes = json.load(open(pp))['companies'] if os.path.exists(pp) else {}
for c in data['companies']:
    c['pipeline'] = pipes.get(c['name'], {'items': []})

# site settings the page needs at runtime (no secrets: keys live only in the AI gateway)
cfg = json.load(open(P('config.json')))
data['config'] = {'ai_gateway_url': cfg.get('ai_gateway_url', '')}

# ---- page
tpl = open(P('tools', 'template.html')).read()
blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
page = tpl.replace('__DATA__', blob)
os.makedirs(P('build'), exist_ok=True)
# site/index.html is a complete static page: GitHub Pages or any web host can serve the site/ folder as is.
open(P('site', 'index.html'), 'w').write(
    '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
    'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
    + page + '</body></html>')

# ---- api
os.makedirs(P('site', 'api'), exist_ok=True)
T = data['tree']
SCEN = {'基准': [30, 15, 15, 10, 10, 10, 10], '等权': [1, 1, 1, 1, 1, 1, 1],
        '前瞻性加重': [40, 12, 12, 9, 9, 9, 9], '地缘压力': [30, 15, 5, 10, 20, 10, 10]}


def text(blocks):
    out = []
    for b in blocks or []:
        if 'p' in b:
            out.append(b['p'])
        elif 't' in b:
            out.append('\n'.join(' | '.join(r) for r in b['t']))
    return out


def node(n):
    return {'heading': n['h'], 'paragraphs': text(n['blocks']), 'children': [node(c) for c in n['children']]}


def ups_for(kind, name):
    k = name.split('（')[0].split('(')[0].strip()
    return [u['id'] for u in updates['items'] if u['entity_type'] == kind and u['entity'].split('（')[0].split('(')[0].strip() == k]


route_track = {}
for i, r in enumerate(data['routes']):
    if r['group'].startswith('21.'):
        first = re.sub(r'与.*$', '', re.sub(r'^[\d.]+\s*', '', r['group']).split(' ')[0])
        for t in data['tracks']:
            if t['name'].startswith(first):
                route_track[i] = t['name']

tracks = [{
    'id': i, 'rank': t['rank'], 'name': t['name'], 'base_score': t['base'],
    'dimension_scores': dict(zip([d['name'] for d in data['dims']], t['scores'])),
    'scenario_scores': {k: round(sum(s * w for s, w in zip(t['scores'], v)) / sum(v), 2) for k, v in SCEN.items()},
    'core_logic': t.get('logic'), 'suggested_action': t.get('action'),
    'plus': t.get('plus'), 'minus': t.get('minus'),
    'companies': [c['name'] for c in data['companies'] if c['track'] == t['name']],
    'routes': [r['name'] for j, r in enumerate(data['routes']) if route_track.get(j) == t['name']],
    'chapter': node(T[t['ch']]), 'update_ids': ups_for('track', t['name']),
} for i, t in enumerate(data['tracks'])]

routes = [{
    'id': i, 'rank': r['rank'], 'name': r['name'], 'direction': r['dir'], 'group': r['group'],
    'track': route_track.get(i), 'score': r['score'], 'pos': r['pos'],
    'scenario_scores': dict(zip(['基准', '等权', '前瞻性加重', '证据优先'], r['scen'])) if r['scen'] else None,
    'targets': [s.strip() for s in r['targets'].split('、') if s.strip()],
    'analysis': text(r['detail']), 'update_ids': ups_for('route', r['name']),
} for i, r in enumerate(data['routes'])]

companies = [{
    'id': i, 'name': c['name'], 'track': c['track'], 'tech_and_assets': c['tech'], 'financing': c['fund'],
    'bd_and_licensing': c['bd'], 'business_model': c['model'], 'core_team': c['team'],
    'investors': c['investors'], 'team_assessment': c['teamEval'], 'analysis': text(c['analysis']),
    'update_ids': ups_for('company', c['name']),
    'pipeline': c['pipeline'],
} for i, c in enumerate(data['companies'])]

scoring = {
    'track_dimensions': data['dims'], 'track_scenarios': SCEN,
    'route_dimensions': data['rdims'],
    'route_scenarios': {'基准': [30, 15, 15, 15, 10, 10, 5], '等权': [14] * 7,
                        '前瞻性加重': [40, 12, 12, 13, 8, 10, 5], '证据优先': [15, 25, 25, 13, 10, 7, 5]},
    'note': '赛道七维 1 至 5 分，加权得分为各维得分乘权重之和除以权重合计。路线仅公布基准得分与前 20 条的情景得分。',
}

meta = {
    'name': '医药赛道研究库', 'source': '医药全产业链细分赛道筛选与头部企业研究报告（撰写人杨诚）',
    'report_as_of': '2026-11-17', 'generated_at': now, 'updates_last_run': updates.get('last_run'),
    'counts': {'tracks': len(tracks), 'routes': len(routes), 'companies': len(companies), 'updates': len(updates['items'])},
    'conventions': {'推断': '报告作者的推论', '证据等级': 'A 监管与法定披露、同行评审；B 公司公告与权威媒体；C 行业媒体与数据库；D 企业自述'},
    'endpoints': {
        'api/tracks.json': '16 个赛道', 'api/routes.json': '64 条技术路线', 'api/companies.json': '48 家企业',
        'api/updates.json': '报告后跟踪动态（每周）', 'api/scoring.json': '打分维度与情景权重',
        'api/report.json': '报告全文章节树'},
    'disclaimer': '不构成任何投资建议。动态不改变报告打分。',
}


def dump(name, obj):
    json.dump(obj, open(P('site', 'api', name), 'w'), ensure_ascii=False, indent=1)


dump('index.json', meta)
dump('tracks.json', {'meta': {'report_as_of': '2026-11-17', 'generated_at': now}, 'items': tracks})
dump('routes.json', {'meta': {'report_as_of': '2026-11-17', 'generated_at': now}, 'items': routes})
dump('companies.json', {'meta': {'report_as_of': '2026-11-17', 'generated_at': now}, 'items': companies})
dump('updates.json', updates)
dump('scoring.json', scoring)
dump('report.json', {'meta': {'report_as_of': '2026-11-17'}, 'chapters': [node(n) for n in T]})
print(f'rendered site/index.html and site/api/* · {len(updates["items"])} updates · {now}')
