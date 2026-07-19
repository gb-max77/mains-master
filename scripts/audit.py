#!/usr/bin/env python3
"""Audit every written answer against its word band and H-section minimum.

    python3 scripts/audit.py            # all papers, summary
    python3 scripts/audit.py gs3 --list # per-question detail for one paper
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add import written_words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def budgets(paper):
    qs = json.load(open(os.path.join(ROOT, 'data', 'questions.json'), encoding='utf-8'))
    out = {}
    for p in qs:
        if p['id'] != paper:
            continue
        for s in p['sections']:
            for q in s['qs']:
                out[f"{paper}-{q['n']}"] = (q.get('wmin', 0), q['w'], q.get('tier'))
                for i, b in enumerate(q.get('branches', [])):
                    out[f"{paper}-{q['n']}-b{i}"] = (b.get('wmin', 0), b['w'], b.get('tier'))
    return out


def main():
    papers = [a for a in sys.argv[1:] if not a.startswith('-')] or \
             ['gs1', 'gs2', 'gs3', 'gs4', 'pubad1', 'pubad2', 'essay']
    detail = '--list' in sys.argv
    grand = {'ok': 0, 'short': 0, 'over': 0, 'thinH': 0}
    for paper in papers:
        path = os.path.join(ROOT, 'data', 'answers', f'{paper}.json')
        if not os.path.exists(path):
            continue
        bank = json.load(open(path, encoding='utf-8'))
        bud = budgets(paper)
        short, over, thinH = [], [], []
        for qid, a in bank.items():
            lo, hi, tier = bud.get(qid, (0, 0, None))
            if not hi:
                continue
            w, hs = written_words(a), len(a.get('body', []))
            if w < lo:
                short.append((qid, w, lo, tier))
            elif w > hi * 1.05:
                over.append((qid, w, hi, tier))
            if hs < 2:
                thinH.append((qid, hs, tier))
        ok = len(bank) - len(short) - len(over)
        grand['ok'] += ok; grand['short'] += len(short)
        grand['over'] += len(over); grand['thinH'] += len(thinH)
        print(f"{paper:8s} {len(bank):4d} written · {ok:4d} in band · {len(short):3d} SHORT · "
              f"{len(over):3d} over · {len(thinH):3d} single-H")
        if detail:
            for qid, w, lo, tier in sorted(short, key=lambda x: x[1] - x[2]):
                print(f"    SHORT {qid:14s} {w:4d}/{lo}w  T{tier}")
            for qid, hs, tier in thinH:
                print(f"    H{hs:<4d} {qid:14s}  T{tier}")
    print(f"\nTOTAL    in band {grand['ok']} · SHORT {grand['short']} · "
          f"over {grand['over']} · single-H {grand['thinH']}")


if __name__ == '__main__':
    main()
