// SPDX-License-Identifier: AGPL-3.0-or-later
{
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const S = {decks: [], cards: [], settings: {}, swaps: [], byId: {}};
let undoFn = null, toastTimer = null;

async function api(path, opts = {}) {
  const r = await fetch(path, {headers: {"Content-Type": "application/json"}, ...opts,
    body: opts.body && typeof opts.body !== "string" ? JSON.stringify(opts.body) : opts.body});
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  const t = r.headers.get("content-type") || "";
  return t.includes("json") ? r.json() : r.text();
}

async function load() {
  const st = await api("/api/state");
  Object.assign(S, st);
  S.byId = Object.fromEntries(S.decks.map(d => [d.id, d]));
  render();
}

function toast(msg, undo) {
  const t = $("#toast");
  t.querySelector("span").textContent = msg;
  undoFn = undo || null;
  $("#toast-undo").hidden = !undo;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 6000);
}
$("#toast-undo").addEventListener("click", async () => { $("#toast").hidden = true; if (undoFn) { await undoFn(); undoFn = null; load(); } });

/* ---------- slots and the sleeve drawing ---------- */
// Slots are numbered per pool along the long edges of the card face:
// 1..N on the left edge, N+1..2N on the right edge. A pool with sideboard
// marks uses the right edge for them instead (same height as the deck's slot).
// Variant marks sit on the bottom edge. Nothing goes on the top strip.
const N = () => S.settings.slots_per_edge || 30;
const NB = () => S.settings.bottom_positions || 20;
const poolInfo = name => (S.pools || []).find(p => p.name === (name || "Main")) || {name, sideboard_marks: false, capacity: 2 * N()};
function slotLabel(s) { return s <= N() ? `L${s}` : `R${s - N()}`; }

// Mark ids: "d12" main mark, "d12.sb" sideboard mark, "d12.v3" variant 3.
function splitMark(m) { const g = /^d(\d+)(?:\.(sb|v(\d+)))?$/.exec(m) || []; return [+g[1], g[3] ? +g[3] : 0, g[2] === "sb" ? "sb" : g[3] ? "var" : "main"]; }
const belongs = (m, d) => splitMark(m)[0] === d;
function markInfo(m) {
  const [d, v, kind] = splitMark(m), deck = S.byId[d];
  if (!deck) return null;
  if (kind === "var") {
    const va = (deck.variants || []).find(x => x.idx === v);
    const pos = va && va.pos || 0;
    return {deck, edge: "B", pos, color: va ? va.color : "#999", label: `B${pos}`, name: `${deck.name} · ${va ? va.name : "variant " + v}`, sub: va ? va.name : "variant"};
  }
  if (kind === "sb") return {deck, edge: "R", pos: deck.slot, color: deck.color, label: `R${deck.slot} SB`, name: `${deck.name} sideboard`, sub: "sideboard"};
  const left = deck.slot <= N();
  return {deck, edge: left ? "L" : "R", pos: left ? deck.slot : deck.slot - N(), color: deck.color, label: slotLabel(deck.slot), name: deck.name};
}

// marks: [{edge:'L'|'R'|'B', pos, color, kind:'keep'|'add'|'clear'}] drawn on a card face
function sleeveSVG(marks, opts = {}) {
  const W = 70, H = 98, m = 9, n = N(), nb = NB(), fromTop = S.settings.slot1_end !== "bottom";
  const sy = (H - 2 * m) / (n - 1), sx = (W - 2 * m) / (nb - 1);
  const y = p => fromTop ? m + (p - 1) * sy : H - m - (p - 1) * sy;
  let g = `<rect x=".5" y=".5" width="${W - 1}" height="${H - 1}" rx="4" fill="var(--sleeve)" stroke="var(--line)"/>`;
  g += `<rect x="7" y="4" width="${W - 14}" height="8" rx="1.5" fill="var(--panel)" opacity=".8"/>`;
  g += `<rect x="7" y="15" width="${W - 14}" height="36" rx="1.5" fill="var(--panel)" opacity=".45"/>`;
  g += `<rect x="7" y="55" width="${W - 14}" height="32" rx="1.5" fill="var(--panel)" opacity=".45"/>`;
  for (let i = 1; i <= n; i++) { const t = i % 5 === 0 ? 2.6 : 1.4;
    g += `<line x1="0" x2="${t}" y1="${y(i)}" y2="${y(i)}" stroke="var(--mute)" stroke-width=".35"/><line x1="${W - t}" x2="${W}" y1="${y(i)}" y2="${y(i)}" stroke="var(--mute)" stroke-width=".35"/>`; }
  for (let i = 1; i <= nb; i++) { const x = m + (i - 1) * sx, t = i % 5 === 0 ? 2.6 : 1.4;
    g += `<line x1="${x}" x2="${x}" y1="${H}" y2="${H - t}" stroke="var(--mute)" stroke-width=".35"/>`; }
  const L = 5.5, T = Math.max(2, Math.min(sy, sx) * .85);
  for (const mk of marks) {
    if (!mk.pos) continue;
    let x, yy, w, h;
    if (mk.edge === "B") { x = m + (mk.pos - 1) * sx - T / 2; yy = H - L; w = T; h = L; }
    else { yy = y(mk.pos) - T / 2; w = L; h = T; x = mk.edge === "L" ? 0 : W - L; }
    const c = esc(mk.color);
    if (mk.kind === "clear") g += `<rect x="${x}" y="${yy}" width="${w}" height="${h}" fill="none" stroke="${c}" stroke-width=".7" stroke-dasharray="1 .6"/><path d="M${x} ${yy}L${x + w} ${yy + h}" stroke="var(--ink)" stroke-width=".5"/>`;
    else g += `<rect x="${x}" y="${yy}" width="${w}" height="${h}" rx=".5" fill="${c}" ${mk.kind === "keep" ? 'opacity=".35"' : 'stroke="var(--ink)" stroke-width=".3"'}/>`;
  }
  return `<svg class="sleeve${opts.big ? " big" : ""}" viewBox="-1 -1 ${W + 2} ${H + 2}" role="img" aria-label="Card face with sleeve marks">${g}</svg>`;
}
const mk = (ids, kind) => ids.map(markInfo).filter(Boolean).map(i => ({edge: i.edge, pos: i.pos, color: i.color, kind}));
const chip = id => { const i = markInfo(id); return i ? `<span class="chip"><span class="dot${i.edge === "B" ? " sm" : ""}" style="--c:${esc(i.color)}"></span>${esc(i.label)} ${esc(i.sub && i.edge === "B" ? i.sub : i.deck.name)}</span>` : `<span class="chip">deleted deck</span>`; };
const short = id => { const i = markInfo(id); return i ? i.label : "?"; };
const EDGE_ORDER = {L: 0, R: 1, B: 2};
const markOrder = (a, b) => { const ia = markInfo(a), ib = markInfo(b); if (!ia || !ib) return !ia - !ib; return EDGE_ORDER[ia.edge] - EDGE_ORDER[ib.edge] || ia.pos - ib.pos; };
const fmt = ids => [...ids].sort(markOrder).map(short).join(" ");

