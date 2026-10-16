// 4K AI WORKSTATION — masaüstü arayüzü. Tüm veri, preload köprüsü üzerinden Python arka ucundan gelir.
'use strict';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const TIER = { local: '🖥️ yerel', free: '🆓 ücretsiz', subscription: '💳 abonelik' };
const TASK_ICON = { 'yapılacak': '⬜', 'devam ediyor': '🔶', 'tamamlandı': '✅' };
const state = { view: 'desk', gear: 'dengeli', selectedProject: null, remoteRunning: false, jobs: new Set() };

// ---------------------------------------------------------------- yardımcılar
async function api(method, path, body) {
  const res = await window.fourk.api(method, path, body);
  if (!res.ok) throw new Error(res.data?.detail || `HTTP ${res.status}`);
  return res.data;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function md(text) {
  return DOMPurify.sanitize(marked.parse(String(text ?? ''), { gfm: true, breaks: false }));
}

function fmtTs(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

const money = (v, cur = 'TRY') =>
  new Intl.NumberFormat('tr-TR', { style: 'currency', currency: cur, maximumFractionDigits: 2 }).format(v || 0);

function toast(message, kind = 'info', ms = 4500) {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), ms);
}

function emptyRow(tbody, cols, text = 'Kayıt yok') {
  tbody.innerHTML = `<tr><td colspan="${cols}" class="empty">${esc(text)}</td></tr>`;
}

function confirmDialog(text) {
  return new Promise((resolve) => {
    const dlg = $('#confirm');
    $('#confirm-text').textContent = text;
    dlg.onclose = () => resolve(dlg.returnValue === 'yes');
    dlg.returnValue = '';
    dlg.showModal();
  });
}

// Uzun işler: kenar çubuğunda görünür ve düğmeyi kilitler.
async function job(name, fn, button) {
  state.jobs.add(name);
  renderJobs();
  if (button) button.disabled = true;
  try {
    return await fn();
  } catch (err) {
    toast(err.message, 'error', 8000);
    return undefined;
  } finally {
    state.jobs.delete(name);
    renderJobs();
    if (button) button.disabled = false;
  }
}

function renderJobs() {
  $('#jobs').innerHTML = state.jobs.size
    ? [...state.jobs].map((j) => `<li><span class="spinner"></span>${esc(j)}</li>`).join('')
    : '<li class="muted">Boşta</li>';
}

// Markdown içindeki bağlantılar sistem tarayıcısında açılır.
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href]');
  if (a && /^https?:/.test(a.href)) {
    e.preventDefault();
    window.fourk.openExternal(a.href);
  }
});

// ---------------------------------------------------------------- gezinme
const loaders = {
  desk: loadDesk,
  chat: loadChat,
  radar: async () => {},
  project: loadProjects,
  business: loadBusiness,
  sync: loadSync,
};

function show(view) {
  state.view = view;
  $$('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
  loaders[view]().catch((err) => toast(err.message, 'error'));
  const focus = { chat: '#chat-input', radar: '#radar-input', project: '#idea-input' }[view];
  if (focus) $(focus).focus();
}

$('#nav').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-view]');
  if (b) show(b.dataset.view);
});

document.addEventListener('keydown', (e) => {
  const idx = ['F1', 'F2', 'F3', 'F4', 'F5', 'F6'].indexOf(e.key);
  if (idx >= 0) {
    e.preventDefault();
    show(Object.keys(loaders)[idx]);
  }
});

// ---------------------------------------------------------------- vites
function renderGear() {
  $$('#gear button').forEach((b) => {
    b.classList.toggle('active', b.dataset.gear === state.gear);
    b.setAttribute('aria-checked', b.dataset.gear === state.gear);
  });
}

$('#gear').addEventListener('click', async (e) => {
  const b = e.target.closest('button[data-gear]');
  if (!b || b.dataset.gear === state.gear) return;
  try {
    await api('PUT', '/api/gear', { gear: b.dataset.gear });
    state.gear = b.dataset.gear;
    renderGear();
    toast(`Vites: ${b.textContent}`);
    if (state.view === 'desk') loadDesk();
  } catch (err) {
    toast(err.message, 'error');
  }
});

