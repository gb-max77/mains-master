#!/usr/bin/env python3
"""Append points to existing answers to close a word shortfall.

    python3 scripts/topup.py pubad2 < batch.json

Batch: { "<qid>": [ {k,x,ex?}, ... ] }  — points are distributed across the
answer's existing sections, back-filling the shortest section first so the
structure stays balanced. Existing content is never touched.

Use this when an answer is already correctly structured and simply runs short;
use expand.py when the body needs re-sectioning, and add.py for a new answer.
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

    for qid, pts in batch.items():
        a = bank.get(qid)
        if a is None or not a.get('body'):
            print(f"  {qid:14s} ⚠ missing or bodiless — skipped", file=sys.stderr)
            continue
        for pt in pts:
            target = min(a['body'], key=lambda s: len(s['p']))   # keep sections even
            target['p'].append(pt)
        w = written_words(a)
        lo, hi = bud.get(qid, (0, 0))
        flag = '  ⚠ OVER' if hi and w > hi * 1.05 else (f'  ⚠ SHORT by {lo-w}' if lo and w < lo else '')
        print(f"  {qid:14s} {w:4d}w / {lo}-{hi}w{flag}", file=sys.stderr)

    json.dump(bank, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{len(batch)} topped up in {paper}.json", file=sys.stderr)


if __name__ == '__main__':
    main()