/* ---------- MARK ---------- */
function markFilter() {
  const q = $("#m-q").value.trim().toLowerCase(), view = $("#m-view").value;
  const deck = +$("#m-deck").value || 0, pool = $("#m-pool").value;
  const inPool = id => !pool || (S.byId[id] && S.byId[id].pool === pool);
  const out = [];
  for (const c of S.cards) {
    if (q && !c.name.toLowerCase().includes(q)) continue;
    let acts = c.actions;
    if (deck) acts = acts.filter(a => [...a.add, ...a.clear].some(m => belongs(m, deck)));
    if (pool) acts = acts.filter(a => [...a.add, ...a.clear].some(m => inPool(splitMark(m)[0])));
    if (view === "undone" && !acts.length) continue;
    if (view === "clear") { acts = acts.filter(a => a.clear.length); if (!acts.length) continue; }
    if (view === "pool" && !c.pool_card) continue;
    if (view === "buy" && !c.short) continue;
    if ((view === "all" || view === "pool" || view === "buy") && (deck || pool) && !c.batches.some(b => b.marks.some(m => (!deck || belongs(m, deck)) && inPool(splitMark(m)[0])))) continue;
    out.push({c, acts, deck});
  }
  return out;
}

// In one-mark-at-a-time mode a check-off paints (or clears) just that deck's mark.
// For a split deck that means its stripe plus any of its variant dots.
function stepFor(a, deck) {
  if (!deck) return {frm: a.from, to: a.to};
  const f = new Set(a.from);
  a.add.filter(m => belongs(m, deck)).forEach(m => f.add(m));
  a.clear.filter(m => belongs(m, deck)).forEach(m => f.delete(m));
  return {frm: a.from, to: [...f].sort((x, y) => x - y)};
}

function renderMark() {
  const all = S.cards, deckF = +$("#m-deck").value || 0;
  let need = 0, todo = 0, clears = 0, buy = 0, pool = 0;
  for (const c of all) { need += c.need; buy += c.short; if (c.pool_card) pool++;
    for (const a of c.actions) { todo += a.count; if (a.clear.length) clears += a.count; } }
  const doneN = Math.max(0, need - all.reduce((s, c) => s + c.actions.filter(a => a.to.length).reduce((t, a) => t + a.count, 0), 0));
  $("#m-meter").style.width = need ? `${(100 * doneN / need).toFixed(1)}%` : "0";
  $("#m-sub").textContent = need ? `${doneN} of ${need} sleeves marked correctly` : "Add a deck to start.";
  $("#m-stats").innerHTML = [[need, "sleeves needed"], [todo, "sleeves to touch"], [clears, "with marks to clear"], [pool, "shared cards"], [buy, "copies to buy"]]
    .map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("");
  $("#m-hint").textContent = deckF && S.byId[deckF] ? `Showing only ${S.byId[deckF].name}'s marks. Each check-off paints or clears just those.` : "";
  const rows = markFilter();
  S.shown = rows;
  if (!S.decks.length) { $("#m-list").innerHTML = `<div class="empty">No decks yet. Go to <a href="#decks">Decks</a> to import from Archidekt or paste a list.</div>`; return; }
  if (!rows.length) { $("#m-list").innerHTML = `<div class="empty">Nothing here. ${$("#m-view").value === "undone" ? "Every sleeve matches its decks." : ""}</div>`; return; }
  $("#m-list").innerHTML = rows.slice(0, 400).map(({c, acts, deck}, ri) => {
    const owned = c.owned == null ? "" : ` · own ${c.owned}`;
    const tags = [c.short ? `<span class="tag warn">buy ${c.short}</span>` : "", c.pool_card ? `<span class="tag">shared</span>` : "",
      c.location ? `<span class="tag">${esc(c.location)}</span>` : "", !acts.length ? `<span class="tag ok">done</span>` : ""].join("");
    const body = acts.map((a, ai) => {
      const st = stepFor(a, deck), keep = st.frm.filter(x => st.to.includes(x));
      const add = st.to.filter(x => !st.frm.includes(x)), clr = st.frm.filter(x => !st.to.includes(x));
      const what = !a.from.length ? "Fresh copy" : !a.to.length ? "Sleeve no longer used, clear it" : "Marked copy";
      const words = [add.length ? `paint <b>${fmt(add)}</b>` : "", clr.length ? `clear <b>${fmt(clr)}</b>` : ""].filter(Boolean).join(", ");
      return `<div class="act"><span class="n">×${a.count}</span><span class="what">${what}: ${words}</span>
        <button data-r="${ri}" data-a="${ai}">Done</button>
        <div class="edge">${sleeveSVG([...mk(keep, "keep"), ...mk(add, "add"), ...mk(clr, "clear")])}</div></div>`;
    }).join("");
    const bt = c.batches.length ? `<div class="batches">Target: ${c.batches.map(b => `${b.count}× [${fmt(b.marks)}]`).join(" · ")}</div>` : "";
    return `<article class="card${acts.length ? "" : " done"}"><div class="ch"><span class="cname">${esc(c.name)}</span><span class="meta">need ${c.need}${owned}</span>${tags}</div>${bt}${body}</article>`;
  }).join("") + (rows.length > 400 ? `<div class="empty">${rows.length - 400} more. Narrow the filters.</div>` : "");
}

