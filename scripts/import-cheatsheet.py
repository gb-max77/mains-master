#!/usr/bin/env python3
"""Parse the ENRICHED PubAd cheat sheets into the reader schema.

    python3 scripts/import-cheatsheet.py pubad1 --map     # propose theme→question map
    python3 scripts/import-cheatsheet.py pubad1 --apply   # write the answers

The source is authored in this app's own structure — dual intros, H1/H2 headings,
`keyword: mechanism. Ex: named authority` points, Way Forward, Conclusion — so the
translation is near-lossless.

Two source quirks that must be handled:

1. **The H1/H2 points are a two-column table.** pdftotext/docx extraction flattens
   it to a single stream in which points ALTERNATE H1, H2, H1, H2… Splitting the
   list in half would scramble both columns; we de-interleave by parity.
2. **Its "covers Qn" refers to a different question compilation.** We ignore those
   numbers and match each theme to our questions by token overlap, then require a
   human to eyeball the proposed map before applying it.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = {'pubad1': '/private/tmp/claude-501/-Users-gbs-Documents/'
                 '0a0132d5-110d-4c2a-96c5-f3a0efd9826b/scratchpad/pubad_p1.txt',
       'pubad2': '/private/tmp/claude-501/-Users-gbs-Documents/'
                 '0a0132d5-110d-4c2a-96c5-f3a0efd9826b/scratchpad/pubad_p2.txt'}

THEME = re.compile(r'^T\d+\s*·\s*(.+?)\s*(?:\(covers[^)]*\))?\s*(?:\[(\d+)m\])?\s*(?:★.*)?$')
INTRO = re.compile(r'^Intro\s*\(([^)]+)\)\s*:\s*(.+)$')
HEAD = re.compile(r'^H([12])\s*[—–-]\s*(.+?):?\s*$')
POINT = re.compile(r'^▪\s*(.+)$')
WF = re.compile(r'^Way Forward\s*:\s*(.+)$')
CONC = re.compile(r'^Conclusion\s*:\s*(.+)$')

STOP = set('the a an of and or in to for on with by is are as its it that this from '
           'discuss examine critically comment analyse evaluate explain trace assess '
           'india indian role than not but has have been how what why which'.split())


def toks(s):
    return {w for w in re.findall(r'[a-z]{4,}', s.lower()) if w not in STOP}


def clean(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'\s+([,.;:])', r'\1', s)


def parse(path):
    """→ [ {title, marks, intro:[{t,x}], h1, h2, pts:[...], wf, conc} ]"""
    themes, cur = [], None
    for raw in open(path, encoding='utf-8'):
        line = clean(raw)
        if not line:
            continue
        m = THEME.match(line)
        if m and line.startswith('T'):
            cur = {'title': m.group(1).strip(' ·'), 'marks': int(m.group(2)) if m.group(2) else None,
                   'intro': [], 'h1': None, 'h2': None, 'pts': [], 'wf': None, 'conc': None}
            themes.append(cur)
            continue
        if cur is None:
            continue
        m = INTRO.match(line)
        if m:
            cur['intro'].append({'t': m.group(1).strip(), 'x': m.group(2).strip()}); continue
        m = HEAD.match(line)
        if m:
            cur['h' + m.group(1)] = m.group(2).strip(); continue
        m = WF.match(line)
        if m:
            cur['wf'] = [p.strip() for p in m.group(1).split('·') if p.strip()]; continue
        m = CONC.match(line)
        if m:
            cur['conc'] = m.group(1).strip(); continue
        m = POINT.match(line)
        if m:
            cur['pts'].append(m.group(1).strip()); continue
        # a wrapped continuation of the previous point
        if cur['pts'] and not line.startswith(('Way Forward', 'Conclusion', 'H1', 'H2', 'Intro')) \
                and len(line) < 120 and not re.match(r'^\d+\s*·', line):
            cur['pts'][-1] = clean(cur['pts'][-1] + ' ' + line)
    return themes


def to_point(raw):
    """'Focus (what): techniques, POSDCORB. Ex: Gulick's claim.' → {k,x,ex}"""
    ex = None
    m = re.search(r'\bEx:\s*(.+?)\s*$', raw)
    if m:
        ex = m.group(1).strip().rstrip('.')
        raw = raw[:m.start()].strip().rstrip('.').rstrip(';')
    m = re.match(r'^(.{3,55}?)\s*:\s+(.+)$', raw)
    if m:
        pt = {'k': m.group(1).strip(), 'x': m.group(2).strip()}
    else:
        pt = {'x': raw.strip()}
    if ex:
        pt['ex'] = ex
    return pt