// ---------------------------------------------------------------- çalışma masası
async function loadDesk() {
  const o = await api('GET', '/api/overview');
  state.gear = o.gear;
  renderGear();
  $('#app-version').textContent = o.app.version;
  $('#title-version').textContent = o.app.version;
  const s = o.system;
  const gpus = s.gpus.map((g) => `${g.name} — ${g.vram_gb} GB VRAM`).join('<br>') || '—';
  $('#sysinfo').innerHTML = `
    <dt>Cihaz</dt><dd>${esc(s.host)}</dd>
    <dt>OS</dt><dd>${esc(s.os)}</dd>
    <dt>CPU</dt><dd>${esc(s.cpu)} (${s.cores} çekirdek)</dd>
    <dt>RAM</dt><dd>${s.ram_gb} GB</dd>
    <dt>GPU</dt><dd>${gpus}</dd>
    <dt>Ollama</dt><dd>${s.ollama_online ? '🟢' : '🔴'} ${s.ollama_models.length} model</dd>
    <dt>CLI Ajanları</dt><dd>${esc(s.cli_agents.join(', ') || '—')}</dd>
    <dt>Ücretsiz API</dt><dd>${esc(s.free_apis.join(', ') || '— (GROQ / OPENROUTER / GEMINI_API_KEY)')}</dd>`;

  const chips = (list) => list.map((p) => `<span class="chip">${esc(p)}</span>`).join(' → ') || '<span class="muted">—</span>';
  const pct = Math.round(o.quota_saved * 100);
  $('#routing').innerHTML = `
    <div class="muted">Vites</div><div><b>${esc(o.gears[o.gear])}</b></div><br>
    <div class="muted">Kota tasarrufu (30 gün): %${pct} çağrı yerel/ücretsiz</div>
    <div class="meter"><div style="width:${pct}%"></div></div>
    <div class="muted">Küçük iş rotası</div><div class="route">${chips(o.routes.small)}</div>
    <div class="muted">Büyük iş rotası</div><div class="route">${chips(o.routes.large)}</div>`;

  const pt = $('#providers');
  if (!o.providers.length) emptyRow(pt, 4, 'Sağlayıcı bulunamadı');
  else pt.innerHTML = o.providers.map((p) => `<tr>
      <td class="mono">${esc(p.name)}</td><td>${TIER[p.kind] || esc(p.kind)}</td>
      <td>${p.cooling ? `🧊 cooldown ${p.cooldown_min} dk` : '✅ hazır'}</td>
      <td class="muted">${esc((p.last_error || '').slice(0, 80))}</td></tr>`).join('');

  const ut = $('#usage');
  if (!o.usage.length) emptyRow(ut, 4, 'Henüz model çağrısı yok');
  else ut.innerHTML = o.usage.map((u) => `<tr><td>${fmtTs(u.ts)}</td><td class="mono">${esc(u.provider)}</td>
      <td class="num">${u.tokens_in}</td><td class="num">${u.tokens_out}</td></tr>`).join('');
}

$('#btn-rescan').addEventListener('click', (e) =>
  job('Donanım keşfi', async () => { await api('POST', '/api/discover'); await loadDesk(); toast('Tarama tamamlandı', 'ok'); }, e.currentTarget));

$('#btn-reset-cooldown').addEventListener('click', async () => {
  await api('POST', '/api/cooldowns/reset');
  toast('Tüm cooldown\'lar sıfırlandı', 'ok');
  loadDesk();
});

// ---------------------------------------------------------------- sohbet
let chatLoaded = false;

function addMessage(role, content, who) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  if (role === 'assistant') el.innerHTML = `<div class="who">🤖 ${esc(who || 'Asistan')}</div><div class="markdown">${md(content)}</div>`;
  else if (role === 'error') el.textContent = `⚠️ ${content}`;
  else el.textContent = content;
  $('#chat-log').append(el);
  el.scrollIntoView({ block: 'end' });
}

