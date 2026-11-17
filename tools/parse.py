import docx, sys, re, json
from docx.table import Table
from docx.text.paragraph import Paragraph

d = docx.Document(sys.argv[1])
items = []
for el in d.element.body.iterchildren():
    tag = el.tag.split('}')[1]
    if tag == 'p':
        blips = el.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
        for b in blips:
            rid = b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            items.append(('i', d.part.rels[rid].target_ref.split('/')[-1]))
        items.append(('p', Paragraph(el, d).text.strip()))
    elif tag == 'tbl':
        t = Table(el, d)
        rows = []
        for r in t.rows:
            cells = []
            prev = None
            for c in r.cells:
                cells.append(c.text.strip())
            rows.append(cells)
        items.append(('t', rows))

# TOC
toc = []
last_toc = 0
for i, (k, v) in enumerate(items):
    if k == 'p' and re.match(r'^.+\t\d+$', v):
        toc.append(v.rsplit('\t', 1)[0].strip())
        last_toc = i


def level(h):
    if re.match(r'^(第.+章|附录|摘要|证据分级说明)', h):
        return 1
    if re.match(r'^\d+\.\d+ ', h):
        return 2
    return 3


# walk body, match headings sequentially
sections = []  # flat list: {h, lvl, blocks}
pre = {'h': '封面', 'lvl': 1, 'blocks': []}
cur = pre
ti = 0
for k, v in items[last_toc + 1:]:
    if k == 'p' and ti < len(toc) and v == toc[ti]:
        cur = {'h': v, 'lvl': level(v), 'blocks': []}
        sections.append(cur)
        ti += 1
        continue
    if k == 'i':
        cur['blocks'].append({'img': v})
    elif k == 'p':
        if v:
            cur['blocks'].append({'p': v})
    else:
        cur['blocks'].append({'t': v})
assert ti == len(toc), (ti, len(toc), toc[ti] if ti < len(toc) else None)

# build tree
tree = []
for s in sections:
    if s['lvl'] == 1:
        tree.append({**s, 'children': []})
    elif s['lvl'] == 2:
        tree[-1]['children'].append({**s, 'children': []})
    else:
        par = tree[-1]['children'][-1] if tree[-1]['children'] else tree[-1]
        par['children'].append({**s, 'children': []})

json.dump({'meta': [b['p'] for b in pre['blocks'] if 'p' in b][:6], 'tree': tree},
          open(sys.argv[2], 'w'), ensure_ascii=False)
print('sections', len(sections), 'chapters', len(tree))
for c in tree:
    print(c['h'], len(c['children']))