async function checkOff(items, label) {
  const snaps = {};
  for (const it of items) { const c = S.cards.find(x => x.key === it.key); snaps[it.key] = c ? c.painted.flatMap(b => Array(b.count).fill(b.marks)) : []; }
  await api("/api/mark", {method: "POST", body: {items}});
  toast(label, async () => { for (const [key, physical] of Object.entries(snaps)) await api("/api/mark/set", {method: "POST", body: {key, physical}}); });
  load();
}
$("#m-list").addEventListener("click", e => {
  const b = e.target.closest("button[data-r]"); if (!b) return;
  const {c, acts, deck} = S.shown[+b.dataset.r], a = acts[+b.dataset.a], st = stepFor(a, deck);
  checkOff([{key: c.key, name: c.name, frm: st.frm, to: st.to, count: a.count}], `${c.name}: ${a.count} sleeve${a.count > 1 ? "s" : ""} checked off`);
});
$("#m-all").addEventListener("click", () => {
  const items = S.shown.flatMap(({c, acts, deck}) => acts.map(a => ({key: c.key, name: c.name, ...stepFor(a, deck), count: a.count})));
  if (!items.length) return toast("Nothing to check off");
  const b = $("#m-all");
  if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = `Confirm: ${items.length} rows`; setTimeout(() => { b.dataset.confirm = ""; b.textContent = "Mark all shown as done"; }, 4000); return; }
  b.dataset.confirm = ""; b.textContent = "Mark all shown as done";
  checkOff(items, `${items.length} rows checked off`);
});
function workText() {
  return S.shown.filter(r => r.acts.length).map(({c, acts, deck}) => acts.map(a => {
    const st = stepFor(a, deck), add = st.to.filter(x => !st.frm.includes(x)), clr = st.frm.filter(x => !st.to.includes(x));
    return `${a.count}x ${c.name}` + (add.length ? `  +${[...add].sort(markOrder).map(short).join(" +")}` : "") + (clr.length ? `  -${[...clr].sort(markOrder).map(short).join(" -")}` : "");
  }).join("\n")).join("\n");
}
async function copy(text, what) { try { await navigator.clipboard.writeText(text); toast(`${what} copied`); } catch { toast("Clipboard blocked by the browser"); } }
$("#m-copy").addEventListener("click", () => copy(workText(), "Work list"));
$("#m-print").addEventListener("click", () => {
  const legend = S.decks.map(d => `<tr><td><span class="dot" style="--c:${esc(d.color)}"></span>${esc(slotLabel(d.slot))}${poolInfo(d.pool).sideboard_marks ? ` / R${d.slot} SB` : ""}</td><td>${esc(d.name)}${(d.variants || []).map(v => `<br><span class="dot sm" style="--c:${esc(v.color)}"></span>B${v.pos}: ${esc(v.name)}`).join("")}</td><td>${esc(d.pool)}${d.dedicated ? " (dedicated)" : ""}</td></tr>`).join("");
  const rows = S.cards.filter(c => c.need).map(c => `<tr><td>${esc(c.name)}</td><td>${c.batches.map(b => `${b.count}× ${b.marks.map(id => { const i = markInfo(id); return i ? `<span class="dot${i.dot ? " sm" : ""}" style="--c:${esc(i.color)}"></span>${esc(i.label)}` : ""; }).join(" ")}`).join(" &nbsp;|&nbsp; ")}</td></tr>`).join("");
  $("#printout").innerHTML = `<h2>Edgemark marking guide</h2><table><tr><th>Slot</th><th>Deck</th><th>Pool</th></tr>${legend}</table><br><table><tr><th>Card</th><th>Copies and marks</th></tr>${rows}</table>`;
  window.print();
});
["#m-q", "#m-view", "#m-deck", "#m-pool"].forEach(s => $(s).addEventListener("input", renderMark));

/* ---------- DECKS ---------- */
function deckFace(d, big) {
  const marks = [...mk([`d${d.id}`], "add"), ...(poolInfo(d.pool).sideboard_marks ? mk([`d${d.id}.sb`], "keep") : []),
    ...mk((d.variants || []).map(v => `d${d.id}.v${v.idx}`), "add")];
  return sleeveSVG(marks, {big});
}
const canSync = d => d.variants.length ? d.variants.some(v => v.source === "archidekt") : d.source === "archidekt";
function renderDecks() {
  const ago = t => t ? new Date(t * 1000).toLocaleDateString() : "never";
  $("#d-list").innerHTML = S.decks.length ? S.decks.map(d => `
    <article class="deck${d.active ? "" : " off"}" style="--c:${esc(d.color)}">
      <div class="ch"><span class="slot">${esc(slotLabel(d.slot))}</span><span class="cname">${esc(d.name)}</span></div>
      <div class="meta">${esc(d.format || "No format")} · ${d.main_count} main${d.side_count ? ` + ${d.side_count} side` : ""}</div>
      <div class="chips"><span class="tag">${esc(d.pool)}</span>${d.dedicated ? `<span class="tag">dedicated</span>` : ""}${d.active ? "" : `<span class="tag warn">inactive</span>`}
        <span class="tag">${d.variants.length ? `${d.variants.length} variants` : d.source === "archidekt" ? `Archidekt · synced ${ago(d.synced)}` : d.source === "cubecobra" ? "CubeCobra" : "pasted list"}</span></div>
      ${d.variants.length ? `<div class="chips">${d.variants.map(v => `<span class="chip"><span class="dot sm" style="--c:${esc(v.color)}"></span>${esc(v.name)} <span class="meta">${v.main_count}</span></span>`).join("")}</div>` : ""}
      <div class="deckface">${deckFace(d)}<span class="meta">${poolInfo(d.pool).sideboard_marks ? `Main ${esc(slotLabel(d.slot))} · sideboard R${d.slot}` : `Mark ${esc(slotLabel(d.slot))}`}${d.variants.length ? ` · variants ${d.variants.map(v => "B" + v.pos).join(" ")}` : ""}</span></div>
      <div class="row">${canSync(d) ? `<button class="ghost" data-sync="${d.id}">Re-sync</button>` : ""}${d.source === "archidekt" && !d.variants.length ? `<a class="btn ghost" href="https://archidekt.com/decks/${encodeURIComponent(d.source_id)}">Open</a>` : ""}<button class="ghost" data-edit="${d.id}">Edit</button></div>
    </article>`).join("") : `<div class="empty">No decks yet. Use <b>Add decks</b> to import from Archidekt or CubeCobra, or paste a list.</div>`;
  renderTokens();
  renderPools();
}