async function loadChat() {
  if (chatLoaded) return;
  chatLoaded = true;
  const history = await api('GET', '/api/chat');
  $('#chat-log').innerHTML = '';
  if (!history.length) {
    addMessage('assistant', '**4K AI ENGINE** hazır. Küçük işler yerelde, büyük mimari/kodlama işleri aboneliklerde çalışır.', '4K AI ENGINE');
  }
  history.forEach((m) => addMessage(m.role, m.content, m.provider));
}

$('#chat-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = $('#chat-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  addMessage('user', message);
  $('#chat-status').textContent = '🧠 Düşünüyor…';
  const r = await job('Sohbet yanıtı', () => api('POST', '/api/chat', { message }), e.submitter);
  if (!r) {
    $('#chat-status').textContent = '';
    addMessage('error', 'Yanıt alınamadı (ayrıntılar bildirimde).');
    return;
  }
  addMessage('assistant', r.text, r.label);
  const fb = r.attempts.length ? ` · ${r.attempts.length} yedeğe geçiş` : '';
  $('#chat-status').textContent = `${TIER[r.tier] || r.tier} · ${r.label} · ${r.elapsed.toFixed(1)} sn${fb}`;
});

$('#chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    $('#chat-form').requestSubmit();
  }
});

$('#chat-clear').addEventListener('click', async () => {
  await api('DELETE', '/api/chat');
  $('#chat-log').innerHTML = '';
  toast('Sohbet geçmişi temizlendi');
});

// ---------------------------------------------------------------- radar
$('#radar-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const mode = $('#radar-mode').value;
  const query = $('#radar-input').value.trim() || (mode === 'github' ? 'ai-agents' : '');
  if (!query) return toast('Arama sorgusu girin', 'error');
  const out = $('#radar-out');
  out.innerHTML = `<p><span class="spinner"></span>${mode === 'deep' ? 'Kaynaklar indiriliyor ve rapor sentezleniyor…' : 'Aranıyor…'}</p>`;
  const result = await job('Radar araması', async () => {
    if (mode === 'quick') return (await api('POST', '/api/radar/quick', { query })).report;
    if (mode === 'deep') return (await api('POST', '/api/radar/deep', { query })).report;
    const repos = await api('GET', `/api/radar/github?topic=${encodeURIComponent(query)}`);
    if (!repos.length) return `\`${query}\` için son 7 günde yeni proje bulunamadı.`;
    return `## 🐙 GitHub Trend: \`${query}\` (son 7 gün)\n\n| Depo | Yıldız | Dil | Tarih | Açıklama |\n|---|---|---|---|---|\n` +
      repos.map((r) => `| [${r.name}](${r.url}) | ⭐ ${r.stars} | ${r.lang} | ${r.created} | ${r.desc.replace(/\|/g, '/')} |`).join('\n');
  }, e.submitter);
  out.innerHTML = result ? md(result) : '<p class="neg">Arama başarısız.</p>';
});

// ---------------------------------------------------------------- project
async function loadProjects() {
  const list = await api('GET', '/api/projects');
  const tb = $('#projects');
  if (!list.length) emptyRow(tb, 4, 'Henüz proje yok — soldan bir fikir girin');
  else tb.innerHTML = list.map((p) => `<tr data-id="${p.id}" class="${p.id === state.selectedProject ? 'selected' : ''}">
      <td>${p.id}</td><td>${esc(p.name)}</td><td>${esc(p.status)}</td><td>${p.done}/${p.ticket_count}</td></tr>`).join('');
  if (!state.selectedProject && list.length) state.selectedProject = list[0].id;
  if (state.selectedProject) await showProject(state.selectedProject);
}

async function showProject(id) {
  state.selectedProject = id;
  $$('#projects tr').forEach((tr) => tr.classList.toggle('selected', Number(tr.dataset.id) === id));
  const p = await api('GET', `/api/projects/${id}`);
  $('#feasibility').innerHTML = md(p.feasibility_md || '') +
    `<p class="mono muted">📁 ${esc(p.repo_path)} <button class="small" data-open="${esc(p.repo_path)}">Klasörü Aç</button></p>`;
  const tb = $('#tickets');
  if (!p.tickets.length) emptyRow(tb, 4);
  else tb.innerHTML = p.tickets.map((t) => `<tr>
      <td>${t.id}</td><td>${esc(t.title)}<div class="muted">${esc(t.description || '')}</div></td>
      <td>${esc(t.status)}</td>
      <td>${t.status === 'tamamlandı' ? '' : `
        <button class="small" data-worktree="${t.id}">🌿 Worktree</button>
        ${t.worktree_path ? `<button class="small" data-close="${t.id}">✅ Kapat</button>` : ''}`}</td></tr>`).join('');
}

