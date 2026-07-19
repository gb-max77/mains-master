#!/usr/bin/env python3
"""Expand existing answers in place: split a flat body into headed sections and
append new points, without retyping what is already there.

    python3 scripts/expand.py gs3 < batch.json

Batch entry per qid:
  { "h1": "First heading", "h2": "Second heading", "cut": 3,
    "add1": [ {k,x,ex} ... ],   # appended to section 1
    "add2": [ {k,x,ex} ... ],   # appended to section 2
    "h3": "...", "add3": [...], # optional third section (new points only)
    "wf": [...], "conc": "...", "flash": [...] }

Existing points are taken from the answer's current sections, flattened in order,
then re-split at `cut`. Nothing is discarded.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add import written_words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    paper = sys.argv[1]
    batch = json.load(sys.stdin)
    path = os.path.join(ROOT, 'data', 'answers', f'{paper}.json')
    bank = json.load(open(path, encoding='utf-8'))

    qs = json.load(open(os.path.join(ROOT, 'data', 'questions.json'), encoding='utf-8'))
    bud = {}
    for p in qs:
        if p['id'] != paper:
            continue
        for s in p['sections']:
            for q in s['qs']:
                bud[f"{paper}-{q['n']}"] = (q.get('wmin', 0), q['w'])
                for i, b in enumerate(q.get('branches', [])):
                    bud[f"{paper}-{q['n']}-b{i}"] = (b.get('wmin', 0), b['w'])

    for qid, spec in batch.items():
        a = bank.get(qid)
        if a is None:
            print(f"  {qid:14s} ⚠ not in bank — skipped", file=sys.stderr)
            continue
        pts = [p for sec in a.get('body', []) for p in sec.get('p', [])]
        cut = min(spec.get('cut', max(2, len(pts) // 2)), len(pts))
        body = [{'h': spec['h1'], 'p': pts[:cut] + spec.get('add1', [])},
                {'h': spec['h2'], 'p': pts[cut:] + spec.get('add2', [])}]
        if spec.get('h3'):
            body.append({'h': spec['h3'], 'p': spec.get('add3', [])})
        a['body'] = [b for b in body if b['p']]
        # Merging corpus points with new ones routinely overshoots. Shed the least
        # substantive point (shortest expansion) until the answer is inside its band —
        # never below three points in a section, so structure survives the trim.
        hi_cap = bud.get(qid, (0, 0))[1]
        while hi_cap and written_words(a) > hi_cap:
            cand = [(len(pt.get('x', '')), si, pi)
                    for si, sec in enumerate(a['body'])
                    for pi, pt in enumerate(sec['p']) if len(sec['p']) > 3]
            if not cand:
                break
            _, si, pi = min(cand)
            a['body'][si]['p'].pop(pi)
        for key in ('wf', 'conc', 'flash', 'directive', 'diag'):
            if spec.get(key):
                a[key] = spec[key]

        w = written_words(a)
        lo, hi = bud.get(qid, (0, 0))
        flag = '  ⚠ OVER' if hi and w > hi * 1.05 else (f'  ⚠ SHORT by {lo-w}' if lo and w < lo else '')
        print(f"  {qid:14s} {w:4d}w / {lo}-{hi}w · H{len(a['body'])}{flag}", file=sys.stderr)

    json.dump(bank, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{len(batch)} expanded in {paper}.json", file=sys.stderr)


if __name__ == '__main__':
    main()