/* ---------- POOLS ---------- */
function renderPools() {
  const pools = (S.pools || []).filter(p => p.decks);
  $("#p-list").innerHTML = pools.map(p => `<div class="card prow"><div><span class="cname">${esc(p.name)}</span> <span class="meta">${p.decks} of ${p.capacity} slots</span></div>
    <label class="chk"><input type="checkbox" data-pool="${esc(p.name)}" ${p.sideboard_marks ? "checked" : ""}> Sideboard marks on the right edge</label></div>`).join("") || `<div class="empty">Pools appear here once you add decks.</div>`;
}
$("#p-list").addEventListener("change", async e => {
  const c = e.target.closest("[data-pool]"); if (!c) return;
  try { await api(`/api/pools/${encodeURIComponent(c.dataset.pool)}`, {method: "PATCH", body: {sideboard_marks: c.checked}}); toast(c.checked ? "Sideboard marks on. Sideboard copies now show right-edge work." : "Sideboard marks off."); }
  catch (err) { c.checked = !c.checked; toast(err.message); }
  load();
});

/* ---------- TOKENS ---------- */
function renderTokens() {
  $("#t-list").innerHTML = S.tokens.length ? S.tokens.map(t => `<div class="card"><div class="ch"><span class="cname">${esc(t.full_name)}</span><span class="meta">${t.qty} per deck</span>
    <button class="ghost" data-tok="${t.id}" style="margin-left:auto">Edit</button></div><div class="chips" style="margin-top:6px">${t.deck_ids.map(id => chip(`d${id}`)).join("") || `<span class="meta">No decks yet</span>`}</div></div>`).join("")
    : `<div class="empty">No tokens. Add one if a deck needs tokens or other extras sleeved with it.</div>`;
}
let editingTok = null;
function openToken(t) {
  editingTok = t || null; $("#tk-err").textContent = "";
  $("#tk-title").textContent = t ? "Edit token" : "Add token";
  $("#tk-name").value = t ? t.name : ""; $("#tk-back").value = t ? t.back : ""; $("#tk-qty").value = t ? t.qty : 1;
  const sel = new Set(t ? t.deck_ids : []);
  $("#tk-decks").innerHTML = S.decks.map(d => `<label class="chk"><input type="checkbox" value="${d.id}" ${sel.has(d.id) ? "checked" : ""}> <span class="dot" style="--c:${esc(d.color)}"></span>${esc(slotLabel(d.slot))} ${esc(d.name)}</label>`).join("") || `<span class="meta">Add a deck first.</span>`;
  $("#tk-del").hidden = !t;
  $("#dlg-token").showModal();
}
$("#t-add").addEventListener("click", () => openToken(null));
$("#t-list").addEventListener("click", e => { const b = e.target.closest("[data-tok]"); if (b) openToken(S.tokens.find(t => t.id === +b.dataset.tok)); });
$("#tk-go").addEventListener("click", async () => {
  const body = {name: $("#tk-name").value.trim(), back: $("#tk-back").value.trim(), qty: Math.max(1, +$("#tk-qty").value || 1), deck_ids: $$("#tk-decks input:checked").map(i => +i.value)};
  try {
    if (editingTok) await api(`/api/tokens/${editingTok.id}`, {method: "PATCH", body}); else await api("/api/tokens", {method: "POST", body});
    $("#dlg-token").close(); toast("Token saved"); load();
  } catch (err) { $("#tk-err").textContent = err.message; }
});
$("#tk-del").addEventListener("click", async () => { await api(`/api/tokens/${editingTok.id}`, {method: "DELETE"}); $("#dlg-token").close(); toast("Token deleted. Its marks are listed under Marks to clear."); load(); });
$("#d-list").addEventListener("click", async e => {
  const s = e.target.closest("[data-sync]"), ed = e.target.closest("[data-edit]");
  if (s) { s.disabled = true; s.textContent = "Syncing…"; try { await api(`/api/decks/${s.dataset.sync}/sync`, {method: "POST"}); toast("Deck re-synced"); } catch (err) { toast(err.message); } load(); }
  if (ed) openDeck(+ed.dataset.edit);
});