$('#projects').addEventListener('click', (e) => {
  const tr = e.target.closest('tr[data-id]');
  if (tr) showProject(Number(tr.dataset.id)).catch((err) => toast(err.message, 'error'));
});

$('#view-project').addEventListener('click', async (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.open) window.fourk.openPath(b.dataset.open);
  if (b.dataset.worktree) {
    const r = await job('Worktree açılıyor', () => api('POST', `/api/tickets/${b.dataset.worktree}/worktree`), b);
    if (r) {
      window.fourk.copy(r.path);
      toast(`🌿 Worktree hazır (yol panoya kopyalandı):\n${r.path}`, 'ok', 8000);
      await loadProjects();
    }
  }
  if (b.dataset.close) {
    const r = await job('Bilet kapatılıyor', () => api('POST', `/api/tickets/${b.dataset.close}/close`), b);
    if (r) {
      toast('✅ Bilet tamamlandı (dal korunuyor)', 'ok');
      await loadProjects();
    }
  }
});

$('#idea-go').addEventListener('click', async (e) => {
  const idea = $('#idea-input').value.trim();
  if (idea.length < 10) return toast('Fikrinizi biraz daha detaylı anlatın', 'error');
  $('#feasibility').innerHTML = '<p><span class="spinner"></span><b>Fikir analiz ediliyor…</b> Büyük iş olarak sınıflandırıldı; vitese göre en güçlü model kullanılıyor.</p>';
  const r = await job('Fikir analizi', () => api('POST', '/api/projects', { idea }), e.currentTarget);
  if (r) {
    $('#idea-input').value = '';
    state.selectedProject = r.id;
    toast(`✅ '${r.name}' oluşturuldu: ${r.tickets} bilet`, 'ok');
    await loadProjects();
  } else if (state.selectedProject) {
    await showProject(state.selectedProject);
  }
});

// ---------------------------------------------------------------- business
async function loadBusiness() {
  const [b, projects] = await Promise.all([api('GET', '/api/business'), api('GET', '/api/projects')]);
  const cur = Object.entries(b.summary.by_currency);
  $('#biz-summary').innerHTML = cur.length
    ? cur.map(([c, v]) => `<div class="stat"><div class="label">${esc(c)} · Net</div>
        <div class="value ${v.net >= 0 ? 'pos' : 'neg'}">${money(v.net, c)}</div>
        <div class="sub">Gelir ${money(v.gelir, c)} · Gider ${money(v.gider, c)}</div></div>`).join('')
    : '<div class="stat"><div class="label">Finansal Özet</div><div class="value">—</div><div class="sub">Henüz kayıt yok</div></div>';

  const sel = $('#l-project');
  const prev = sel.value;
  sel.innerHTML = '<option value="">Projesiz</option>' + projects.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  sel.value = prev;

  const lt = $('#ledger');
  if (!b.entries.length) emptyRow(lt, 7);
  else lt.innerHTML = b.entries.map((e) => `<tr><td>${fmtTs(e.ts)}</td><td>${esc(e.type)}</td>
      <td class="num ${e.type === 'gelir' ? 'pos' : 'neg'}">${e.type === 'gelir' ? '+' : '−'}${money(e.amount, e.currency)}</td>
      <td>${esc(e.category || '-')}</td><td>${esc(e.project || '-')}</td><td>${esc(e.note || '')}</td>
      <td><button class="small" data-del-ledger="${e.id}" title="Sil">🗑️</button></td></tr>`).join('');

  $('#tasks').innerHTML = b.tasks.length
    ? b.tasks.map((t) => `<li class="${t.status === 'tamamlandı' ? 'done' : ''}">
        <button class="status-btn" data-advance="${t.id}" title="Durumu ilerlet">${TASK_ICON[t.status] || '⬜'}</button>
        <span class="t">${esc(t.title)}</span><span class="muted">${esc(t.project || '')}</span>
        <button class="small" data-del-task="${t.id}" title="Sil">🗑️</button></li>`).join('')
    : '<li class="muted">Görev yok</li>';

  const bt = $('#budgets');
  if (!b.budgets.length) emptyRow(bt, 4);
  else bt.innerHTML = b.budgets.map((p) => `<tr><td>${esc(p.name)}</td><td class="num">${money(p.budget)}</td>
      <td class="num">${money(p.spent)}</td><td class="num">${money(p.earned)}</td></tr>`).join('');

  const tc = $('#token-costs');
  if (!b.token_costs.length) emptyRow(tc, 4);
  else tc.innerHTML = b.token_costs.map((c) => `<tr><td class="mono">${esc(c.provider)}</td><td>${esc(c.tier)}</td>
      <td class="num">${c.calls}</td><td class="num">${(c.tin || 0) + (c.tout || 0)}</td></tr>`).join('');
}

