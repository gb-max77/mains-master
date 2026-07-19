// ── Mains Master ── one module, no build step. Data in, reader out.
const $ = s => document.querySelector(s);
const el = (t, c, h) => { const n = document.createElement(t); if (c) n.className = c; if (h != null) n.innerHTML = h; return n; };
const esc = s => String(s ?? '').replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m]));
// **gold** spans are the load-bearing keywords — they drive Cloze masking too.
const md = s => esc(s)
  .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
  .replace(/(^|[^*])\*(?!\s)([^*]+?)\*(?!\*)/g, '$1<i>$2</i>');

const EXAM = { essay: '2026-08-21', gs1: '2026-08-22', gs2: '2026-08-22', gs3: '2026-08-23', gs4: '2026-08-23', pubad1: '2026-08-30', pubad2: '2026-08-30' };
// The order you revise in, not the order UPSC sits them.
const ORDER = ['gs1', 'gs3', 'pubad1', 'pubad2', 'gs2', 'gs4', 'essay'];

const store = {
  get k() { return 'mm-progress'; },
  data: JSON.parse(localStorage.getItem('mm-progress') || '{}'),
  save() { localStorage.setItem(this.k, JSON.stringify(this.data)); },
  rec(qid) { return this.data[qid] || null; },
  // SRS: Blank→1d, Shaky→3d, Confident→10d. Deliberately coarse — this is a 5-week run-in, not Anki.
  mark(qid, r) {
    // clicking the already-selected rating clears it — a question can go back to unmarked
    if (this.data[qid]?.r === r) { delete this.data[qid]; this.save(); return null; }
    const days = { 1: 1, 2: 3, 3: 10 }[r];
    this.data[qid] = { r, seen: Date.now(), due: Date.now() + days * 864e5 };
    this.save();
    return r;
  }
};

let PAPERS = [], ANSWERS = {}, cur = null, mode = 'full', stepOn = false, stepIdx = -1;

const paperOf = id => PAPERS.find(p => p.id === id);
const qidOf = (pid, n, b) => b == null ? `${pid}-${n}` : `${pid}-${n}-b${b}`;

async function loadAnswers(pid) {
  if (ANSWERS[pid]) return ANSWERS[pid];
  try {
    const r = await fetch(`data/answers/${pid}.json`, { cache: 'no-cache' });
    ANSWERS[pid] = r.ok ? await r.json() : {};
  } catch { ANSWERS[pid] = {}; }
  return ANSWERS[pid];
}

// flatten a paper into renderable rows (main question, then its branches)
function rows(p, mainOnly) {
  const out = [];
  for (const s of p.sections) for (const q of s.qs) {
    out.push({ ...q, sec: s.t, qid: qidOf(p.id, q.n), pid: p.id });
    if (mainOnly) continue;
    (q.branches || []).forEach((b, i) => out.push({
      ...b, sec: s.t, qid: qidOf(p.id, q.n, i), pid: p.id, isBranch: true, parent: qidOf(p.id, q.n), parentQ: q.q
    }));
  }
  return out;
}

/* ══════════════════ HOME ══════════════════ */
function renderHome() {
  const d = Math.ceil((new Date('2026-08-21') - Date.now()) / 864e5);
  $('#countdown').innerHTML = `<b>${d > 0 ? d : 0}</b><span>days to Essay paper · 21 Aug 2026</span>`;

  const wrap = $('#papers'); wrap.innerHTML = '';
  for (const pid of ORDER) {
    const p = paperOf(pid); if (!p) continue;
    const all = rows(p);
    const done = all.filter(r => ANSWERS[pid]?.[r.qid]).length;          // answer available
    const rev = all.filter(r => store.rec(r.qid)).length;                // covered in revision
    const pctD = all.length ? Math.round(done / all.length * 100) : 0;
    const pctR = all.length ? Math.round(rev / all.length * 100) : 0;
    const b = el('button', 'paper');
    b.innerHTML = `<span class="ic">${p.icon}</span>
      <span class="nm"><b>${esc(p.short)} — ${esc(p.title.replace(/^.*?—\s*/, ''))}</b>
      <small>${all.length} questions · ${new Date(EXAM[pid]).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</small></span>
      <span class="rings">
        <span class="ring ans" style="--p:${pctD}" title="${done} of ${all.length} have a model answer"><i>${done}</i></span>
        <span class="ring rev" style="--p:${pctR}" title="${rev} of ${all.length} marked in revision"><i>${rev}</i></span>
      </span>`;
    b.onclick = () => go(`#/p/${pid}`);
    wrap.append(b);
  }

  const due = [];
  for (const p of PAPERS) for (const r of rows(p)) {
    const rc = store.rec(r.qid);
    if (rc && rc.due < Date.now() && ANSWERS[p.id]?.[r.qid]) due.push(r);
  }
  $('#due-wrap').hidden = !due.length;
  if (due.length) {
    const L = $('#due-list'); L.innerHTML = '';
    due.slice(0, 12).forEach(r => L.append(qRow(r)));
  }
}