let addMode = "arch";
$("#d-add").addEventListener("click", () => { $("#a-err").textContent = ""; $("#dlg-add").showModal(); });
$$("#dlg-add .seg button").forEach(b => b.addEventListener("click", () => {
  addMode = b.dataset.mode; $$("#dlg-add .seg button").forEach(x => x.classList.toggle("on", x === b));
  $$("#dlg-add [data-pane]").forEach(p => (p.hidden = p.dataset.pane !== addMode));
}));
$("#a-find").addEventListener("click", async () => {
  const u = $("#a-user").value.trim(); if (!u) return;
  $("#a-userdecks").textContent = "Looking…";
  try {
    const {decks} = await api(`/api/archidekt/user/${encodeURIComponent(u)}`);
    const have = new Set(S.decks.map(d => d.source_id));
    $("#a-userdecks").innerHTML = decks.map(d => `<label class="chk"><input type="checkbox" value="${esc(d.id)}" ${have.has(String(d.id)) ? "disabled" : ""}> ${esc(d.name)} <span class="meta">${esc(d.format)}${have.has(String(d.id)) ? " · already added" : ""}</span></label>`).join("");
  } catch (err) { $("#a-userdecks").textContent = err.message; }
});
function cubeBody() {
  const csv = $("#cb-csv").value.trim();
  return csv ? {csv, name: $("#cb-name").value.trim() || null} : {cube: $("#cb-ref").value.trim(), name: $("#cb-name").value.trim() || null};
}
$("#cb-load").addEventListener("click", async () => {
  $("#cb-info").textContent = "Loading…"; $("#cb-tags").innerHTML = "";
  try {
    const r = await api("/api/cubecobra/tags", {method: "POST", body: cubeBody()});
    if (!$("#cb-name").value) $("#cb-name").value = r.name;
    $("#cb-info").textContent = `${r.cards} cards, ${r.tags.length} tags, ${r.untagged} untagged.`;
    $("#cb-tags").innerHTML = r.tags.map(t => `<label class="chk"><input type="checkbox" value="${esc(t.tag)}"> ${esc(t.tag)} <span class="meta">${t.count}</span></label>`).join("") || `<span class="meta">No tags: import it as one deck.</span>`;
    if (!r.tags.length) $("#cb-whole").checked = true;
  } catch (err) { $("#cb-info").textContent = err.message; }
});
$("#p-file").addEventListener("change", async e => { const f = e.target.files[0]; if (!f) return; $("#p-text").value = await f.text(); if (!$("#p-name").value) $("#p-name").value = f.name.replace(/\.[^.]+$/, ""); });
$("#a-go").addEventListener("click", async () => {
  const base = {pool: $("#a-pool").value.trim() || "Main", dedicated: $("#a-ded").checked, format: $("#a-format").value.trim() || null};
  const btn = $("#a-go"); btn.disabled = true; $("#a-err").textContent = "";
  try {
    if (addMode === "cube") {
      const tags = $$("#cb-tags input:checked").map(i => i.value), whole = $("#cb-whole").checked;
      if (!whole && !tags.length) throw new Error("Tick at least one tag, or choose whole cube as one deck.");
      const pool = $("#a-pool").value.trim();
      const r = await api("/api/cubecobra/import", {method: "POST", body: {...cubeBody(), tags, whole, untagged: $("#cb-untagged").checked, pool: pool && pool !== "Main" ? pool : null}});
      $("#dlg-add").close(); toast(`${r.created.length} cube deck${r.created.length === 1 ? "" : "s"} added to ${r.pool}`);
      $("#cb-tags").innerHTML = ""; $("#cb-info").textContent = ""; $("#cb-csv").value = "";
    } else if (addMode === "arch") {
      const refs = [...$("#a-links").value.split(/\s+/).filter(Boolean), ...$$("#a-userdecks input:checked").map(i => i.value)];
      if (!refs.length) throw new Error("Paste a deck link or pick decks from the list.");
      if ($("#a-builds").checked) {
        if (refs.length < 2) throw new Error("Builds need at least two Archidekt decks.");
        btn.textContent = `Importing ${refs.length} builds…`;
        const r = await api("/api/decks/builds", {method: "POST", body: {refs, pool: base.pool, format: base.format, dedicated: base.dedicated}});
        $("#dlg-add").close(); toast(`Added ${r.name} with builds ${r.builds.join(", ")}`);
        $("#a-links").value = ""; $("#a-userdecks").innerHTML = ""; $("#a-builds").checked = false;
        btn.disabled = false; btn.textContent = "Add"; load(); return;
      }
      let ok = 0, fails = [];
      for (const r of refs) { btn.textContent = `Importing ${ok + fails.length + 1}/${refs.length}`; try { await api("/api/decks", {method: "POST", body: {...base, archidekt: r}}); ok++; } catch (err) { fails.push(`${r}: ${err.message}`); } }
      if (fails.length) { $("#a-err").textContent = fails.join(" · "); } else $("#dlg-add").close();
      toast(`${ok} deck${ok === 1 ? "" : "s"} imported`);
    } else {
      await api("/api/decks", {method: "POST", body: {...base, name: $("#p-name").value.trim() || null, decklist: $("#p-text").value}});
      $("#dlg-add").close(); toast("Deck added");
    }
    $("#a-links").value = ""; $("#p-text").value = ""; $("#p-name").value = ""; $("#a-userdecks").innerHTML = "";
  } catch (err) { $("#a-err").textContent = err.message; }
  btn.disabled = false; btn.textContent = "Add"; load();
});