$('#ledger-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await api('POST', '/api/ledger', {
      type: $('#l-type').value,
      amount: Number($('#l-amount').value),
      currency: $('#l-currency').value,
      category: $('#l-category').value.trim() || 'genel',
      note: $('#l-note').value.trim(),
      project_id: $('#l-project').value ? Number($('#l-project').value) : null,
    });
  } catch (err) {
    return toast(err.message, 'error');
  }
  ['#l-amount', '#l-category', '#l-note'].forEach((s) => { $(s).value = ''; });
  toast('💰 Kayıt eklendi', 'ok');
  loadBusiness();
});

$('#task-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const title = $('#task-input').value.trim();
  if (!title) return;
  await api('POST', '/api/tasks', { title, project_id: state.selectedProject });
  $('#task-input').value = '';
  loadBusiness();
});

$('#view-business').addEventListener('click', async (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  try {
    if (b.dataset.delLedger) await api('DELETE', `/api/ledger/${b.dataset.delLedger}`);
    else if (b.dataset.advance) await api('POST', `/api/tasks/${b.dataset.advance}/advance`);
    else if (b.dataset.delTask) await api('DELETE', `/api/tasks/${b.dataset.delTask}`);
    else return;
    loadBusiness();
  } catch (err) {
    toast(err.message, 'error');
  }
});

// ---------------------------------------------------------------- sync
function renderSide(s) {
  const nodes = s.tailscale.nodes || [];
  $('#side-nodes').innerHTML = !s.tailscale.installed
    ? '<li class="muted">Tailscale kurulu değil</li>'
    : !s.tailscale.running
      ? '<li class="muted">Tailscale kapalı</li>'
      : nodes.map((n) => `<li><span class="dot ${n.online ? 'on' : ''}"></span>${esc(n.name)}${n.self ? ' <span class="muted">(bu cihaz)</span>' : ''}
          <span class="ip">${esc(n.ip)} · ${esc(n.os)}</span></li>`).join('');
  const active = s.tailscale.running || s.cloud === 'bağlı';
  const badge = $('#sync-badge');
  badge.textContent = active ? 'SYNC Aktif' : 'SYNC Pasif';
  badge.className = `badge ${active ? 'ok' : 'warn'}`;
  $('#side-sync').innerHTML = `
    Tailscale: ${s.tailscale.running ? '🟢' : '🔴'}<br>
    Google: ${s.cloud === 'bağlı' ? `🟢 ${esc(s.email)}` : `🔴 ${esc(s.cloud)}`}<br>
    Son yedek: ${s.last_backup ? fmtTs(s.last_backup) : 'hiç'}<br>
    API: ${s.remote_api.running ? '🟢 açık' : '⚫ kapalı'}`;
}

