#!/usr/bin/env python3
"""Convert the user's GS3_Model_Answers.docx into the reader schema.

The docx is already written to the target architecture (Intro — / ▪ point / Way
Forward / Conclusion —), so this is a faithful structural translation, not a
rewrite. One deliberate limitation: the source has a FLAT bullet list per answer
with no H1/H2 sub-headings, so every answer lands in a single body section. We do
not invent sub-headings — inventing structure the author didn't write would put
words in their mouth. Answers enriched later can be split by hand.
"""
import html, json, os, re, sys, zipfile

DOCX = "/Users/gbs/Downloads/GS3_Model_Answers.docx"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'data', 'answers', 'gs3.json')

Q_RE = re.compile(r'^Q(\d+)\.\s*\[([^\]]*)\]\s*(.+)$')
BRANCH_RE = re.compile(r'^↳\s*Branch[^:]*:\s*(.+)$')
INTRO_RE = re.compile(r'^Intro\s*[—–-]\s*(.+)$')
CONC_RE = re.compile(r'^Conclusion\s*[—–-]\s*(.+)$')
WF_RE = re.compile(r'^Way Forward\b.*$', re.I)
BULLET_RE = re.compile(r'^▪\s*(.+)$')
SECTION_RE = re.compile(r'^[A-F]\.\d+\s')
EX_RE = re.compile(r'\s*(?:Ex|E\.g)[.:]\s*(.+?)\s*$', re.I)


def text_of(docx):
    x = zipfile.ZipFile(docx).read('word/document.xml').decode('utf-8')
    x = re.sub(r'</w:p>', '\n', x)
    x = re.sub(r'<[^>]+>', '', x)
    return [l.strip() for l in html.unescape(x).split('\n')]


# The docx carries no bold runs, so Cloze/Skeleton would have nothing to key on.
# We re-derive gold keywords mechanically and conservatively: hard data, acronyms,
# and formally-named instruments. Nothing subjective — no "important-sounding" prose.
# ONE alternation scanned left-to-right: finditer yields non-overlapping matches, so
# a token can never be wrapped twice. (Running separate regexes in sequence produced
# nested markers like **₹**2,817 cr**** and split "LVM-3" into **LVM**-**3, cr**ew.)
GOLD = re.compile(
    r'~?₹\s?[\d,][\d,.]*(?:\s?(?:lakh|crore|cr|bn|mn|trillion))?'          # money
    r'|~?\d[\d,.]*\s?(?:%|GW|MW|BCM|MtCO2e?|km|bn|mt|cr)\b'                # quantities
    r'|[A-Z][A-Za-z]*(?:[- ][A-Z][A-Za-z]*)*\s'
    r'(?:Mission|Scheme|Yojana|Act|Code|Codes|Commission|Council|Policy|Summit|Declaration|Treaty|Programme)'
    r'(?:,\s?\d{4})?'                                                       # named instruments
    r'|\b[A-Z]{2,6}(?:-[A-Z0-9]{1,4})?\b'                                   # acronyms, incl. LVM-3
)
STOP = {'US', 'UK', 'EU', 'GDP', 'AI', 'IT', 'India'}   # too generic to be worth recalling


def goldify(s, budget=4):
    """Wrap up to `budget` load-bearing tokens in ** **."""
    if '**' in s:
        return s                      # author already marked emphasis — leave it alone
    out, last, n = [], 0, 0
    for m in GOLD.finditer(s):
        if n >= budget:
            break
        if m.group(0).strip() in STOP:
            continue
        out.append(s[last:m.start()])
        out.append(f'**{m.group(0)}**')
        last, n = m.end(), n + 1
    out.append(s[last:])
    return ''.join(out)


def mk_point(raw):
    """'Export competitiveness restored: The US is...' → {k, x, ex?}"""
    ex = None
    m = EX_RE.search(raw)
    if m:
        ex = m.group(1).strip()
        raw = raw[:m.start()].strip().rstrip(';').rstrip('.')
    # split on the first colon that terminates a short lead-in
    m = re.match(r'^(.{3,60}?):\s+(.+)$', raw, re.S)
    if m:
        pt = {'k': m.group(1).strip(), 'x': goldify(m.group(2).strip())}
    else:
        pt = {'x': goldify(raw.strip())}
    if ex:
        pt['ex'] = ex
    return pt


def flush(cur, bank, qid):
    if not cur or not qid:
        return
    a = {'src': 'docx'}
    if cur['intro']:
        a['intro'] = [{'t': 'concept', 'x': goldify(cur['intro'])}]
    if cur['points']:
        a['body'] = [{'h': 'Core dimensions', 'p': cur['points']}]
    if cur['wf']:
        a['wf'] = [goldify(w, 2) for w in cur['wf']]
    if cur['conc']:
        a['conc'] = goldify(cur['conc'], 2)
    if cur['diag']:
        a['diag'] = {'k': 'flow', 'd': cur['diag']}
    bank[qid] = a


def blank():
    return {'intro': None, 'points': [], 'wf': [], 'conc': None, 'diag': None, 'in_wf': False}


def main():
    lines = text_of(DOCX)
    qs = json.load(open(os.path.join(ROOT, 'data', 'questions.json'), encoding='utf-8'))
    paper = [p for p in qs if p['id'] == 'gs3'][0]
    branches = {q['n']: q.get('branches', []) for s in paper['sections'] for q in s['qs']}

    bank, cur, qid, master_n, b_used = {}, None, None, None, {}

    for line in lines:
        if not line:
            continue

        m = Q_RE.match(line)
        if m:
            flush(cur, bank, qid)
            master_n = int(m.group(1))
            qid, cur = f'gs3-{master_n}', blank()
            continue

        m = BRANCH_RE.match(line)
        if m and master_n:
            flush(cur, bank, qid)
            # branches appear in the same order as the prediction file lists them
            i = b_used.get(master_n, 0)
            b_used[master_n] = i + 1
            qid = f'gs3-{master_n}-b{i}' if i < len(branches.get(master_n, [])) else None
            cur = blank()
            continue

        if cur is None:
            continue
        if SECTION_RE.match(line):
            flush(cur, bank, qid); cur, qid = None, None
            continue

        m = INTRO_RE.match(line)
        if m:
            cur['intro'] = m.group(1).strip(); continue
        m = CONC_RE.match(line)
        if m:
            cur['conc'] = m.group(1).strip(); continue
        if WF_RE.match(line):
            cur['in_wf'] = True; continue
        m = BULLET_RE.match(line)
        if m:
            if cur['in_wf']:
                cur['wf'].append(m.group(1).strip())
            else:
                cur['points'].append(mk_point(m.group(1).strip()))
            continue
        # unbulleted line sitting between intro and the points = the ASCII diagram
        if cur['intro'] and not cur['points'] and not cur['diag'] and len(line) > 20:
            cur['diag'] = re.sub(r'\s{2,}', ' ', line)

    flush(cur, bank, qid)
    json.dump(bank, open(DEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    main_n = sum(1 for k in bank if k.count('-') == 1)
    print(f"  {main_n} master + {len(bank)-main_n} branch = {len(bank)} → gs3.json", file=sys.stderr)
    thin = [k for k, a in bank.items() if not a.get('body')]
    if thin:
        print(f"  ⚠ no body parsed for: {', '.join(thin)}", file=sys.stderr)


if __name__ == '__main__':
    main()