let editing = null;
function fillSlotPicker() {
  const d = editing, pool = $("#e-pool").value.trim() || "Main", info = poolInfo(pool), samePool = pool === (d.pool || "Main");
  const used = new Map(S.decks.filter(x => (x.pool || "Main") === pool && x.id !== d.id).map(x => [x.slot, x.name]));
  const cap = (S.pools || []).some(p => p.name === pool) ? info.capacity : 2 * N();
  const want = samePool ? d.slot : 0;
  $("#e-slot").innerHTML = (samePool ? "" : `<option value="">Next free slot</option>`) + Array.from({length: cap}, (_, i) => i + 1).map(s =>
    `<option value="${s}" ${s === want ? "selected" : ""} ${used.has(s) ? "disabled" : ""}>${slotLabel(s)}${used.has(s) ? ` (${esc(used.get(s))})` : ""}</option>`).join("");
}
$("#e-pool").addEventListener("input", () => editing && fillSlotPicker());
async function openDeck(id) {
  const d = S.byId[id]; editing = d; $("#e-err").textContent = "";
  $("#e-title").textContent = d.name; $("#e-name").value = d.name; $("#e-pool").value = d.pool; $("#e-format").value = d.format || "";
  $("#e-color").value = /^#[0-9a-f]{6}$/i.test(d.color) ? d.color : "#e53935";
  $("#e-ded").checked = !!d.dedicated; $("#e-active").checked = !!d.active; $("#e-side").checked = !!d.include_side; $("#e-notes").value = d.notes || "";
  fillSlotPicker();
  renderVariantsEditor(d);
  $("#dlg-deck").showModal();
  await loadEditList();
}
function renderVariantsEditor(d) {
  const vs = d.variants || [];
  $("#e-varlist").innerHTML = vs.map(v => `<div class="vrow" data-v="${v.idx}"><input type="color" value="${esc(/^#[0-9a-f]{6}$/i.test(v.color) ? v.color : "#1e88e5")}" data-f="color" aria-label="Variant mark colour"><input value="${esc(v.name)}" data-f="name" aria-label="Variant name"><span class="meta">B${v.pos} · ${v.main_count}${v.side_count ? "+" + v.side_count : ""}${v.source === "archidekt" ? " · Archidekt" : ""}</span><button type="button" class="ghost" data-vdel="${v.idx}">Remove</button></div>`).join("");
  $("#e-varsum").textContent = vs.length ? "+ Add another variant" : "+ Split into variants";
  const taken = new Set([...S.decks.map(x => x.color), ...vs.map(v => v.color)].map(c => c.toLowerCase()));
  $("#ev-color").value = (S.settings.pens || []).find(c => !taken.has(c.toLowerCase())) || "#1e88e5";
  $("#e-listvar").hidden = !vs.length;
  $("#e-listvar").innerHTML = vs.map(v => `<option value="${v.idx}">${esc(v.name)}</option>`).join("");
  $("#e-listlbl").textContent = vs.length ? "Decklist of variant" : "Decklist";
}
async function loadEditList() {
  const v = editing.variants.length ? +$("#e-listvar").value : 0;
  $("#e-list").value = "Loading…";
  $("#e-list").value = await api(`/api/decks/${editing.id}/list${v ? `?variant=${v}` : ""}`);
  $("#e-list").dataset.orig = $("#e-list").value; $("#e-list").dataset.v = v;
}
$("#e-listvar").addEventListener("change", loadEditList);
$("#e-varlist").addEventListener("click", async e => {
  const b = e.target.closest("[data-vdel]"); if (!b) return;
  if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = "Confirm"; return; }
  await api(`/api/decks/${editing.id}/variants/${b.dataset.vdel}`, {method: "DELETE"});
  await load(); editing = S.byId[editing.id]; renderVariantsEditor(editing); await loadEditList();
  toast(editing.variants.length ? "Variant removed" : "Variant removed. This is a plain deck again.");
});
$("#ev-go").addEventListener("click", async () => {
  const body = {name: $("#ev-name").value.trim() || null, color: $("#ev-color").value, archidekt: $("#ev-arch").value.trim() || null, decklist: $("#ev-list").value || null};
  if (!body.archidekt && !body.decklist) { $("#e-err").textContent = "Give the new variant an Archidekt link or a pasted list."; return; }
  try {
    await api(`/api/decks/${editing.id}/variants`, {method: "POST", body});
    $("#ev-name").value = $("#ev-arch").value = $("#ev-list").value = ""; $("#e-varadd").open = false; $("#e-err").textContent = "";
    await load(); editing = S.byId[editing.id]; renderVariantsEditor(editing); await loadEditList();
    toast("Variant added");
  } catch (err) { $("#e-err").textContent = err.message; }
});
$("#e-save").addEventListener("click", async () => {
  const body = {name: $("#e-name").value.trim(), pool: $("#e-pool").value.trim() || "Main", format: $("#e-format").value.trim(), slot: +$("#e-slot").value || null,
    color: $("#e-color").value, dedicated: $("#e-ded").checked, active: $("#e-active").checked, include_side: $("#e-side").checked, notes: $("#e-notes").value};
  if ($("#e-list").value !== $("#e-list").dataset.orig) { body.decklist = $("#e-list").value; if (+$("#e-list").dataset.v) body.variant = +$("#e-list").dataset.v; }
  try {
    for (const row of $$("#e-varlist .vrow")) {
      const v = editing.variants.find(x => x.idx === +row.dataset.v), name = row.querySelector('[data-f="name"]').value.trim(), color = row.querySelector('[data-f="color"]').value;
      if (v && (name !== v.name || color !== v.color)) await api(`/api/decks/${editing.id}/variants/${v.idx}`, {method: "PATCH", body: {name, color}});
    }
    await api(`/api/decks/${editing.id}`, {method: "PATCH", body}); $("#dlg-deck").close(); toast("Deck saved"); load();
  }
  catch (err) { $("#e-err").textContent = err.message; }
});
$("#e-del").addEventListener("click", async () => {
  const b = $("#e-del");
  if (b.dataset.confirm !== "1") { b.dataset.confirm = "1"; b.textContent = "Click again to delete"; return; }
  b.dataset.confirm = ""; b.textContent = "Delete deck";
  await api(`/api/decks/${editing.id}`, {method: "DELETE"}); $("#dlg-deck").close();
  toast("Deck deleted. Its marks are listed under Marks to clear."); load();
});

