// ClawShield Dashboard — SSE client, event rendering, proxy activity log

const MAX_EVENTS = 200;
const MAX_ACTIVITY = 50;

let eventSource = null;
let blockMode = true;
let events = [];
let activityLog = [];

const counters = { total: 0, injection: 0, blocked: 0, tool_calls: 0 };

// --- DOM refs ---
const feed = document.getElementById('event-feed');
const activityEl = document.getElementById('activity-log');
const connDot = document.getElementById('conn-dot');
const countTotal = document.getElementById('count-total');
const countThreats = document.getElementById('count-threats');
const countBlocked = document.getElementById('count-blocked');
const countTools = document.getElementById('count-tools');
const blockBtn = document.getElementById('block-btn');
const blockStatus = document.getElementById('block-status');
const clearBtn = document.getElementById('clear-btn');

// --- SSE ---
function connect() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/events');

  eventSource.onopen = () => {
    connDot.className = 'connection-dot connected';
  };

  eventSource.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'PING') return;
      handleEvent(ev);
    } catch (err) {
      console.error('SSE parse error', err);
    }
  };

  eventSource.onerror = () => {
    connDot.className = 'connection-dot disconnected';
    setTimeout(connect, 3000);
  };
}

function handleEvent(ev) {
  events.unshift(ev);
  if (events.length > MAX_EVENTS) events.pop();

  updateCounters(ev);
  renderEventCard(ev, true);

  if (ev.type === 'LLM_RESPONSE') {
    addActivityEntry(ev);
  }
}

function updateCounters(ev) {
  counters.total++;
  if (ev.type === 'INJECTION_PROBE' || ev.type === 'INJECTION_BLOCKED') counters.injection++;
  if (ev.type === 'INJECTION_BLOCKED' || ev.type === 'TOOL_BLOCKED') counters.blocked++;
  if (ev.type === 'TOOL_CALL') counters.tool_calls++;

  countTotal.textContent = counters.total;
  countThreats.textContent = counters.injection;
  countBlocked.textContent = counters.blocked;
  countTools.textContent = counters.tool_calls;
}

// --- Event card rendering ---
const TYPE_LABELS = {
  LLM_REQUEST: 'LLM Request',
  LLM_RESPONSE: 'LLM Response',
  TOOL_CALL: 'Tool Call',
  TOOL_BLOCKED: 'Tool Blocked',
  INJECTION_PROBE: 'Injection Detected',
  INJECTION_BLOCKED: 'Injection Blocked',
  CREDENTIAL_LEAK: 'Credential Leak',
  RATE_LIMIT_HIT: 'Rate Limited',
};

