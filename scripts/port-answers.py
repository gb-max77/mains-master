#!/usr/bin/env python3
"""Port answers from the upsc-mains-companion bank into Mains Master's reader schema.

Old point:  {"x": "**Head:** expansion", "va": "Sarnath capital", "vt": "case", "vf": "n"}
New point:  {"k": "Head", "x": "expansion", "ex": "Sarnath capital"}

The split is on the leading bold span (the screenshot's bold point-head); anything
that has no bold lead-in stays as a headless point (x only), which the reader
renders as a plain bullet.
"""
import json, os, re, sys

SRC_DIR = "/Users/gbs/Documents/upsc-mains-companion/data/answers"
DEST_DIR = "/Users/gbs/Documents/mains-master/data/answers"

HEAD_RE = re.compile(r'^\*\*(.+?)\*\*[:\s—-]*\s*(.*)$', re.S)
EX_RE = re.compile(r'\s*(?:Ex|E\.g|For instance)[.:]\s*(.+?)\s*$', re.I | re.S)


def port_point(p):
    raw = (p.get('x') or '').strip()
    out = {}
    m = HEAD_RE.match(raw)
    if m:
        out['k'] = m.group(1).strip().rstrip(':')
        rest = m.group(2).strip()
    else:
        rest = raw
    # pull a trailing "Ex: …" out of the expansion if present
    ex = None
    em = EX_RE.search(rest)
    if em:
        ex = em.group(1).strip()
        rest = rest[:em.start()].strip().rstrip(';').rstrip('.')
    out['x'] = rest
    ex = ex or (p.get('va') or '').strip() or None
    if ex:
        out['ex'] = ex
    if p.get('vf') == 'u':
        out['unv'] = True
    return out


def port(ans):
    out = {}
    for key in ('directive', 'lens', 'conc', 'diag', 'flash', 'wf', 'mne'):
        if ans.get(key):
            out[key] = ans[key]
    if ans.get('intro'):
        out['intro'] = [{'t': i.get('t', 'concept'), 'x': i['x']} for i in ans['intro'] if i.get('x')]
    if ans.get('body'):
        out['body'] = [
            {'h': b.get('h', ''), 'p': [port_point(p) for p in b.get('p', []) if p.get('x')]}
            for b in ans['body']
        ]
    out['src'] = 'ported'
    return out


def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    total = 0
    for name in ('gs1', 'pubad1', 'pubad2'):
        src = os.path.join(SRC_DIR, f'{name}.json')
        if not os.path.exists(src):
            continue
        data = json.load(open(src, encoding='utf-8'))
        ported = {qid: port(a) for qid, a in data.items()}
        dest = os.path.join(DEST_DIR, f'{name}.json')
        json.dump(ported, open(dest, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"  {name:8s} {len(ported):3d} answers → {dest}", file=sys.stderr)
        total += len(ported)
    print(f"TOTAL {total} ported", file=sys.stderr)


if __name__ == '__main__':
    main()
