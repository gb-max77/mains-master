#!/usr/bin/env python3
"""Import the MainsLab prepared-answer corpus into the reader schema.

    python3 scripts/import-mainslab.py pubad1 pubad2

Two hard rules, both about not shipping a wrong answer:

1. **Never overwrite a hand-written answer.** Existing entries are kept; the
   corpus only fills gaps.
2. **Quarantine duplicated bodies.** 132 of 288 PubAd entries share an identical
   prepared answer with another entry, and 21 of those groups span *different*
   master questions — the same text pasted under unrelated stems. We import a
   duplicated body for only ONE question (the lowest id in its group, flagged for
   verification) and skip the rest, leaving them unwritten.

The corpus authors' own word modes sit below this app's bands (PubAd 15m is
authored at 200w against a 250-280 band), so imports land short by design and
are expanded afterwards with expand.py.
"""
import hashlib, json, os, re, sys

SRC = "/Users/gbs/Downloads/MainsLab_2026_Complete_Prepared_Answers.md"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER_OF = {'gs1': 'f26-gs1', 'gs2': 'f26-gs2', 'gs3': 'f26-gs3',
            'pubad1': 'f26-pa1', 'pubad2': 'f26-pa2'}

BULLET = re.compile(r'^\s*-\s+\*\*(.+?)\*\*\s*(?:_\[(.*?)\]_)?\s*:?\s*(.*)$')
HEAD = re.compile(r'^####\s+(.+?)\s*$')
NORM = lambda s: re.sub(r'\W+', '', (s or '')).lower()


def blocks():
    txt = open(SRC, encoding='utf-8').read()
    for bid, b in re.findall(r'<!-- ANSWER_START id="([^"]+)" -->(.*?)<!-- ANSWER_END', txt, re.S):
        yield bid, b


def field(b, name):
    m = re.search(rf'\|\s*{name}\s*\|\s*([^|]+)\|', b)
    return m.group(1).strip() if m else None


def parse_answer(b):
    """→ (intro, [ {h,p:[...]} ], conc). 'Study buffer — trim first' is dropped:
    the corpus marks it as optional enrichment, not exam core."""
    seg = re.search(r'### Prepared answer(.*?)(?:### Keywords|### Sources|$)', b, re.S)
    if not seg:
        return None, [], None
    intro, conc, sections, cur = None, None, [], None
    for line in seg.group(1).split('\n'):
        h = HEAD.match(line)
        if h:
            name = h.group(1).strip()
            low = name.lower()
            if low.startswith('introduction'):
                cur = 'intro'
            elif low.startswith('conclusion'):
                cur = 'conc'
            elif 'study buffer' in low:
                cur = 'skip'
            else:
                cur = {'h': name, 'p': []}
                sections.append(cur)
            continue
        if cur == 'skip' or not line.strip():
            continue
        if cur == 'intro' and not line.startswith('-'):
            intro = (intro + ' ' + line.strip()).strip() if intro else line.strip()
        elif cur == 'conc' and not line.startswith('-'):
            conc = (conc + ' ' + line.strip()).strip() if conc else line.strip()
        elif isinstance(cur, dict):
            m = BULLET.match(line)
            if m:
                tag = (m.group(2) or '').lower()
                if 'study buffer' in tag:          # inline buffer bullets go too
                    continue
                cur['p'].append({'k': m.group(1).strip(), 'x': m.group(3).strip()})
    return intro, [s for s in sections if s['p']], conc


def main():
    papers = sys.argv[1:] or ['pubad1', 'pubad2']
    qs = json.load(open(os.path.join(ROOT, 'data', 'questions.json'), encoding='utf-8'))

    # group identical bodies so we can keep at most one question per body
    body_of, groups = {}, {}
    for bid, b in blocks():
        seg = re.search(r'### Prepared answer(.*?)(?:### Keywords|### Sources|$)', b, re.S)
        if not seg:
            continue
        h = hashlib.md5(re.sub(r'\s+', '', seg.group(1)).encode()).hexdigest()
        body_of[bid] = h
        groups.setdefault(h, []).append(bid)
    keeper = {ids[0] for ids in groups.values()}      # lowest id wins its body
    shared = {h for h, ids in groups.items() if len(ids) > 1}

    for paper in papers:
        prefix = PAPER_OF[paper]
        P = [p for p in qs if p['id'] == paper][0]
        # index our questions by normalised text, master and branch alike
        idx = {}
        for s in P['sections']:
            for q in s['qs']:
                idx[NORM(q['q'])] = f"{paper}-{q['n']}"
                for i, br in enumerate(q.get('branches', [])):
                    idx[NORM(br['q'])] = f"{paper}-{q['n']}-b{i}"

        path = os.path.join(ROOT, 'data', 'answers', f'{paper}.json')
        bank = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
        kept_hand = set(bank)

        added = skipped_dup = skipped_kept = unmatched = 0
        for bid, b in blocks():
            if not bid.startswith(prefix):
                continue
            qtext = re.search(r'### Question\s*\n+(.+?)\n', b)
            if not qtext:
                continue
            qid = idx.get(NORM(qtext.group(1)))
            if not qid:
                unmatched += 1
                continue
            if qid in kept_hand:
                skipped_kept += 1
                continue
            if bid not in keeper:
                skipped_dup += 1                      # its body belongs to another question
                continue
            intro, body, conc = parse_answer(b)
            if not body:
                continue
            a = {'src': 'mainslab'}
            if intro:
                a['intro'] = [{'t': 'concept', 'x': intro}]
            a['body'] = body
            if conc:
                a['conc'] = conc
            d = field(b, 'Directive')
            if d:
                a['directive'] = d.lower()
            kw = re.search(r'### Keywords(.*?)(?:### Sources|$)', b, re.S)
            if kw:
                flash = [l.strip('- ').strip() for l in kw.group(1).split('\n') if l.strip().startswith('-')]
                a['flash'] = [f for f in flash if len(f) > 3][:6]
            if body_of.get(bid) in shared:
                a['lens'] = ('⚠ This prepared answer shares its body with other questions in the source '
                             'corpus — verify it answers this stem before relying on it.')
            bank[qid] = a
            added += 1

        json.dump(bank, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"  {paper}: +{added} imported · {skipped_kept} hand-written kept · "
              f"{skipped_dup} skipped (body belongs to another question) · {unmatched} unmatched "
              f"→ {len(bank)} total", file=sys.stderr)


if __name__ == '__main__':
    main()
