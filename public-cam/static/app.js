/* ─────────────────────────────────────────
   eyes-on — Frontend JavaScript
   ───────────────────────────────────────── */

let allCameras = [];
let eventSource = null;

// ── Tab Navigation ──────────────────────────────────────
function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${name}`).classList.add('active');
  document.getElementById(`nav-${name}`).classList.add('active');

  if (name === 'history') loadHistory();
}

// ── Radio Card Toggle ────────────────────────────────────
document.querySelectorAll('.radio-group').forEach(group => {
  group.querySelectorAll('.radio-card').forEach(card => {
    card.addEventListener('click', () => {
      group.querySelectorAll('.radio-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      card.querySelector('input').checked = true;
    });
  });
});

// ── Scan Control ─────────────────────────────────────────
function startScan() {
  const mode    = document.querySelector('#scan-mode .radio-card.active').dataset.value;
  const filter  = document.querySelector('#filter-mode .radio-card.active').dataset.value;
  const pages   = parseInt(document.getElementById('pages-input').value) || 3;
  const country = document.getElementById('country-select').value || null;

  // Reset
  allCameras = [];
  document.getElementById('results-grid').innerHTML = `
    <div class="empty-state" id="empty-state">
      <span class="empty-icon">👁</span>
      <p>Scanning...</p>
      <small>Live cameras will appear here as they are found.</small>
    </div>`;
  document.getElementById('counter-value').textContent = '0';
  document.getElementById('result-badge').textContent = '0';

  fetch('/api/start_scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, filter, pages, country })
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) { logLine('error', data.error); return; }
    setStatus('running', 'Scanning...');
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled  = false;
    logLine('success', `✓ Scan started — Mode: ${mode}, Filter: ${filter}, Pages: ${pages}${country ? ', Country: ' + country : ''}`);
    startSSE();
  })
  .catch(e => logLine('error', 'Failed to start scan: ' + e));
}

function stopScan() {
  fetch('/api/stop_scan', { method: 'POST' }).then(() => {
    logLine('warn', '⚠ Scan stopped by user.');
    setStatus('done', 'Stopped');
    resetButtons();
    if (eventSource) { eventSource.close(); eventSource = null; }
  });
}

function startSSE() {
  if (eventSource) eventSource.close();

  eventSource = new EventSource('/api/stream');

  eventSource.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    handleSSEMessage(msg);
  };

  eventSource.onerror = () => {
    logLine('error', 'Stream connection lost.');
    eventSource.close();
    resetButtons();
  };
}

function handleSSEMessage(msg) {
  switch (msg.event) {
    case 'init':
      break;
    case 'status':
      logLine('info', msg.data);
      break;
    case 'camera':
      addCameraCard(msg.data);
      updateCounters();
      break;
    case 'done':
      const stopped = msg.data?.stopped ? ' (stopped)' : '';
      logLine('success', `✓ Scan complete. Found ${msg.data?.total || 0} live cameras${stopped}.`);
      setStatus('done', `Done — ${msg.data?.total || 0} cameras`);
      resetButtons();
      if (eventSource) { eventSource.close(); eventSource = null; }
      break;
    case 'ping':
      break;
  }
}

// ── Camera Cards ─────────────────────────────────────────
function addCameraCard(cam) {
  allCameras.push(cam);

  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();

  const grid = document.getElementById('results-grid');
  const card = buildCamCard(cam, allCameras.length - 1);
  grid.appendChild(card);
}

function buildCamCard(cam, idx) {
  const typeBadge = getTypeBadge(cam.type);
  const isStream  = cam.type && cam.type.includes('STREAM');

  const card = document.createElement('div');
  card.className = 'cam-card';
  card.dataset.idx = idx;
  card.dataset.url = cam.url.toLowerCase();
  card.dataset.brand = (cam.brand || '').toLowerCase();
  card.dataset.location = (cam.location || '').toLowerCase();
  card.dataset.type = cam.type || '';

  card.innerHTML = `
    <div class="cam-preview" onclick="openModal(${idx})">
      <img
        src="${cam.url}"
        alt="Camera Feed"
        onerror="this.parentElement.innerHTML='<div class=\\'cam-preview-fallback\\'><span class=\\'big-icon\\'>📷</span><span>Stream Unavailable</span></div>'"
        loading="lazy"
      />
      <span class="cam-type-badge ${typeBadge.cls}">${typeBadge.label}</span>
    </div>
    <div class="cam-info" onclick="openModal(${idx})">
      <div class="cam-url" title="${cam.url}">${cam.url}</div>
      <div class="cam-meta">
        <div class="cam-meta-row"><span class="mi">🏷️</span><span>${cam.brand || 'Unknown Brand'}</span></div>
        <div class="cam-meta-row"><span class="mi">📍</span><span>${cam.location || 'Unknown Location'}</span></div>
        <div class="cam-meta-row"><span class="mi">🖥️</span><span>${cam.server || 'Unknown Server'}</span></div>
      </div>
    </div>
    <div class="cam-actions">
      <button class="cam-btn cam-btn-open" onclick="window.open('${cam.url}','_blank')">🔗 Open</button>
      <button class="cam-btn cam-btn-copy" onclick="copyUrl('${cam.url}', this)">📋 Copy URL</button>
    </div>`;

  return card;
}

function getTypeBadge(type) {
  if (!type) return { label: 'UNKNOWN', cls: 'badge-snapshot' };
  if (type.includes('STREAM'))   return { label: '● LIVE', cls: 'badge-stream' };
  if (type.includes('SNAPSHOT')) return { label: '📷 SNAPSHOT', cls: 'badge-snapshot' };
  if (type.includes('VIDEO'))    return { label: '🎥 VIDEO', cls: 'badge-video' };
  return { label: type, cls: 'badge-snapshot' };
}

function updateCounters() {
  const count = allCameras.length;
  document.getElementById('counter-value').textContent = count;
  document.getElementById('result-badge').textContent = count;
}

// ── Filtering ────────────────────────────────────────────
function filterCards() {
  const query   = document.getElementById('search-input').value.toLowerCase();
  const typeVal = document.getElementById('type-filter').value.toLowerCase();

  document.querySelectorAll('.cam-card').forEach(card => {
    const matchQuery = !query ||
      card.dataset.url.includes(query) ||
      card.dataset.brand.includes(query) ||
      card.dataset.location.includes(query);

    const matchType = !typeVal || card.dataset.type.toLowerCase().includes(typeVal);

    card.style.display = (matchQuery && matchType) ? '' : 'none';
  });
}

// ── Clear / Export ────────────────────────────────────────
function clearResults() {
  allCameras = [];
  document.getElementById('results-grid').innerHTML = `
    <div class="empty-state" id="empty-state">
      <span class="empty-icon">👁</span>
      <p>No cameras found yet.</p>
      <small>Start a scan to discover live camera feeds.</small>
    </div>`;
  document.getElementById('counter-value').textContent = '0';
  document.getElementById('result-badge').textContent = '0';
  logLine('muted', '— Results cleared.');
}

function exportResults() {
  if (!allCameras.length) { logLine('warn', 'No results to export.'); return; }
  const blob = new Blob([JSON.stringify(allCameras, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `scan_result_${Date.now()}.json`;
  a.click();
  logLine('success', `✓ Exported ${allCameras.length} cameras to JSON.`);
}

// ── Modal ─────────────────────────────────────────────────
function openModal(idx) {
  const cam = allCameras[idx];
  if (!cam) return;

  const isStream = cam.type && cam.type.includes('STREAM');

  document.getElementById('modal-content').innerHTML = `
    <div class="${isStream ? 'modal-preview-stream' : 'modal-preview'}">
      ${isStream
        ? `<img src="${cam.url}" style="max-width:100%;max-height:300px;object-fit:contain;" onerror="this.parentElement.innerHTML='<span style=\\'font-size:48px\\'>📷</span><span>Stream Unavailable</span>'" />`
        : `<img src="${cam.url}" alt="Camera Feed" onerror="this.parentElement.innerHTML='<span style=\\'font-size:48px\\'>📷</span><span>Image Unavailable</span>'" />`
      }
    </div>
    <h3 class="modal-title">📡 Camera Details</h3>
    <div class="modal-grid">
      <div class="modal-field full">
        <div class="modal-field-label">Stream URL</div>
        <div class="modal-field-value">${cam.url}</div>
      </div>
      <div class="modal-field">
        <div class="modal-field-label">Status</div>
        <div class="modal-field-value" style="color:var(--accent-3)">● ${cam.status || 'Live'}</div>
      </div>
      <div class="modal-field">
        <div class="modal-field-label">Type</div>
        <div class="modal-field-value">${cam.type || 'Unknown'}</div>
      </div>
      <div class="modal-field">
        <div class="modal-field-label">Brand</div>
        <div class="modal-field-value">${cam.brand || 'Unknown'}</div>
      </div>
      <div class="modal-field">
        <div class="modal-field-label">Server</div>
        <div class="modal-field-value">${cam.server || 'Unknown'}</div>
      </div>
      <div class="modal-field full">
        <div class="modal-field-label">Location</div>
        <div class="modal-field-value">📍 ${cam.location || 'Unknown'}</div>
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-primary" onclick="window.open('${cam.url}', '_blank')">🔗 Open in New Tab</button>
      <button class="btn btn-ghost" onclick="copyUrl('${cam.url}', this)">📋 Copy URL</button>
    </div>`;

  document.getElementById('modal-overlay').classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── History ───────────────────────────────────────────────
function loadHistory() {
  fetch('/api/history')
    .then(r => r.json())
    .then(files => {
      const list = document.getElementById('history-list');
      if (!files.length) {
        list.innerHTML = `<div class="empty-state"><span class="empty-icon">📂</span><p>No scan history found.</p></div>`;
        return;
      }
      list.innerHTML = files.map(f => `
        <div class="history-item" onclick="loadHistoryFile('${f.filename}')">
          <span class="history-file-icon">📄</span>
          <div class="history-file-info">
            <div class="history-file-name">${f.filename}</div>
            <div class="history-file-meta">${new Date(f.timestamp * 1000).toLocaleString()}</div>
          </div>
          <span class="history-count">${f.count}</span>
        </div>`).join('');
    });
}

function loadHistoryFile(filename) {
  fetch(`/api/history/${filename}`)
    .then(r => r.json())
    .then(cameras => {
      allCameras = cameras;
      const grid = document.getElementById('history-cameras');

      if (!cameras.length) {
        grid.innerHTML = `<div class="empty-state"><span class="empty-icon">📭</span><p>No cameras in this file.</p></div>`;
        return;
      }

      grid.innerHTML = '';
      cameras.forEach((cam, idx) => grid.appendChild(buildCamCard(cam, idx)));
    });
}

// ── Helpers ───────────────────────────────────────────────
function logLine(type, text) {
  const body = document.getElementById('terminal-body');
  const line = document.createElement('div');
  line.className = `terminal-line ${type}`;
  const prefixes = { success: '✓', error: '✗', warn: '⚠', info: '→', muted: '·', default: '>' };
  const prefix = prefixes[type] || prefixes.default;
  line.innerHTML = `<span class="t-prefix">${prefix}</span><span class="t-text">${text}</span>`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

function clearLog() {
  document.getElementById('terminal-body').innerHTML = `
    <div class="terminal-line muted"><span class="t-prefix">·</span><span class="t-text">Log cleared.</span></div>`;
}

function setStatus(state, text) {
  const dot  = document.getElementById('status-dot');
  const span = document.getElementById('status-text');
  dot.className = `status-dot ${state}`;
  span.textContent = text;
}

function resetButtons() {
  document.getElementById('btn-start').disabled = false;
  document.getElementById('btn-stop').disabled  = true;
}

function copyUrl(url, btn) {
  navigator.clipboard.writeText(url).then(() => {
    const orig = btn.textContent;
    btn.textContent = '✓ Copied!';
    setTimeout(() => btn.textContent = orig, 2000);
  });
}