/* ══════════════════ LIST ══════════════════ */
const isThin = (a, r) => writtenWords(a) < (r.wmin || 0) || (a.body || []).length < 2;

let filt = { tier: 'all', q: '', theme: 'all', pid: null };

function qRow(r) {
  const a = ANSWERS[r.pid]?.[r.qid], rc = store.rec(r.qid);
  const b = el('button', `qrow tier${r.tier || 3}${r.isBranch ? ' branch' : ''}`);
  const rcTxt = rc ? `<span class="rc${rc.r}">${['', '● Blank', '● Shaky', '● Confident'][rc.r]}</span>` : '';
  b.innerHTML = `<span class="meta">
      ${r.tier ? `<span class="tag t${r.tier}">T${r.tier}</span>` : ''}
      <span>${r.m}M · ${r.w}w</span>
      ${r.isBranch ? '<span>↳ branch</span>' : ''}
      ${a ? '<span class="ok">✓ written</span>' : ''}
      ${rcTxt}</span><p><span class="qn">Q${r.n}.</span> ${esc(r.q)}</p>`;
  b.onclick = () => go(`#/a/${r.qid}`);
  if (r.isBranch || !r.branches?.length) return b;

  // Branches stay attached to their parent in the list: one chip, expanding in place.
  const wrap = el('div', 'qgroup');
  const bar = el('button', 'btoggle');
  const done = r.branches.filter((_, i) => ANSWERS[r.pid]?.[qidOf(r.pid, r.n, i)]).length;
  const more = r.branches.length - 1;
  bar.innerHTML = `<span class="caret">▸</span>
    <span class="btopic">↳ ${esc(topicOf(r.branches[0].q))}${more ? ` &nbsp;+${more} more` : ''}</span>
    <span class="bmeta">${done}/${r.branches.length} written</span>`;
  const box = el('div', 'bbox'); box.hidden = true;
  bar.onclick = () => {
    const open = box.hidden;
    if (open && !box.dataset.filled) {
      r.branches.forEach((br, i) => {
        const id = qidOf(r.pid, r.n, i);
        box.append(branchItem(id, br, ANSWERS[r.pid]?.[id]));
      });
      box.dataset.filled = '1';
    }
    box.hidden = !open;
    wrap.classList.toggle('open', open);
  };
  wrap.append(b, bar, box);
  return wrap;
}