/* ---------- COLLECTION ---------- */
function decksUsing(c) { return [...new Set(c.batches.flatMap(b => b.marks))].sort(markOrder); }
function renderCollection() {
  const q = $("#c-q").value.trim().toLowerCase(), loc = $("#c-loc").value, sh = $("#c-short").checked;
  const rows = S.cards.filter(c => (!q || c.name.toLowerCase().includes(q)) && (!loc || c.location === loc) && (!sh || c.short));
  const locs = S.settings.locations || [];
  $("#c-table tbody").innerHTML = rows.slice(0, 600).map(c => `<tr data-k="${esc(c.key)}">
    <td>${esc(c.name)}</td><td class="num">${c.need}</td>
    <td class="num"><input type="number" min="0" inputmode="numeric" data-f="owned" value="${c.owned ?? ""}" placeholder="?" aria-label="Owned"></td>
    <td class="num">${c.short ? `<span class="tag warn">${c.short}</span>` : ""}</td>
    <td><select data-f="location" aria-label="Location"><option value=""></option>${[...new Set([...locs, c.location].filter(Boolean))].map(l => `<option ${l === c.location ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></td>
    <td><div class="chips">${decksUsing(c).map(chip).join("")}</div></td></tr>`).join("") || `<tr><td colspan="6" class="meta">No cards match.</td></tr>`;
}
$("#c-table").addEventListener("change", async e => {
  const f = e.target.dataset.f; if (!f) return;
  const key = e.target.closest("tr").dataset.k;
  const body = f === "owned" ? (e.target.value === "" ? {clear_owned: true} : {owned: +e.target.value}) : {location: e.target.value};
  await api(`/api/cards/${encodeURIComponent(key)}`, {method: "PATCH", body}); load();
});
["#c-q", "#c-loc", "#c-short"].forEach(s => $(s).addEventListener("input", renderCollection));
$("#c-buy").addEventListener("click", () => copy(S.cards.filter(c => c.short).map(c => `${c.short} ${c.name}`).join("\n"), "Buy list"));
$("#c-import").addEventListener("click", () => { $("#ci-err").textContent = ""; $("#dlg-coll").showModal(); });
$("#ci-go").addEventListener("click", async () => {
  try { const r = await api("/api/collection", {method: "POST", body: {text: $("#ci-text").value, location: $("#ci-loc").value || null, mode: $("#ci-mode").value}});
    $("#dlg-coll").close(); $("#ci-text").value = ""; toast(`${r.count} cards imported`); load(); }
  catch (err) { $("#ci-err").textContent = err.message; }
});

/* ---------- SWAPS ---------- */
function swapBody() { return {deck_id: +$("#s-deck").value, board: $("#s-board").value, variant: $("#s-var-l").hidden ? 0 : +$("#s-var").value, out_name: $("#s-out").value.trim(), in_name: $("#s-in").value.trim(), qty: Math.max(1, +$("#s-qty").value || 1)}; }
function fillVariants() {
  const d = S.byId[+$("#s-deck").value], vs = d ? d.variants : [];
  $("#s-var-l").hidden = !vs.length;
  const keep = $("#s-var").value;
  $("#s-var").innerHTML = vs.map(v => `<option value="${v.idx}">${esc(v.name)}</option>`).join("");
  if (vs.some(v => String(v.idx) === keep)) $("#s-var").value = keep;
}
async function fillOut() {
  const id = +$("#s-deck").value; if (!id) return;
  fillVariants();
  const v = $("#s-var-l").hidden ? 0 : +$("#s-var").value;
  const txt = await api(`/api/decks/${id}/list${v ? `?variant=${v}` : ""}`);
  $("#s-out-list").innerHTML = txt.split("\n").map(l => l.replace(/^\d+\s+/, "")).filter(l => l && l !== "Sideboard").map(n => `<option value="${esc(n)}">`).join("");
}
$("#s-deck").addEventListener("change", fillOut);
$("#s-var").addEventListener("change", fillOut);
$("#s-form").addEventListener("submit", async e => {
  e.preventDefault(); const b = swapBody(); if (!b.out_name && !b.in_name) return toast("Name a card out, a card in, or both");
  try {
    const r = await api("/api/swaps/preview", {method: "POST", body: b});
    $("#s-preview").innerHTML = `<h2>${r.no_new_marks ? "No new paint needed" : "Marks for this swap"}</h2><div class="list">` + r.cards.map(c => `<article class="card"><div class="ch"><span class="cname">${esc(c.name)}</span></div><div class="batches">Target before: ${c.before.map(b => `${b.count}× [${fmt(b.marks)}]`).join(" · ") || "none"} → after: ${c.after.map(b => `${b.count}× [${fmt(b.marks)}]`).join(" · ") || "none"}</div>` +
      (c.actions.length ? c.actions.map(a => `<div class="act"><span class="n">×${a.count}</span><span class="what">${a.add.length ? `paint <b>${fmt(a.add)}</b>` : ""}${a.add.length && a.clear.length ? ", " : ""}${a.clear.length ? `clear <b>${fmt(a.clear)}</b>` : ""}${!a.from.length ? " on a fresh copy" : ""}</span><span></span><div class="edge">${sleeveSVG([...mk(a.from.filter(x => a.to.includes(x)), "keep"), ...mk(a.add, "add"), ...mk(a.clear, "clear")])}</div></div>`).join("") : `<p class="meta">Already right.</p>`) + `</article>`).join("") + `</div>`;
  } catch (err) { toast(err.message); }
});
$("#s-queue").addEventListener("click", async () => { const b = swapBody(); if (!b.out_name && !b.in_name) return; await api("/api/swaps", {method: "POST", body: b}); toast("Added to queue"); load(); });
function renderSwaps() {
  const sel = $("#s-deck").value;
  $("#s-deck").innerHTML = S.decks.map(d => `<option value="${d.id}">${esc(slotLabel(d.slot))} ${esc(d.name)}</option>`).join("");
  if (sel && S.byId[sel]) { $("#s-deck").value = sel; fillVariants(); } else fillOut();
  const q = S.swaps.filter(s => s.status === "queued"), done = S.swaps.filter(s => s.status !== "queued").slice(0, 15);
  const vname = s => { const d = S.byId[s.deck_id], v = d && s.variant ? d.variants.find(x => x.idx === s.variant) : null; return v ? ` (${esc(v.name)})` : ""; };
  const line = s => `${S.byId[s.deck_id] ? esc(S.byId[s.deck_id].name) : "Deleted deck"}${vname(s)}${s.board === "side" ? " sideboard" : ""}: ${s.out_name ? `−${s.qty} ${esc(s.out_name)}` : ""} ${s.in_name ? `+${s.qty} ${esc(s.in_name)}` : ""}`;
  $("#s-queue-list").innerHTML = (q.length ? q.map(s => `<div class="card"><div class="ch"><span class="cname">${line(s)}</span></div><div class="row" style="margin:8px 0 0"><button data-apply="${s.id}">Apply to list</button><button class="ghost" data-del="${s.id}">Remove</button></div></div>`).join("") : `<div class="empty">No queued swaps.</div>`)
    + (done.length ? `<h2>Applied</h2>` + done.map(s => `<div class="meta">${line(s)}${S.byId[s.deck_id]?.source === "archidekt" ? " · make the same change on Archidekt" : ""}</div>`).join("") : "");
}
$("#s-queue-list").addEventListener("click", async e => {
  const a = e.target.closest("[data-apply]"), d = e.target.closest("[data-del]");
  if (a) { await api(`/api/swaps/${a.dataset.apply}/apply`, {method: "POST"}); toast("Applied. Marks to change are now on the Mark sleeves tab."); load(); }
  if (d) { await api(`/api/swaps/${d.dataset.del}`, {method: "DELETE"}); load(); }
});

/* ---------- SLOTS ---------- */
async function renderSlots() {
  const pools = (S.pools || []).filter(p => p.decks);
  $("#sl-sub").textContent = `Slot 1 is nearest the ${S.settings.slot1_end === "bottom" ? "bottom" : "top"} of the card. Slot numbers count separately in each pool.`;
  $("#sl-map").innerHTML = pools.length ? pools.map(p => {
    const decks = S.decks.filter(d => (d.pool || "Main") === p.name);
    const marks = decks.flatMap(d => [...mk([`d${d.id}`], d.active ? "add" : "keep"), ...(p.sideboard_marks ? mk([`d${d.id}.sb`], "keep") : []), ...mk((d.variants || []).map(v => `d${d.id}.v${v.idx}`), "add")]);
    return `<div class="poolmap"><div>${sleeveSVG(marks, {big: true})}</div><div><h3>${esc(p.name)}</h3><p class="meta">${p.decks} of ${p.capacity} slots used${p.sideboard_marks ? " · right edge holds sideboard marks" : ""}</p><div class="chips">${decks.map(d => chip(`d${d.id}`)).join("")}</div></div></div>`;
  }).join("") : `<div class="empty">No decks yet.</div>`;
  try {
    const m = await api("/api/overlap");
    if (!m.decks.length) { $("#sl-overlap").innerHTML = ""; return; }
    $("#sl-overlap").innerHTML = `<table class="tbl matrix"><tr><th class="rowh"></th>${m.decks.map(id => `<th>${esc(slotLabel(S.byId[id].slot))} ${esc(S.byId[id].name)}</th>`).join("")}</tr>` +
      m.matrix.map((row, i) => `<tr><th class="rowh">${chip(`d${m.decks[i]}`)}</th>${row.map((v, j) => `<td style="background:color-mix(in srgb,var(--accent) ${i === j ? 0 : Math.min(60, v * 2)}%,transparent)">${i === j ? "–" : v}</td>`).join("")}</tr>`).join("") + `</table>`;
  } catch {}
}

/* ---------- SETTINGS ---------- */
function renderSettings() {
  const s = S.settings;
  $("#st-end").value = s.slot1_end; $("#st-spe").value = s.slots_per_edge; $("#st-nb").value = s.bottom_positions; $("#st-basics").checked = !!s.skip_basics;
  $("#st-locs").value = (s.locations || []).join("\n");
  $("#st-pens").innerHTML = (s.pens || []).map((p, i) => `<input type="color" value="${esc(p)}" data-i="${i}" aria-label="Pen ${i + 1}">`).join("");
}
$("#st-form").addEventListener("submit", async e => {
  e.preventDefault();
  await api("/api/settings", {method: "PUT", body: {values: {slot1_end: $("#st-end").value, slots_per_edge: Math.max(8, Math.min(40, +$("#st-spe").value || 30)), bottom_positions: Math.max(4, Math.min(24, +$("#st-nb").value || 20)),
    skip_basics: $("#st-basics").checked, locations: $("#st-locs").value.split("\n").map(x => x.trim()).filter(Boolean), pens: $$("#st-pens input").map(i => i.value)}}});
  toast("Settings saved"); load();
});
$("#st-restore").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  try { await api("/api/restore", {method: "POST", body: await f.text()}); toast("Backup restored"); load(); } catch (err) { toast(err.message); }
  e.target.value = "";
});

/* ---------- shell ---------- */
function render() {
  const pools = [...new Set(S.decks.map(d => d.pool))].sort();
  const keepSel = (sel, html) => { const v = $(sel).value; $(sel).innerHTML = html; if ([...$(sel).options].some(o => o.value === v)) $(sel).value = v; };
  keepSel("#m-deck", `<option value="">All decks</option>` + S.decks.map(d => `<option value="${d.id}">One deck: ${esc(d.name)} (${esc(d.pool)} ${esc(slotLabel(d.slot))})</option>`).join(""));
  keepSel("#m-pool", `<option value="">All pools</option>` + pools.map(p => `<option>${esc(p)}</option>`).join(""));
  const locs = [...new Set([...(S.settings.locations || []), ...S.cards.map(c => c.location).filter(Boolean)])];
  keepSel("#c-loc", `<option value="">All locations</option>` + locs.map(l => `<option>${esc(l)}</option>`).join(""));
  $("#pools").innerHTML = pools.map(p => `<option value="${esc(p)}">`).join("");
  $("#locs").innerHTML = locs.map(l => `<option value="${esc(l)}">`).join("");
  $("#all-cards").innerHTML = S.cards.slice(0, 3000).map(c => `<option value="${esc(c.name)}">`).join("");
  renderMark(); renderDecks(); renderCollection(); renderSwaps(); renderSettings();
  if (current() === "slots") renderSlots();
}
const VIEWS = ["mark", "decks", "collection", "swaps", "slots", "settings", "guide"];
const current = () => VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "mark";
function route() {
  const v = current();
  VIEWS.forEach(x => $(`#v-${x}`).classList.toggle("on", x === v));
  $$("#tabs a").forEach(a => a.classList.toggle("on", a.getAttribute("href") === `#${v}`));
  if (v === "slots") renderSlots();
}
addEventListener("hashchange", route);
route();
load().catch(err => { $("#m-list").innerHTML = `<div class="empty">Couldn't reach the server: ${esc(err.message)}</div>`; });
}
