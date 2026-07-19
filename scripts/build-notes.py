#!/usr/bin/env python3
"""Turn the VR Mains Smasher PDFs into browsable notes: data/notes/<paper>.json.

pdftotext -layout gives us page-separated text with the printed chapter headings
intact. We split on chapter headings, keep the per-chapter PYQ block (which is
what makes these notes worth reading), and index sub-headings for navigation.

Nothing here paraphrases the source — the app shows the notes as written.
"""
import json, os, re, subprocess, sys

SRC_DIR = "/Users/gbs/Desktop/MAIN NOTES CONSOLIDATION/26 smashers"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST_DIR = os.path.join(ROOT, 'data', 'notes')

# which paper each book belongs to, and how it should be labelled in the UI
BOOKS = [
    ("VR_Mains_Smasher_Ancient_and_Medieval_History_Art_and_Culture_2026.pdf", "gs1", "Ancient & Medieval History, Art & Culture", "🏛"),
    ("VR_Mains_Smasher_Modern_History_2026.pdf",        "gs1", "Modern History",      "📜"),
    ("World_History_Mains_Smasher_2026.pdf",            "gs1", "World History",       "🌍"),
    ("VR_Mains_Smasher_Geography_2026_updated.pdf",     "gs1", "Geography",           "🗺"),
    ("VR_Mains_Smasher_Indian_Society_2026.pdf",        "gs1", "Indian Society",      "👥"),
    ("VR_Mains_Smasher_Polity_2026.pdf",                "gs2", "Polity & Governance", "⚖️"),
    ("International_Relations_Mains_Smasher_2026.pdf",  "gs2", "International Relations", "🤝"),
    ("VR_Mains_Smasher_Agriculture_2026.pdf",           "gs3", "Agriculture",         "🌾"),
    ("VR_Disaster_Management_2026_Merge_file.pdf",      "gs3", "Disaster Management", "🌪"),
]

# "  3      Natural Hazards"  — fallback heading when a book has no usable TOC
CHAP_RE = re.compile(r'^\s{2,}(\d{1,2})\s{4,}([A-Z][A-Za-z0-9 &,\-\'/()]{4,70})\s*$')
SUB_RE = re.compile(r'^\s*(\d{1,2}(?:\.\d{1,2}){1,2})\s+([A-Z][^\n]{4,90})$')
PYQ_HEAD = re.compile(r'UPSC Mains PYQs', re.I)
PYQ_ITEM = re.compile(r'^\s*\d{1,2}\.\s+(.{15,})$')


def pdf_pages(path):
    txt = subprocess.run(['pdftotext', '-layout', path, '-'],
                         capture_output=True, text=True).stdout
    return txt.split('\f')


def clean(page):
    """Drop the bare page-number lines that pdftotext leaves behind."""
    return '\n'.join(l for l in page.split('\n') if not PAGENO_RE.match(l))

# TOC lines: "3. Plate Tectonics.........9"  /  "1. Major Crops ... ……1"
TOC_CH = re.compile(r'^\s*(\d{1,2})[.)]\s*(.+?)\s*[.\u2026]{2,}\s*(\d{1,3})\s*$')
# Part banners in merged books: "Climatology..........58" (no leading number)
TOC_PART = re.compile(r'^\s*([A-Z][A-Za-z0-9 ,\-&\u2019\'()/]{6,90}?)\s*[.\u2026]{3,}\s*(\d{1,3})?\s*$')
PAGENO_RE = re.compile(r'^\s*(\d{1,3})\s*$')


def printed_page_map(pages):
    """printed page number → index into the pdftotext page list."""
    m = {}
    for i, pg in enumerate(pages):
        for line in reversed(pg.split('\n')[-8:]):
            pm = PAGENO_RE.match(line)
            if pm:
                m.setdefault(int(pm.group(1)), i)
                break
    return m


# pdftotext leaves control bytes (notably \x08) between dot-leaders and the page
# number in some books, which silently defeats the TOC regexes.
CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0e-\x1f]')


def parse_toc(pages):
    """Read the contents pages; returns [(part, num, title, printed_page)]."""
    entries, part = [], None
    for pg in pages[:4]:
        for line in CTRL_RE.sub(' ', pg).split('\n'):
            cm = TOC_CH.match(line)
            if cm:
                title = re.sub(r'\s+', ' ', cm.group(2)).strip(' .\u2026')
                if len(title) > 3:
                    entries.append((part, int(cm.group(1)), title, int(cm.group(3))))
                continue
            pm = TOC_PART.match(line)
            if pm and pm.group(2):
                t = re.sub(r'\s+', ' ', pm.group(1)).strip(' .\u2026')
                if 6 < len(t) < 90 and not t[0].isdigit():
                    part = t
    return entries



