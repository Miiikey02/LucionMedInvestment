import json, sys, re

T = json.load(open(sys.argv[1]))['tree']


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n['children'])


def find(prefix):
    for n in walk(T):
        if n['h'].startswith(prefix):
            return n
    raise KeyError(prefix)


def tables(n):
    return [b['t'] for b in n['blocks'] if 't' in b]


# ---- tracks
dims_t = tables(find('3.1'))[0]
dims = [{'name': r[0], 'w': int(r[1].rstrip('%')), 'meaning': r[2], 'hi': r[3], 'lo': r[4]} for r in dims_t[1:]]
score_t = tables(find('3.2'))[0]
top_t = tables(find('1.2'))[0]
top = {r[1]: {'logic': r[3], 'action': r[4]} for r in top_t[1:]}
reason_t = tables(find('附录 A'))[0]
reason = {r[0]: {'plus': r[1], 'minus': r[2]} for r in reason_t[1:]}
chapters = {re.sub(r'^第.+?章 ', '', c['h']): i for i, c in enumerate(T)}
tracks = []
for i, r in enumerate(score_t[1:]):
    name = r[0]
    t = {'rank': i + 1, 'name': name, 'scores': [int(x) for x in r[1:8]], 'base': float(r[8]),
         'ch': chapters.get(name), **top.get(name, {}), **reason.get(name, {})}
    tracks.append(t)

# ---- companies
companies = []
for tr in tracks:
    ch = T[tr['ch']]
    secs = ch['children']
    prof = tables(secs[2])[0]
    team = tables(secs[3])[0] if tables(secs[3]) else []
    teamd = {r[0]: r[1:] for r in team[1:]}
    analysis = {s['h']: s['blocks'] for s in secs[4]['children']}
    for r in prof[1:]:
        nm = r[0]
        key = re.split(r'[（(]', nm)[0].strip()
        an = None
        for h, b in analysis.items():
            if h == nm or h.startswith(key) or key.startswith(re.split(r'[（(]', h)[0].strip()):
                an = (h, b)
                break
        tm = teamd.get(nm) or next((v for k, v in teamd.items() if k.startswith(key)), None)
        companies.append({'name': nm, 'track': tr['name'], 'tech': r[1], 'fund': r[2], 'bd': r[3], 'model': r[4],
                          'team': tm[0] if tm else '', 'investors': tm[1] if tm else '', 'teamEval': tm[2] if tm else '',
                          'analysis': an[1] if an else None})

# ---- routes
rank_t = tables(find('20.3'))[0]
scen_t = tables(find('20.4'))[0]
scen = {r[0]: [float(x) for x in r[1:]] for r in scen_t[1:]}
rdims = [{'name': r[0], 'w': int(r[1].rstrip('%')), 'meaning': r[2]} for r in tables(find('20.2'))[0][1:]]
targets, detail, group = {}, {}, {}
for prefix in ('第二十一章', '第二十二章'):
    ch = find(prefix)
    for g in ch['children']:
        for t in tables(g):
            if t[0][0] == '技术路线':
                for r in t[1:]:
                    targets[r[0]] = r[4]
        for s in g['children']:
            detail[s['h']] = s['blocks']
            group[s['h']] = g['h']
routes = []
for r in rank_t[1:]:
    nm = r[1]
    routes.append({'rank': int(r[0]), 'name': nm, 'dir': r[2], 'score': float(r[3]), 'pos': r[4],
                   'targets': targets.get(nm, ''), 'scen': scen.get(nm), 'group': group.get(nm, ''),
                   'detail': detail.get(nm)})
missing = [x['name'] for x in routes if not x['detail']]
print('routes', len(routes), 'no detail:', missing)
print('companies', len(companies), 'no analysis:', [c['name'] for c in companies if not c['analysis']],
      'no team:', [c['name'] for c in companies if not c['team']])

out = {'dims': dims, 'tracks': tracks, 'companies': companies, 'routes': routes, 'rdims': rdims,
       'tree': [{'h': c['h'], 'blocks': c['blocks'], 'children': c['children']} for c in T]}
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
