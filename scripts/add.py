#!/usr/bin/env python3
"""Merge a batch of answers into data/answers/<paper>.json.

    python3 scripts/add.py gs1 < batch.json

Batch is a JSON object keyed by qid. Existing keys are overwritten, so a batch
can also be used to revise an answer already in the bank. Prints a word-count
audit against each question's budget — over-budget answers can't be written in
the exam, so they get flagged loudly rather than silently shipped.
"""
import json, re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def written_words(a):
    """Count the words you'd actually put on paper: ONE intro + points + wf + conclusion."""
    parts = []
    if a.get('intro'):
        parts.append(a['intro'][0]['x'])
    for b in a.get('body', []):
        parts.append(b.get('h', ''))
        for p in b.get('p', []):
            parts += [p.get('k', ''), p.get('x', ''), p.get('ex', '')]
    parts += a.get('wf', [])
    parts.append(a.get('conc', ''))
    text = ' '.join(parts)
    text = re.sub(r'\*\*|[•·—–]', ' ', text)
    return len(text.split())


def main():
    paper = sys.argv[1]
    batch = json.load(sys.stdin)
    path = os.path.join(ROOT, 'data', 'answers', f'{paper}.json')
    bank = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}

    qs = json.load(open(os.path.join(ROOT, 'data', 'questions.json'), encoding='utf-8'))
    budget = {}
    for p in qs:
        if p['id'] != paper:
            continue
        for s in p['sections']:
            for q in s['qs']:
                budget[f"{paper}-{q['n']}"] = q['w']
                for i, b in enumerate(q.get('branches', [])):
                    budget[f"{paper}-{q['n']}-b{i}"] = b['w']

    for qid, a in batch.items():
        bank[qid] = a
        w, lim = written_words(a), budget.get(qid, 0)
        flag = '  ⚠ OVER' if lim and w > lim * 1.12 else ('  ⚠ thin' if lim and w < lim * 0.75 else '')
        print(f"  {qid:14s} {w:4d}w / {lim}w{flag}", file=sys.stderr)

    json.dump(bank, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{len(batch)} merged → {paper}.json now holds {len(bank)}", file=sys.stderr)


if __name__ == '__main__':
    main()