function renderEventCard(ev, prepend = false) {
  const empty = feed.querySelector('.empty-state');
  if (empty) empty.remove();

  const card = document.createElement('div');
  card.className = `event-card severity-${ev.severity}`;

  const time = ev.timestamp ? ev.timestamp.split('T')[1]?.replace('Z', '') : '';
  const label = TYPE_LABELS[ev.type] || ev.type;

  let body = '';
  const d = ev.data || {};

  if (ev.type === 'LLM_REQUEST') {
    body = `Provider: <strong>${d.provider || '?'}</strong> · ${d.message_count || 0} msgs · ${d.tool_count || 0} tools`;
    if (d.last_user_message) body += `<br><span style="color:var(--text)">${esc(d.last_user_message.slice(0, 80))}</span>`;
  } else if (ev.type === 'LLM_RESPONSE') {
    body = `Provider: <strong>${d.provider || '?'}</strong> · ${d.latency_ms || 0}ms · HTTP ${d.status || 200}`;
  } else if (ev.type === 'TOOL_CALL') {
    body = `Tool: <strong>${d.tool || '?'}</strong>`;
    const args = d.args || {};
    const argStr = Object.entries(args).map(([k, v]) => `${k}=${String(v).slice(0, 40)}`).join(', ');
    if (argStr) body += ` · ${esc(argStr)}`;
    if (d.source === 'audit_log') body += ' <span style="color:var(--text-muted);font-size:10px">[audit]</span>';
  } else if (ev.type === 'TOOL_BLOCKED') {
    body = `Tool: <strong>${d.tool || '?'}</strong> · ${esc((d.error || '').slice(0, 100))}`;
  } else if (ev.type === 'INJECTION_PROBE' || ev.type === 'INJECTION_BLOCKED') {
    const patterns = (d.patterns || []).slice(0, 3).join(', ');
    body = `Patterns: <strong>${esc(patterns)}</strong>`;
  } else if (ev.type === 'CREDENTIAL_LEAK') {
    body = `Provider: ${d.provider || '?'} · ${d.note || ''}`;
  } else {
    body = JSON.stringify(d).slice(0, 120);
  }

  const snippet = d.snippet ? `<div class="event-snippet">${esc(d.snippet.slice(0, 200))}</div>` : '';

  card.innerHTML = `
    <div class="event-header">
      <span class="event-type">${label}</span>
      <span class="event-time">${esc(time)}</span>
    </div>
    <div class="event-body">${body}${snippet}</div>
  `;

  if (prepend) {
    feed.insertBefore(card, feed.firstChild);
  } else {
    feed.appendChild(card);
  }
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// --- Proxy activity log ---
function addActivityEntry(ev) {
  const d = ev.data || {};
  activityLog.unshift({
    time: ev.timestamp ? ev.timestamp.split('T')[1]?.replace('Z', '') : '',
    provider: d.provider || '?',
    msgs: d.message_count || 0,
    latency: d.latency_ms || 0,
    status: d.status || 200,
    snippet: d.last_user_message || '',
  });
  if (activityLog.length > MAX_ACTIVITY) activityLog.pop();
  renderActivityLog();
}

function renderActivityLog() {
  if (!activityLog.length) return;
  activityEl.innerHTML = activityLog.map(e => `
    <div class="proxy-entry">
      <span class="proxy-time">${esc(e.time)}</span>
      <span class="proxy-provider">${esc(e.provider)}</span>
      <span class="proxy-msgs">${e.msgs} msgs</span>
      <span class="proxy-snippet">${esc(e.snippet.slice(0, 60))}</span>
      <span class="proxy-latency ${e.status >= 400 ? 'proxy-status-err' : 'proxy-status-ok'}">${e.latency}ms</span>
    </div>
  `).join('');
}

// --- Controls ---
clearBtn.addEventListener('click', () => {
  feed.innerHTML = '<div class="empty-state"><div class="icon">🛡</div><p>Events will appear here</p></div>';
  events = [];
  activityLog = [];
  counters.total = 0; counters.injection = 0; counters.blocked = 0; counters.tool_calls = 0;
  countTotal.textContent = '0';
  countThreats.textContent = '0';
  countBlocked.textContent = '0';
  countTools.textContent = '0';
  activityEl.innerHTML = '<div class="no-activity">No proxy traffic yet</div>';
});

blockBtn.addEventListener('click', async () => {
  blockMode = !blockMode;
  blockBtn.classList.toggle('active', blockMode);
  blockBtn.textContent = blockMode ? '🔒 Blocking ON' : '🔓 Blocking OFF';
  if (blockStatus) blockStatus.textContent = blockMode ? 'ON' : 'OFF';
  try {
    await fetch(`/settings/block-injections?enabled=${blockMode}`, { method: 'POST' });
  } catch (e) {
    console.error('Failed to toggle block mode', e);
  }
});

// --- Init ---
connect();

fetch('/stats').then(r => r.json()).then(data => {
  const c = data.counts || {};
  counters.total = c.total || 0;
  counters.injection = c.injection || 0;
  counters.blocked = c.blocked || 0;
  counters.tool_calls = c.tool_calls || 0;
  countTotal.textContent = counters.total;
  countThreats.textContent = counters.injection;
  countBlocked.textContent = counters.blocked;
  countTools.textContent = counters.tool_calls;

  if (data.block_injections !== undefined) {
    blockMode = data.block_injections;
    blockBtn.classList.toggle('active', blockMode);
    blockBtn.textContent = blockMode ? '🔒 Blocking ON' : '🔓 Blocking OFF';
    if (blockStatus) blockStatus.textContent = blockMode ? 'ON' : 'OFF';
  }

  const kernelBadge = document.getElementById('kernel-badge');
  if (kernelBadge && data.hardening) {
    const h = data.hardening;
    if (h.landlock_active) {
      kernelBadge.textContent = '🔒 Landlock ON';
      kernelBadge.style.color = 'var(--green)';
      kernelBadge.style.borderColor = 'var(--green)';
    } else if (h.seatbelt_active) {
      kernelBadge.textContent = '🔒 Seatbelt ON';
      kernelBadge.style.color = 'var(--green)';
      kernelBadge.style.borderColor = 'var(--green)';
    } else {
      const reason = h.landlock_reason || h.seatbelt_reason || 'inactive';
      kernelBadge.textContent = `⚠ Kernel: ${reason}`;
      kernelBadge.style.color = 'var(--yellow)';
      kernelBadge.style.borderColor = 'var(--yellow)';
    }
    kernelBadge.title = `Platform: ${h.platform} | no_new_privs: ${h.no_new_privs}`;
  }
}).catch(() => {});