def merge(old, new):
    """Fold cheat-sheet content into an existing answer instead of replacing it.

    The cheat sheet is denser (named thinkers, Ex: anchors) but shorter than the
    corpus answers, so a straight replace pushes answers BELOW the word band.
    We keep the cheat sheet's headings, intros, way-forward and conclusion — its
    framing is better — and append the old points that add something new."""
    if not old:
        return new
    seen = {re.sub(r'\W+', '', (p.get('k', '') + p.get('x', ''))[:70]).lower()
            for sec in new.get('body', []) for p in sec['p']}
    extra = []
    for sec in old.get('body', []):
        for p in sec.get('p', []):
            sig = re.sub(r'\W+', '', (p.get('k', '') + p.get('x', ''))[:70]).lower()
            if sig not in seen:
                seen.add(sig)
                extra.append(p)
    if extra and new.get('body'):
        # spread the surviving old points across the two headed sections
        half = (len(extra) + 1) // 2
        new['body'][0]['p'] += extra[:half]
        if len(new['body']) > 1:
            new['body'][1]['p'] += extra[half:]
        else:
            new['body'][0]['p'] += extra[half:]
    for k in ('flash', 'directive', 'diag'):
        if old.get(k) and not new.get(k):
            new[k] = old[k]
    return new


def build(theme):
    a = {'src': 'cheatsheet'}
    if theme['intro']:
        a['intro'] = [{'t': i['t'], 'x': i['x']} for i in theme['intro'][:2]]
    # de-interleave the two-column point table: even index → H1, odd → H2
    h1 = [to_point(p) for p in theme['pts'][0::2]]
    h2 = [to_point(p) for p in theme['pts'][1::2]]
    body = []
    if h1:
        body.append({'h': theme['h1'] or 'Core dimensions', 'p': h1})
    if h2:
        body.append({'h': theme['h2'] or 'Analysis', 'p': h2})
    a['body'] = body
    if theme['wf']:
        a['wf'] = theme['wf']
    if theme['conc']:
        a['conc'] = theme['conc']
    return a


# Token overlap tangles a few near-neighbours (the Mughal theme drifting onto a
# British-legacy stem, Land Records swapping with Colonial Land-Revenue). Pin those
# by hand; the matcher handles the rest.
OVERRIDE = {
    'pubad2': {
        'Mughal Administration': 'pubad2-2',
        'Colonial Land-Revenue Settlements': 'pubad2-7',
        'Land Records & Land Administration': 'pubad2-43',
    },
    'pubad1': {},
}


def main():
    paper = sys.argv[1]
    apply = '--apply' in sys.argv
    themes = parse(SRC[paper])
    qs = json.load(open(os.path.join(ROOT, 'data', 'questions.json'), encoding='utf-8'))
    P = [p for p in qs if p['id'] == paper][0]
    ours = []
    for s in P['sections']:
        for q in s['qs']:
            ours.append((f"{paper}-{q['n']}", q['q'], q['m'], toks(q['q'])))

    path = os.path.join(ROOT, 'data', 'answers', f'{paper}.json')
    bank = json.load(open(path, encoding='utf-8'))

    # Hand-written answers are already in band and carefully structured — the cheat
    # sheet may replace an imported stub, never our own work.
    REPLACEABLE = {'mainslab', 'ported', 'docx', 'cheatsheet'}
    protected = {q for q, a in bank.items() if a.get('src') not in REPLACEABLE}

    proposed, used = [], set()
    for t in themes:
        pin = OVERRIDE.get(paper, {}).get(t['title'])
        if pin and pin not in used and pin not in protected:
            proposed.append((1.0, pin, t['title'], dict((q, x) for q, x, _, _ in
                             [(o[0], o[1], 0, 0) for o in ours]).get(pin, '')))
            used.add(pin)
            if apply:
                bank[pin] = merge(bank.get(pin), build(t))
            continue
        sig = toks(t['title'] + ' ' + (t['h1'] or '') + ' ' + (t['h2'] or '') + ' ' +
                   ' '.join(p[:60] for p in t['pts'][:6]))
        scored = []
        for qid, qtext, marks, qt in ours:
            if not qt:
                continue
            ov = len(sig & qt) / len(qt)                       # share of the question covered
            if t['marks'] and marks != t['marks']:
                ov *= 0.65                                      # mark mismatch is a weak signal
            scored.append((ov, qid, qtext))
        scored.sort(reverse=True)
        for ov, qid, qtext in scored[:2]:
            if ov >= 0.40 and qid not in used and qid not in protected:
                proposed.append((round(ov, 2), qid, t['title'], qtext))
                used.add(qid)
                if apply:
                    bank[qid] = merge(bank.get(qid), build(t))
                break

    print(f"{paper}: {len(themes)} themes → {len(proposed)} matched", file=sys.stderr)
    for ov, qid, title, qtext in sorted(proposed, key=lambda x: int(x[1].split('-')[1])):
        print(f"  {ov:.2f} {qid:12s} {title[:44]:44s} ← {qtext[:56]}")
    if apply:
        json.dump(bank, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"applied → {path}", file=sys.stderr)


if __name__ == '__main__':
    main()
