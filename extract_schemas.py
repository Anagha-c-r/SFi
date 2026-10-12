"""Extract dataset schemas from CBK GDI User Guide (pages.json from pdfplumber)."""
import json, re, sys, difflib
pages = json.load(open(sys.argv[1]))
outdir = sys.argv[2]

# locate section starts
starts = []
for p in pages:
    for l in p['text'].split('\n'):
        m = re.match(r'^\s*(\d{1,2})\.\s+([A-Z][^.]*?.*)$', l)
        if m and 2 <= int(m.group(1)) <= 47 and p['page'] >= 19 and 'SFI can' not in l:
            n = int(m.group(1))
            if not any(s[0] == n for s in starts) and (not starts or n == starts[-1][0] + 1):
                starts.append((n, m.group(2).strip(), p['page']))
by_page = {p['page']: p for p in pages}
last_page = 234

def clean(s): return re.sub(r'\s+', ' ', (s or '').replace('\n', ' ')).strip()

def slugify(s): return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

TYPE_MAP = {'number': 'number', 'date': 'date', 'string': 'string', 'decimal': 'number', 'integer': 'number'}

results = []
for idx, (n, title, pg) in enumerate(starts):
    end = starts[idx + 1][2] if idx + 1 < len(starts) else last_page
    secpages = [by_page[x] for x in range(pg, end + 1) if x in by_page]
    text = '\n'.join(sp['text'] for sp in secpages)
    # restrict text to this section
    st = text.find(f'{n}.')
    nxt = text.find(f'\n{n+1}.', st + 1) if n < 47 else -1
    stext = text[st: nxt if nxt > 0 else None]
    # endpoint
    m = re.search(r'(https://gdi\.centralbank\.go\.ke/preprod/api[^\s]*(?:\n[^\s\n]+)?)', stext)
    url = m.group(1).replace('\n', '') if m else None
    if url and not re.search(r'/submit\w+$', url):
        m2 = re.search(r'https://gdi\.centralbank\.go\.ke/preprod/api[\s\S]{0,200}?(submit\w+)', stext)
        if m2: url = re.sub(r'(1\.0/).*$', r'\1', url) + m2.group(1)
    path = re.sub(r'^https://gdi\.centralbank\.go\.ke/preprod', '', url or '').replace('rest//', 'rest/')
    # tables
    tables = []
    for sp in secpages:
        tables += sp['tables']
    array_key, fields = None, []
    in_section = False
    for t in tables:
        if not t or not t[0]: continue
        h = clean(t[0][0]).upper()
        if h.startswith('INPUT PARAMET'):
            for r in t[1:]:
                if r and len(r) >= 2 and r[1] and '[' in (r[1] or ''):
                    array_key = clean(r[0]).replace(' ', '')
        if h == 'ELEMENT':
            for r in t[1:]:
                r = [clean(c) for c in r] + [''] * 4
                if not r[0]: 
                    # continuation row
                    if fields and r[2]: fields[-1]['description'] += ' ' + r[2]
                    continue
                if fields and not fields[-1]['type'] and not fields[-1]['description']:
                    fields[-1]['name'] += ' ' + r[0]; fields[-1].update(type=r[1], description=r[2], example=r[3]); continue
                fields.append({'name': r[0], 'type': r[1], 'description': r[2], 'example': r[3]})
    # stop if we pulled next section's fields: cut fields after a duplicate 'ROW ID'
    rid = [i for i, f in enumerate(fields) if f['name'].upper().replace('_',' ') in ('ROW ID', 'ROWID')]
    if len(rid) > 1: fields = fields[:rid[1]]
    # sample keys
    sample_start = stext.find('Sample & Business')
    sample = stext[sample_start:] if sample_start >= 0 else stext
    sample_keys = []
    for k in re.findall(r'"([^"]+)"\s*:', sample):
        if k not in sample_keys: sample_keys.append(k)
    envelope = {'INSTITUTION_CODE', 'REQUEST_ID', 'IS_ATTACHED', 'REPORTING_DATE'}
    item_keys = [k for k in sample_keys if k not in envelope and k != array_key]
    m_arr = re.search(r'"([^"]+)"\s*:\s*\[', sample)
    if m_arr:
        array_key = m_arr.group(1)
        item_keys = [k for k in sample_keys if k not in envelope and k != array_key]
    if not array_key:
        cands = [k for k in sample_keys if k not in envelope]
        array_key = cands[0] if cands else None
        item_keys = cands[1:]
    # match field -> payload key
    used = set()
    def norm(s): return re.sub(r'[^A-Z0-9]', '', s.upper())
    def toks(s): return [t for t in re.split(r'[^A-Z0-9]+', s.upper()) if t]
    def tokscore(a, b):
        ta, tb = toks(a), toks(b)
        if not ta or not tb: return 0
        hit = sum(1 for x in tb if any(y.startswith(x[:3]) or x.startswith(y[:3]) for y in ta))
        return hit / max(len(ta), len(tb))
    def score(a, b):
        return max(difflib.SequenceMatcher(None, norm(a), norm(b)).ratio(), tokscore(a, b))
    pairs = sorted(((score(f['name'], k), i, k) for i, f in enumerate(fields) for k in item_keys), reverse=True)
    assigned = {}
    for sc, i, k in pairs:
        if sc < 0.55 or i in assigned or k in used: continue
        assigned[i] = (k, sc); used.add(k)
    for i, f in enumerate(fields):
        if i in assigned:
            f['payload_key'], sc = assigned[i]; f['key_confidence'] = round(sc, 2)
        else:
            f['payload_key'] = f['name']; f['key_confidence'] = 0
        t = f['type'].lower()
        f['type'] = next((v for k2, v in TYPE_MAP.items() if k2 in t), 'string')
        f['key'] = slugify(f['name'])[:60]
    results.append({
        'number': n, 'code': slugify(title)[:50], 'title': title, 'endpoint': path,
        'array_key': array_key, 'fields': fields,
        'unmatched_sample_keys': [k for k in item_keys if k not in used],
        'source_pages': [pg, end],
    })

import os
os.makedirs(outdir, exist_ok=True)
for r in results:
    json.dump(r, open(f"{outdir}/{r['number']:02d}_{r['code']}.json", 'w'), indent=2)
print(len(results))
for r in results:
    print(r['number'], r['title'][:40], '|', r['array_key'], '|', len(r['fields']), 'fields |', r['endpoint'][-45:], '| unmatched', len(r['unmatched_sample_keys']), '| low', sum(1 for f in r['fields'] if f['key_confidence'] < 0.85))
