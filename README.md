# Mains Master — UPSC CSE 2026 Model Answer Book

A static, offline-first PWA of exam-replicable model answers for CSE Mains 2026,
built for high visual recall rather than for reading.

**Live:** https://gb-max77.github.io/mains-master/

## The idea

An examiner spends ~90 seconds on an answer. So the *skeleton* is the design target:
colour carries structure, and every role has exactly one hue.

| Colour | Role |
|---|---|
| Gold | Question title · Conclusion — the frame |
| Lavender italic | Intro (two alternative openings per answer) |
| Blue | H1/H2/H3 body headings |
| Bold white → grey | Point head → its expansion |
| Green | `Ex:` examples · Way Forward — the mark-fetchers |

## Reading modes

- **Full** — the answer as you'd write it
- **Skeleton** — headings and point-heads only, for active recall
- **Cloze** — load-bearing keywords masked; tap to reveal
- **60s scan** — heads and examples, for last-week revision
- **Step** (→ / ←) — walk one point at a time in a focus box

Plus Confident/Shaky/Blank recall with spaced repetition, tier and theme filters,
branch questions expanding in place under their parent, a live word-count chip
against each question's budget, print-to-PDF, and a per-answer
**Regenerate in Google AI Mode** button carrying the full answer architecture.

## Data

`data/questions.json` — 458 master + 225 branch questions, parsed from the 2026
prediction compilation. `data/answers/<paper>.json` — answers keyed `gs1-8`
(master) or `gs1-8-b0` (branch).

```
scripts/build-questions.py    prediction markdown → questions.json
scripts/import-gs3-docx.py    GS3 answer docx → answers/gs3.json
scripts/add.py                merge an answer batch + audit words vs budget
```

Word budget is 15 × marks (10m ≈ 150w, 15m ≈ 250w). `add.py` flags anything
over or thin — an answer that can't be written in the time isn't a model answer.

## Local

```sh
python3 -m http.server 4200
```

Bump `CACHE` in `sw.js` on every deploy or the service worker serves stale assets.
