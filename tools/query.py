"""Query the 医药赛道研究库 API files from the command line (for agents and colleagues).

  python3 tools/query.py 高瓴                     # full-text search across tracks, routes, companies, updates
  python3 tools/query.py --company 艾博生物         # one company as JSON
  python3 tools/query.py --route 表观遗传编辑       # one route as JSON
  python3 tools/query.py --track 小核酸             # one track (without chapter text) as JSON
  python3 tools/query.py --pos 重点跟踪             # routes with a given 定位
  python3 tools/query.py --updates 14              # update items from the last N days
  python3 tools/query.py --base http://localhost:8765 ...   # read over HTTP instead of local files
"""
import argparse, json, os, sys, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, base):
    if base:
        with urllib.request.urlopen(f'{base.rstrip("/")}/api/{name}') as r:
            return json.load(r)
    return json.load(open(os.path.join(ROOT, 'site', 'api', name)))


def flat(o):
    return json.dumps(o, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('q', nargs='?')
    ap.add_argument('--company'); ap.add_argument('--route'); ap.add_argument('--track')
    ap.add_argument('--pos'); ap.add_argument('--updates', type=int); ap.add_argument('--base')
    a = ap.parse_args()
    out = lambda o: print(json.dumps(o, ensure_ascii=False, indent=1))
    pick = lambda items, n: [x for x in items if n in x['name']]
    if a.company:
        return out(pick(load('companies.json', a.base)['items'], a.company))
    if a.route:
        return out(pick(load('routes.json', a.base)['items'], a.route))
    if a.track:
        return out([{k: v for k, v in t.items() if k != 'chapter'} for t in pick(load('tracks.json', a.base)['items'], a.track)])
    if a.pos:
        return out([{k: r[k] for k in ('rank', 'name', 'direction', 'score', 'targets')} for r in load('routes.json', a.base)['items'] if r['pos'] == a.pos])
    if a.updates is not None:
        cut = (datetime.date.today() - datetime.timedelta(days=a.updates)).isoformat()
        return out([u for u in load('updates.json', a.base)['items'] if u['date'] >= cut])
    if not a.q:
        return out(load('index.json', a.base))
    hits = []
    for name, kind in (('tracks.json', 'track'), ('routes.json', 'route'), ('companies.json', 'company')):
        for it in load(name, a.base)['items']:
            s = flat(it)
            i = s.find(a.q)
            if i >= 0:
                hits.append({'kind': kind, 'name': it['name'], 'count': s.count(a.q), 'snippet': s[max(0, i - 40): i + 60]})
    for u in load('updates.json', a.base)['items']:
        if a.q in flat(u):
            hits.append({'kind': 'update', 'name': f"{u['date']} {u['entity']} {u['title']}", 'count': 1, 'snippet': u.get('summary', '')})
    out(sorted(hits, key=lambda h: -h['count']))


if __name__ == '__main__':
    main()