function renderList() {
  const p = paperOf(filt.pid); if (!p) return go('#/');
  $('#list-title').textContent = `${p.icon} ${p.title}`;

  const sel = $('#theme-sel');
  if (sel.dataset.pid !== p.id) {
    sel.dataset.pid = p.id;
    sel.innerHTML = `<option value="all">All themes (${rows(p, true).length})</option>` +
      p.sections.map(s => `<option value="${esc(s.t)}">${esc(s.t)} (${s.qs.length})</option>`).join('');
    sel.value = 'all'; filt.theme = 'all';
  }

  const needle = filt.q.toLowerCase();
  const list = rows(p, true).filter(r => {
    if (filt.theme !== 'all' && r.sec !== filt.theme) return false;
    const ans = ANSWERS[p.id]?.[r.qid];
    if (filt.tier === 'todo') { if (ans) return false; }
    else if (filt.tier === 'thin') { if (!ans || !isThin(ans, r)) return false; }
    else if (filt.tier === 'weak') { const rc = store.rec(r.qid); if (!rc || rc.r > 2) return false; }
    else if (filt.tier !== 'all' && String(r.tier) !== filt.tier) return false;
    if (needle) {
      const hay = (r.q + ' ' + (ANSWERS[p.id]?.[r.qid]?.flash || []).join(' ')).toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });

  const L = $('#q-list'); L.innerHTML = '';
  if (!list.length) { L.append(el('div', 'empty', 'No questions match these filters.')); return; }
  let sec = null;
  for (const r of list) {
    if (r.sec !== sec) { sec = r.sec; L.append(el('div', 'sec-h', esc(sec))); }
    L.append(qRow(r));
  }
}

// A branch's gist: first clause, trimmed — enough to recognise the angle at a glance.
function topicOf(q) {
  let t = String(q).replace(/\*/g, '').split(/[;—]|\s+with reference to\s+/i)[0].trim();
  return t.length > 72 ? t.slice(0, 69).replace(/\s+\S*$/, '') + '…' : t;
}

/* ══════════════════ ANSWER ══════════════════ */
function findRow(qid) {
  const pid = qid.split('-')[0];
  const p = paperOf(pid); if (!p) return null;
  return rows(p).find(r => r.qid === qid) || null;
}

// Cloze masks the gold spans — tap to reveal one, or hit the reveal-all action.
const clozed = h => h.replace(/<b>(.+?)<\/b>/g, '<b class="cz">$1</b>');

function pointHTML(pt) {
  let h = '';
  if (pt.k) h += `<b class="lbl">${md(pt.k)}</b>: `;
  h += `<span class="x">${md(pt.x)}</span>`;
  if (pt.ex) h += ` <span class="ex"><b class="lbl">Ex:</b> ${md(pt.ex)}</span>`;
  return h;
}

// Words you'd actually put on paper: ONE intro + headings + points + wf + conclusion.
// Mirrors scripts/add.py written_words() — keep the two in step.
function writtenWords(a) {
  const parts = [];
  if (a.intro?.length) parts.push(a.intro[0].x);
  for (const b of a.body || []) {
    parts.push(b.h || '');
    for (const p of b.p || []) parts.push(p.k || '', p.x || '', p.ex || '');
  }
  parts.push(...(a.wf || []), a.conc || '');
  return parts.join(' ').replace(/\*\*|[•·—–]/g, ' ').split(/\s+/).filter(Boolean).length;
}

function diagHTML(d) {
  if (!d) return '';
  const parts = String(d.d).split(/\s*(?:→|->)\s*/);
  const body = parts.length > 1
    ? `<div class="flow">${parts.map(x => `<span class="node">${esc(x)}</span>`).join('<span class="arw">→</span>')}</div>`
    : `<div>${esc(d.d)}</div>`;
  return `<div class="diag"><div class="lbl">Diagram · ${esc(d.k)} · drawable in 30s</div>${body}</div>`;
}

// Each paper is marked on different things, so the regeneration prompt differs.
// Keep these short — an over-specified prompt produces a worse answer, not a better one.
const PAPER_BRIEF = {
  essay: r => `Write a UPSC CSE Mains 2026 essay (1000-1200 words) on: "${r.q}".
Philosophical and multidimensional. Open with an anecdote, parable or paradox; build a clear thesis; develop 6-8 dimensions (historical, social, economic, political, ethical, technological, global); illustrate each with real examples and thinkers; give the counter-view its due; close by returning to the opening image with a forward-looking vision. Flowing prose, no bullet points or headings-as-lists. Reflective, balanced, never partisan.`,

  pubad1: r => `Write a UPSC Public Administration Paper I (Administrative Theory) answer, ${r.m} marks, ${r.wmin}-${r.w} words, at top-100 optional standard: "${r.q}".
Answer IN the discipline's vocabulary. Open with a thinker or paradigm, not a general definition. Name theorists and their works and dates. Organise under 2-3 bold sub-headings with bullet points. Bridge every theory to ONE concrete Indian administrative example. Scholarly critique is mandatory — who challenged this, in which work. Close with a one-line analytical verdict.`,

  pubad2: r => `Write a UPSC Public Administration Paper II (Indian Administration) answer, ${r.m} marks, ${r.wmin}-${r.w} words, at top-100 optional standard: "${r.q}".
Anchor in constitutional provisions, committee and commission reports (2nd ARC first), and current administrative developments. Interlink at least one Paper-I theory or thinker — that linkage is the scoring differentiator. Organise under 2-3 bold sub-headings with bullet points. Keep it in the administrative lane, not the political one. Close with a reform-oriented line.`,

  gs: r => `Write a UPSC CSE Mains 2026 model answer, ${r.m} marks, ${r.wmin}-${r.w} words, as an AIR top-20 candidate would write it in the exam: "${r.q}".
Format: 1-2 line intro (definition, data, judgment or report as the demand fits); then 2-3 headed body sections; under each, 3-4 points as "Bold point heading: one-line expansion. Ex: named example, data, committee, report, Article or judgment"; then a Way Forward line; then one forward-looking conclusion tied to a constitutional value or national goal. Maximise keywords. No repetition, no generic filler. Every named fact must be real and verifiable.`
};

function gaiURL(r) {
  const brief = (PAPER_BRIEF[r.pid] || PAPER_BRIEF.gs)(r);
  return 'https://www.google.com/search?udm=50&q=' + encodeURIComponent(brief);
}

// The answer body as a string, so the same renderer serves the full page and the
// inline branch panels — one source of truth for how an answer looks.
function answerHTML(a) {
  let h = '';
  for (const i of a.intro || []) h += `<p class="intro"><b class="lbl">Intro (${esc(i.t)}):</b> ${md(i.x)}</p>`;
  (a.body || []).forEach((bd, bi) => {
    h += `<div class="bh">H${bi + 1} — ${md(bd.h)}</div>`;
    for (const pt of bd.p || []) h += `<p class="pt${pt.unv ? ' unv' : ''}">${pointHTML(pt)}</p>`;
  });
  if (a.diag) h += diagHTML(a.diag);
  if (a.wf?.length) h += `<p class="wf"><b class="lbl">Way Forward:</b> ${a.wf.map(md).join(' · ')}</p>`;
  if (a.mne) h += `<p class="wf"><b class="lbl">Mnemonic:</b> ${md(a.mne)}</p>`;
  if (a.conc) h += `<p class="conc">Conclusion: ${md(a.conc)}</p>`;
  return h;
}

const noAnswerHTML = r => `<div class="nowrite"><p>No model answer written for this question yet.</p>
  <small>Tier ${r.tier || '—'} · generate one in Google AI Mode below, pre-loaded with the paper's answer brief.</small></div>`;

// A collapsed branch: question line + toggle. Expanding reveals the answer in place.
function branchItem(id, b, ans) {
  const it = el('div', 'bitem');
  const head = el('button', 'bhead');
  head.innerHTML = `<span class="caret">▸</span><span class="btxt">↳ ${esc(b.q)}</span>
    <span class="bmeta">${b.m}M${ans ? ' <i class="ok">✓</i>' : ''}</span>`;
  const body = el('div', 'bbody');
  body.hidden = true;
  head.onclick = () => {
    const open = body.hidden;
    if (open && !body.dataset.filled) {
      body.innerHTML = (ans ? answerHTML(ans) : noAnswerHTML(b))
        + `<a class="bopen" href="#/a/${id}">Open full ↗</a>`;
      body.dataset.filled = '1';
    }
    body.hidden = !open;
    it.classList.toggle('open', open);
    if (open && mode === 'cloze') applyCloze(body);
  };
  it.append(head, body);
  return it;
}

async function renderAnswer(qid) {
  const pid = qid.split('-')[0];
  await loadAnswers(pid);
  const r = findRow(qid); if (!r) return go('#/');
  cur = r; stepIdx = -1; stepOn = false; $('#btn-step').classList.remove('on');
  const a = ANSWERS[pid]?.[qid];
  const A = $('#answer'); A.innerHTML = '';

  const p = paperOf(pid);
  A.append(el('h1', 'qtitle', esc(r.q)));
  const rc = store.rec(qid);
  let wc = '';
  if (a) {
    const w = writtenWords(a), lo = r.wmin || 0;
    // below the floor = marks left on the table; above the ceiling = can't be written in time
    const cls = w > r.w * 1.05 ? 'over' : (w < lo ? 'thin' : 'ok');
    const note = { over: ' — trim', thin: ' — under limit', ok: '' }[cls];
    wc = ` · <span class="wc ${cls}">${w} / ${lo}-${r.w}w${note}</span>`;
  }
  A.append(el('div', 'qmeta',
    `${p.short} · ${r.sec} ${r.tier ? `· T${r.tier}` : ''} · ${r.m} marks · ${Math.round(r.m * 0.72)} min`
    + (r.isBranch ? ` · ↳ branch of Q${r.parent.split('-')[1]}` : '')
    + wc
    + (rc ? ` · last recall: ${['', 'Blank', 'Shaky', 'Confident'][rc.r]}` : '')));

  A.insertAdjacentHTML('beforeend', a ? answerHTML(a) : noAnswerHTML(r));

  // Branches ride on the same prepared content, so they live WITH the parent rather
  // than as separate destinations — each expands inline instead of navigating away.
  const parent = r.isBranch ? findRow(r.parent) : r;
  if (parent?.branches?.length) {
    const bx = el('div', 'branches',
      `<h3>Branch angles — ${esc(topicOf(parent.q))}</h3>`);
    if (r.isBranch) {
      const l = el('a', 'bmain', `🌳 Main question: ${esc(r.parentQ)}`);
      l.href = `#/a/${r.parent}`; bx.append(l);
    }
    parent.branches.forEach((b, i) => {
      const id = qidOf(pid, parent.n, i);
      if (id === qid) return;
      bx.append(branchItem(id, b, ANSWERS[pid]?.[id]));
    });
    A.append(bx);
  }

  const acts = el('div', 'actions');
  const gai = el('button', 'act gai', '⟳ Regenerate in Google AI Mode');
  gai.onclick = () => window.open(gaiURL(r), '_blank', 'noopener');
  const rev = el('button', 'act', '👁 Reveal all cloze');
  rev.onclick = () => A.querySelectorAll('.cz').forEach(c => c.classList.add('show'));
  const pr = el('button', 'act', '🖨 Print / PDF');
  pr.onclick = () => window.print();
  const cp = el('button', 'act', '⧉ Copy answer');
  cp.onclick = () => { navigator.clipboard.writeText(A.innerText); cp.textContent = '✓ Copied'; setTimeout(() => cp.textContent = '⧉ Copy answer', 1400); };
  acts.append(gai, rev, cp, pr);
  A.append(acts);

  paintRecall(qid);
  renderPager(r);
  renderSidebar(r);
  applyMode();
  window.scrollTo(0, 0);
}

function applyCloze(root) {
  root.querySelectorAll('.pt, .intro, .conc, .wf').forEach(n => { n.innerHTML = clozed(n.innerHTML); });
  root.querySelectorAll('.cz').forEach(c => c.onclick = () => c.classList.toggle('show'));
}

function applyMode() {
  document.body.dataset.mode = mode;
  const A = $('#answer');
  // removeAttribute, not className='' — a leftover class="" stops clozed()'s <b> regex matching on re-entry
  A.querySelectorAll('b.cz').forEach(c => c.removeAttribute('class'));
  if (mode === 'cloze') applyCloze(A);
}

function step(dir) {
  const pts = [...$('#answer').querySelectorAll('.pt')];
  if (!pts.length) return;
  pts.forEach(p => p.classList.remove('focus'));
  stepIdx = Math.max(0, Math.min(pts.length - 1, stepIdx + dir));
  const n = pts[stepIdx];
  n.classList.add('focus');
  n.scrollIntoView({ block: 'center' }); // instant — smooth scrolling breaks the in-app browser
}

/* ══════════════════ PAGER + SIDEBAR ══════════════════ */
// Both walk the same ordered list of main questions, so "next" in the pager and
// the sidebar's order can never disagree.
const mainRows = pid => { const p = paperOf(pid); return p ? rows(p, true) : []; };

function renderPager(r) {
  const list = mainRows(r.pid);
  const base = r.isBranch ? r.parent : r.qid;
  const i = list.findIndex(x => x.qid === base);
  const prev = i > 0 ? list[i - 1] : null, next = i >= 0 && i < list.length - 1 ? list[i + 1] : null;
  $('#pg-pos').textContent = i >= 0 ? `Q${list[i].n} of ${list.length}` : '';
  for (const [btn, tgt] of [[$('#pg-prev'), prev], [$('#pg-next'), next]]) {
    btn.disabled = !tgt;
    btn.title = tgt ? tgt.q.slice(0, 90) : '';
    btn.onclick = tgt ? () => go(`#/a/${tgt.qid}`) : null;
  }
}

function renderSidebar(r) {
  const L = $('#sb-list'); L.innerHTML = '';
  const base = r.isBranch ? r.parent : r.qid;
  let sec = null;
  for (const q of mainRows(r.pid)) {
    if (q.sec !== sec) { sec = q.sec; L.append(el('div', 'sb-sec', esc(sec))); }
    const a = ANSWERS[r.pid]?.[q.qid];
    const b = el('button', 'sb-q' + (q.qid === base ? ' on' : '') + (a ? '' : ' todo'));
    b.innerHTML = `<span class="sb-n">Q${q.n}</span><span class="sb-t">${esc(q.q)}</span>`;
    b.onclick = () => { go(`#/a/${q.qid}`); document.body.classList.remove('sb-open'); };
    L.append(b);
  }
  const on = L.querySelector('.sb-q.on');
  if (on) on.scrollIntoView({ block: 'center' });   // instant — smooth breaks the in-app browser
}

/* ══════════════════ ROUTER ══════════════════ */
function go(hash) { location.hash = hash; }

async function route() {
  const h = location.hash || '#/';
  const [, kind, arg] = h.split('/');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.body.dataset.mode = 'full';
  document.body.classList.remove('sb-open');
  $('#back').hidden = h === '#/';
  $('#btn-sb').hidden = kind !== 'a';

  if (kind === 'p' && arg) {
    filt.pid = arg; filt.q = ''; $('#q-search').value = '';
    await loadAnswers(arg);
    $('#view-list').classList.add('active'); renderList();
  } else if (kind === 'a' && arg) {
    $('#view-answer').classList.add('active'); await renderAnswer(arg);
  } else {
    $('#view-home').classList.add('active');
    await Promise.all(ORDER.map(loadAnswers));
    renderHome();
  }
}

/* ══════════════════ WIRING ══════════════════ */
$('#back').onclick = () => history.back();
$('#btn-search').onclick = () => { if (filt.pid) { go(`#/p/${filt.pid}`); setTimeout(() => $('#q-search').focus(), 60); } };
$('#q-search').oninput = e => { filt.q = e.target.value; renderList(); };
$('#theme-sel').onchange = e => { filt.theme = e.target.value; renderList(); };
$('#tier-chips').onclick = e => {
  const c = e.target.closest('.chip'); if (!c) return;
  filt.tier = c.dataset.tier;
  $('#tier-chips').querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', x === c));
  renderList();
};
$('#modes').onclick = e => {
  const m = e.target.closest('.mode'); if (!m) return;
  mode = m.dataset.mode;
  $('#modes').querySelectorAll('.mode').forEach(x => x.classList.toggle('active', x === m));
  applyMode();
};
$('#btn-step').onclick = () => {
  stepOn = !stepOn; $('#btn-step').classList.toggle('on', stepOn);
  if (stepOn) { stepIdx = -1; step(1); }
  else $('#answer').querySelectorAll('.pt').forEach(p => p.classList.remove('focus'));
};
$('#recall').onclick = e => {
  const b = e.target.closest('.rc'); if (!b || !cur) return;
  const set = store.mark(cur.qid, +b.dataset.r);
  paintRecall(cur.qid);
  if (set === null) return;                    // just cleared — stay put
  b.textContent = '✓';
  setTimeout(() => { b.textContent = { 1: 'Blank', 2: 'Shaky', 3: 'Confident' }[b.dataset.r]; history.back(); }, 450);
};

function paintRecall(qid) {
  const rc = store.rec(qid);
  $('#recall').querySelectorAll('.rc').forEach(x => x.classList.toggle('on', rc && +x.dataset.r === rc.r));
  $('#recall').querySelector('span').textContent =
    rc ? `Marked ${{ 1: 'Blank', 2: 'Shaky', 3: 'Confident' }[rc.r]} — tap again to clear` : 'How well did you recall it?';
}
addEventListener('keydown', e => {
  if (!$('#view-answer').classList.contains('active')) return;
  if (e.key === 'ArrowRight') { stepOn = true; $('#btn-step').classList.add('on'); step(1); }
  if (e.key === 'ArrowLeft') step(-1);
});
const toggleSb = () => document.body.classList.toggle('sb-open');
$('#sb-pin').onclick = toggleSb;
$('#btn-sb').onclick = toggleSb;
addEventListener('keydown', e => {
  if (!$('#view-answer').classList.contains('active')) return;
  if (e.key === 'Escape') document.body.classList.remove('sb-open');
});
addEventListener('hashchange', route);

(async function init() {
  PAPERS = await (await fetch('data/questions.json', { cache: 'no-cache' })).json();
  await route();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => { });
})();