def pyqs_of(text):
    """Pull the PYQ list that heads most chapters — years included."""
    m = PYQ_HEAD.search(text)
    if not m:
        return []
    out, blank = [], 0
    for line in text[m.end():].split('\n'):
        im = PYQ_ITEM.match(line)
        if im:
            out.append(re.sub(r'\s+', ' ', im.group(1)).strip()); blank = 0
        elif out and line.strip():
            out[-1] += ' ' + re.sub(r'\s+', ' ', line.strip())
        elif not line.strip():
            blank += 1
            if blank > 3 and out:
                break
    # A real PYQ always carries its year — that filter drops numbered table rows
    # and section headings that happen to match the "1. …" item pattern.
    qs = [re.sub(r'\s+', ' ', q).strip() for q in out if len(q) > 25]
    qs = [q for q in qs if re.search(r'\((?:19|20)\d{2}\)', q)]
    out2 = []
    for q in qs:
        m2 = re.search(r'\((?:19|20)\d{2}\)', q)
        out2.append(q[:m2.end()].strip())
    return out2[:14]


def build_book(pdf, paper, title, icon):
    path = os.path.join(SRC_DIR, pdf)
    pages = pdf_pages(path)
    toc = parse_toc(pages)
    pmap = printed_page_map(pages)
    out = []

    if len(toc) >= 3:
        # slice on printed start pages; a chapter runs to the next entry's start
        marks = []
        for part, n, t, pp in toc:
            idx = pmap.get(pp)
            if idx is None:                       # nearest printed page we did see
                near = [k for k in pmap if abs(k - pp) <= 2]
                idx = pmap[min(near, key=lambda k: abs(k - pp))] if near else None
            if idx is not None:
                marks.append((idx, part, n, t))
        marks.sort(key=lambda x: x[0])
        for i, (idx, part, n, t) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(pages)
            text = '\n'.join(clean(p) for p in pages[idx:end]).strip()
            if len(text) < 400:
                continue
            out.append({'n': n, 't': t, 'part': part, 'p': idx + 1, 'text': text})

    if not out:                                    # no usable TOC — fall back to headings
        cur = None
        chapters = []
        for pno, page in enumerate(pages, 1):
            body = clean(page)
            for line in body.split('\n')[:12]:
                m = CHAP_RE.match(line)
                if m:
                    cur = {'n': int(m.group(1)), 't': m.group(2).strip(), 'part': None,
                           'p': pno, 'pages': []}
                    chapters.append(cur)
                    break
            if cur is not None:
                cur['pages'].append(body)
        for c in chapters:
            text = '\n'.join(c['pages']).strip()
            if len(text) >= 400:
                out.append({'n': c['n'], 't': c['t'], 'part': c['part'], 'p': c['p'], 'text': text})

    for c in out:
        c['text'] = re.sub(r'\n{4,}', '\n\n\n', c['text'])
        subs = []
        for line in c['text'].split('\n'):
            sm = SUB_RE.match(line)
            if sm:
                sv = re.sub(r'\s{2,}', '  ', sm.group(2)).strip()
                if len(sv) < 90 and not sv.endswith(('.', ',')):
                    subs.append(f"{sm.group(1)} {sv}")
        c['subs'] = subs[:28]
        c['pyq'] = pyqs_of(c['text'])

    return {'id': re.sub(r'\W+', '-', title.lower()).strip('-'),
            'paper': paper, 'title': title, 'icon': icon,
            'src': pdf, 'chapters': out}


def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    books = []
    for pdf, paper, title, icon in BOOKS:
        b = build_book(pdf, paper, title, icon)
        words = sum(len(c['text'].split()) for c in b['chapters'])
        pyq = sum(len(c['pyq']) for c in b['chapters'])
        print(f"  {paper}  {title:42s} {len(b['chapters']):3d} ch · {words:6d} w · {pyq:3d} PYQ", file=sys.stderr)
        json.dump(b, open(os.path.join(DEST_DIR, b['id'] + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
        books.append({k: b[k] for k in ('id', 'paper', 'title', 'icon', 'src')} |
                     {'chapters': [{'n': c['n'], 't': c['t'], 'subs': len(c['subs']),
                                    'w': len(c['text'].split())} for c in b['chapters']]})
    json.dump(books, open(os.path.join(DEST_DIR, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f"{len(books)} books → data/notes/", file=sys.stderr)


if __name__ == '__main__':
    main()