async function loadSync() {
  const s = await api('GET', '/api/sync');
  renderSide(s);
  $('#cloud').innerHTML = `
    <dt>Google Drive</dt><dd>${esc(s.cloud)} ${esc(s.email)}</dd>
    <dt>Yerel yedekler</dt><dd>${s.local_backups} adet <span class="mono muted">${esc(s.backup_dir)}</span></dd>
    <dt>Son yedek</dt><dd>${s.last_backup ? fmtTs(s.last_backup) : 'hiç'}</dd>
    <dt>Veritabanı</dt><dd class="mono">${esc(s.db_path)}</dd>`;
  state.remoteRunning = s.remote_api.running;
  $('#remote-toggle').textContent = s.remote_api.running ? '⏹️ Durdur' : '🌐 Başlat';
  $('#remote-info').innerHTML = s.remote_api.running
    ? `URL: <b>${esc(s.remote_api.url)}</b><br>Token: <b>${esc(s.remote_api.token)}</b><br>Başlık: Authorization: Bearer &lt;token&gt;`
    : '<span class="muted">Kapalı</span>';

  const nt = $('#nodes');
  const nodes = s.tailscale.nodes || [];
  if (!nodes.length) emptyRow(nt, 5, 'Tailscale cihazı yok');
  else nt.innerHTML = nodes.map((n) => `<tr><td>${esc(n.name)}${n.self ? ' ⭐' : ''}</td><td class="mono">${esc(n.ip)}</td>
      <td>${esc(n.os)}</td><td><span class="dot ${n.online ? 'on' : ''}"></span>${n.online ? 'çevrimiçi' : 'çevrimdışı'}</td>
      <td>${esc(n.last_seen)}</td></tr>`).join('');

  const lt = $('#sync-log');
  if (!s.log.length) emptyRow(lt, 4);
  else lt.innerHTML = s.log.map((r) => `<tr><td>${fmtTs(r.ts)}</td><td>${esc(r.action)}</td><td>${esc(r.status)}</td>
      <td class="muted">${esc((r.detail || '').slice(0, 100))}</td></tr>`).join('');

  const help = $('#sync-help');
  help.classList.toggle('hidden', !s.setup_help);
  help.innerHTML = s.setup_help ? md(s.setup_help) : '';
}

async function refreshSide() {
  try {
    renderSide(await api('GET', '/api/sync'));
  } catch {
    // kenar çubuğu yenilemesi sessizce başarısız olabilir
  }
}

$('#g-connect').addEventListener('click', async (e) => {
  toast('Tarayıcıda Google izin sayfası açılıyor…');
  const r = await job('Google girişi', () => api('POST', '/api/sync/google/connect'), e.currentTarget);
  if (r) toast(`✅ Google hesabı bağlandı: ${r.email}`, 'ok');
  loadSync();
});

$('#g-backup').addEventListener('click', async (e) => {
  const r = await job('Yedekleme', () => api('POST', '/api/sync/backup'), e.currentTarget);
  if (r) toast(`✅ Yedek alındı (${r.cloud ? 'yerel + ☁️ Google Drive' : 'yalnızca yerel'})`, 'ok');
  loadSync();
});

$('#g-restore').addEventListener('click', async (e) => {
  const ok = await confirmDialog('En yeni yedek geri yüklenecek. Mevcut veritabanı ve projeler klasörü değiştirilecek (önce otomatik "pre-restore" yedeği alınır). Devam edilsin mi?');
  if (!ok) return;
  const r = await job('Geri yükleme', () => api('POST', '/api/sync/restore'), e.currentTarget);
  if (r) {
    toast(`✅ ${r.source} yedek geri yüklendi: ${r.name}`, 'ok');
    chatLoaded = false;
    state.selectedProject = null;
  }
  loadSync();
});

$('#g-logout').addEventListener('click', async () => {
  await api('POST', '/api/sync/google/disconnect');
  toast('Google hesabı bağlantısı kaldırıldı');
  loadSync();
});

$('#remote-toggle').addEventListener('click', async (e) => {
  await job('Uzaktan erişim API', () => api('POST', state.remoteRunning ? '/api/sync/remote/stop' : '/api/sync/remote/start'), e.currentTarget);
  loadSync();
});

// ---------------------------------------------------------------- başlangıç
show('desk');
refreshSide();
setInterval(refreshSide, 30_000);
setInterval(() => { if (state.view === 'desk') loadDesk().catch(() => {}); }, 15_000);
