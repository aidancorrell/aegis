// ClawShield Dashboard — SSE client, event rendering, chat

const MAX_EVENTS = 200;
const MAX_LLM_LOG = 20;

let eventSource = null;
let blockMode = false;
let events = [];
let llmLog = [];

const counters = { total: 0, injection: 0, blocked: 0, tool_calls: 0 };

// --- DOM refs ---
const feed = document.getElementById('event-feed');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const llmLogEl = document.getElementById('llm-log-entries');
const connDot = document.getElementById('conn-dot');
const countTotal = document.getElementById('count-total');
const countThreats = document.getElementById('count-threats');
const countBlocked = document.getElementById('count-blocked');
const countTools = document.getElementById('count-tools');
const blockBtn = document.getElementById('block-btn');
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
    addLlmLogEntry(ev);
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
  PING: 'Ping',
};

function renderEventCard(ev, prepend = false) {
  // Remove empty state if present
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

// --- LLM log ---
function addLlmLogEntry(ev) {
  const d = ev.data || {};
  const entry = { provider: d.provider || '?', latency: d.latency_ms || 0, status: d.status || 200 };
  llmLog.unshift(entry);
  if (llmLog.length > MAX_LLM_LOG) llmLog.pop();
  renderLlmLog();
}

function renderLlmLog() {
  llmLogEl.innerHTML = llmLog.map(e => `
    <div class="llm-entry">
      <span class="provider">${esc(e.provider)}</span>
      <span class="latency">${e.latency}ms</span>
      <span class="msgs">HTTP ${e.status}</span>
    </div>
  `).join('');
}

// --- Chat ---
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;

  appendMessage('user', text);
  const thinking = appendMessage('thinking', '<span class="thinking-dots"><span>•</span><span>•</span><span>•</span></span>');

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    thinking.remove();
    appendMessage('assistant', data.reply || data.detail || 'No response');
  } catch (err) {
    thinking.remove();
    appendMessage('assistant', `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

function appendMessage(role, content) {
  const msg = document.createElement('div');
  msg.className = `message ${role}`;
  if (role === 'thinking') {
    msg.innerHTML = content;
  } else {
    msg.textContent = content;
  }
  chatMessages.appendChild(msg);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msg;
}

// --- Controls ---
clearBtn.addEventListener('click', () => {
  feed.innerHTML = '<div class="empty-state"><div class="icon">🛡</div><p>Events will appear here</p></div>';
  events = [];
  llmLog = [];
  counters.total = 0; counters.injection = 0; counters.blocked = 0; counters.tool_calls = 0;
  countTotal.textContent = '0';
  countThreats.textContent = '0';
  countBlocked.textContent = '0';
  countTools.textContent = '0';
  llmLogEl.innerHTML = '';
});

blockBtn.addEventListener('click', async () => {
  blockMode = !blockMode;
  blockBtn.classList.toggle('active', blockMode);
  blockBtn.textContent = blockMode ? '🔒 Block ON' : '🔓 Block OFF';
  try {
    await fetch(`/settings/block-injections?enabled=${blockMode}`, { method: 'POST' });
  } catch (e) {
    console.error('Failed to toggle block mode', e);
  }
});

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

// --- Init ---
connect();

// Fetch initial stats
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

  // Update mode badge
  const modeBadge = document.getElementById('mode-badge');
  if (modeBadge) {
    modeBadge.textContent = data.mode === 'builtin' ? 'Built-in Engine' : 'Proxy Mode';
    modeBadge.className = `status-badge ${data.mode}`;
  }
}).catch(() => {});
