/**
 * teacher.js — EduPlus Teacher Dashboard Logic
 * Mock data only. No real backend, solver, or authentication.
 */
(function () {
  "use strict";

// ─── AUTH GUARD ───────────────────────────────────────────────────────────────
const _teacherUser = (() => {
  try {
    const u = JSON.parse(sessionStorage.getItem('eduplus_user') || 'null');
    if (!u || u.role !== 'teacher') { window.location.href = 'index.html'; return null; }
    return u;
  } catch (_) { window.location.href = 'index.html'; return null; }
})();
if (_teacherUser) {
  document.getElementById('sidebar-username').textContent = _teacherUser.name;
  document.getElementById('sidebar-avatar').textContent =
    _teacherUser.name.split(' ').map(p => p[0]).join('').slice(0,2).toUpperCase();
}

const D = window.EduPlusData;
const { MOCK_TIMETABLE_VALID, TEACHERS, SUBJECTS, ROOMS, TIME_SLOTS, DAYS, DEMO_REQUESTS } = D;

const TEACHER_ID = _teacherUser?.teacherId || 'TCH005';
const TEACHER    = TEACHERS.find(t => t.id === TEACHER_ID);
const SUBJECT_MAP = {};
SUBJECTS.forEach(s => { SUBJECT_MAP[s.id] = s; });
const ROOM_MAP = {};
ROOMS.forEach(r => { ROOM_MAP[r.id] = r; });

const LUNCH_SLOT = 'TS6';
const DAYS_ORDER = DAYS;

// ─── PANEL NAVIGATION ─────────────────────────────────────────────────────────
const PANEL_TITLES = {
  'my-timetable':  'My Timetable',
  'today':         "Today's Classes",
  'submit-request': 'Submit Request',
  'my-requests':   'My Requests',
  'teacher-query': 'Submit Query',
  'notifications': 'Notifications',
};

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => { p.classList.add('hidden'); p.classList.remove('active'); });
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById(`panel-${name}`);
  const nav   = document.getElementById(`nav-${name}`);
  if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
  if (nav)   nav.classList.add('active');
  document.getElementById('topbar-title').textContent = PANEL_TITLES[name] || name;
  if (name === 'my-timetable') renderTeacherGrid('all');
  if (name === 'today')        renderTodaySessions();
  if (name === 'my-requests')  renderMyRequests();
  if (name === 'notifications') renderNotifications();
}
function signOut() {
  sessionStorage.removeItem('eduplus_user');
  window.location.href = 'index.html';
}

// ─── TOAST ───────────────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 350); }, 4000);
}

// ─── TEACHER TIMETABLE GRID ──────────────────────────────────────────────────
let _teacherViewFilter = 'all';

function setTeacherView(filter) {
  _teacherViewFilter = filter;
  ['all','practical','lecture'].forEach(f => {
    const btn = document.getElementById(`view-${f}-btn`);
    if (btn) {
      btn.className = `btn btn-sm ${f === filter ? 'btn-primary' : 'btn-secondary'}`;
    }
  });
  renderTeacherGrid(filter);
}

function renderTeacherGrid(filter) {
  const grid = document.getElementById('teacher-tt-grid');
  if (!grid) return;

  // Get sessions for this teacher
  const mySessions = MOCK_TIMETABLE_VALID.sessions.filter(s => {
    if (s.teacherId !== TEACHER_ID || s.hidden) return false;
    if (filter === 'practical' && s.type !== 'practical') return false;
    if (filter === 'lecture'   && s.type !== 'lecture')   return false;
    return true;
  });

  // Build map
  const sessionMap = {};
  DAYS.forEach(day => { sessionMap[day] = {}; TIME_SLOTS.forEach(ts => { sessionMap[day][ts.id] = null; }); });
  mySessions.forEach(s => { if (sessionMap[s.day]) sessionMap[s.day][s.slot] = s; });

  let html = '';
  html += `<div class="tt-header-cell" role="columnheader">Time</div>`;
  DAYS.forEach(d => { html += `<div class="tt-header-cell" role="columnheader">${d}</div>`; });

  TIME_SLOTS.forEach(ts => {
    const isLunch = ts.id === LUNCH_SLOT;
    html += `<div class="tt-time-cell" role="rowheader">${ts.label}</div>`;
    DAYS.forEach(day => {
      if (isLunch) {
        html += `<div class="tt-cell lunch-cell" role="cell"><div class="tt-lunch-label">🍽 Lunch</div></div>`;
        return;
      }
      const s = sessionMap[day]?.[ts.id];
      if (!s) {
        html += `<div class="tt-cell" role="cell" style="background: var(--gray-50);"></div>`;
        return;
      }
      const subj = SUBJECT_MAP[s.subjectId];
      const room = ROOM_MAP[s.roomId];
      const css  = s.type === 'practical' ? 'session-practical' : 'session-lecture';
      html += `<div class="tt-cell" role="cell">
        <div class="tt-session ${css}" tabindex="0" aria-label="${subj?.shortName} ${s.type} ${day} ${ts.label}">
          <div class="tt-session-type">${s.type === 'practical' ? '⚗ Lab' : '📖 Lecture'}</div>
          <div class="tt-session-code">${subj?.shortName || s.subjectId}</div>
          <div class="tt-session-teacher">${s.targetGroup?.includes('/') ? s.targetGroup.split('/')[1] : s.targetGroup}</div>
          <div class="tt-session-room">${room?.name || s.roomId}</div>
        </div>
      </div>`;
    });
  });
  grid.innerHTML = html;
}

// ─── TODAY'S SESSIONS (Wednesday for demo) ────────────────────────────────────
function renderTodaySessions() {
  const container = document.getElementById('today-sessions-list');
  if (!container) return;
  document.getElementById('today-date-label').textContent =
    new Date().toLocaleDateString('en-IN', { weekday:'long', day:'numeric', month:'long', year:'numeric' });

  const todaySessions = MOCK_TIMETABLE_VALID.sessions
    .filter(s => s.day === 'Wednesday' && s.teacherId === TEACHER_ID && !s.hidden)
    .sort((a, b) => TIME_SLOTS.findIndex(t => t.id === a.slot) - TIME_SLOTS.findIndex(t => t.id === b.slot));

  if (todaySessions.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-title">No sessions today</div></div>`;
    return;
  }

  container.innerHTML = todaySessions.map(s => {
    const subj = SUBJECT_MAP[s.subjectId];
    const room = ROOM_MAP[s.roomId];
    const ts   = TIME_SLOTS.find(t => t.id === s.slot);
    return `
      <div class="today-class-item">
        <div class="today-class-time">${ts?.label || s.slot}</div>
        <div class="today-class-info">
          <div class="today-class-name">${subj?.name || s.subjectId}</div>
          <div class="today-class-sub">
            ${s.type === 'practical' ? `⚗ Lab Practical · ${s.targetGroup?.split('/')[1] || ''} · ` : `📖 ${s.type.charAt(0).toUpperCase() + s.type.slice(1)} · `}
            ${room?.name || s.roomId}
          </div>
        </div>
        <span class="badge ${s.type === 'practical' ? 'badge-success' : 'badge-brand'}">${s.type}</span>
      </div>`;
  }).join('');
}

// ─── REQUEST FORM ─────────────────────────────────────────────────────────────
let _myRequests = DEMO_REQUESTS.filter(r => r.submittedBy === TEACHER_ID);

const reqForm = document.getElementById('request-form');
if (reqForm) {
  reqForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const type    = document.getElementById('req-type').value;
    const session = document.getElementById('req-session').value;
    const reason  = document.getElementById('req-reason').value.trim();
    const errorDiv = document.getElementById('req-form-error');
    const errText  = document.getElementById('req-error-text');
    errorDiv.classList.add('hidden');

    if (!type || !session || reason.length < 20) {
      errorDiv.classList.remove('hidden');
      errText.textContent = !type ? 'Please select a request type.'
        : !session ? 'Please select an affected session.'
        : 'Please provide a more detailed reason (minimum 20 characters).';
      return;
    }

    const newReq = {
      id: `REQ${Date.now()}`,
      type,
      submittedBy: TEACHER_ID,
      submitterName: TEACHER?.name || 'Prof. Arjun Mehta',
      subject: `${type.charAt(0).toUpperCase() + type.slice(1)}: ${session}`,
      details: reason,
      status: 'pending',
      submittedAt: new Date().toISOString(),
      priority: 'normal',
    };
    _myRequests.unshift(newReq);
    reqForm.reset();
    showToast('Request submitted. Admin will review shortly. (Simulated — no backend call made.)', 'success');
    renderMyRequests();
  });
}

function renderMyRequests() {
  const card = document.getElementById('my-requests-card');
  if (!card) return;
  if (_myRequests.length === 0) {
    card.innerHTML = `<div class="card-body"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-title">No requests submitted yet</div></div></div>`;
    return;
  }
  card.innerHTML = _myRequests.map(r => `
    <div class="request-item">
      <div class="request-dot dot-${r.status}"></div>
      <div style="flex:1;">
        <div style="display:flex; gap:6px; align-items:center;">
          <span class="badge ${r.type === 'reschedule' ? 'badge-brand' : r.type === 'substitution' ? 'badge-info' : 'badge-error'}">${r.type}</span>
        </div>
        <div class="request-subject">${r.subject}</div>
        <div class="request-details">${r.details}</div>
        <div class="request-meta">
          <span>🕒 ${new Date(r.submittedAt).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</span>
        </div>
        <div style="margin-top: 8px;">
          <span class="status-pill ${r.status === 'approved' ? 'status-published' : r.status === 'rejected' ? 'status-diagnostic' : 'status-pending'}">
            <span class="status-dot"></span> ${r.status.charAt(0).toUpperCase() + r.status.slice(1)}
          </span>
        </div>
      </div>
    </div>`).join('');
}

// ─── QUERY FORM ───────────────────────────────────────────────────────────────
const tqForm = document.getElementById('teacher-query-form');
if (tqForm) {
  tqForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const text = document.getElementById('tq-text').value.trim();
    if (!text) return;
    document.getElementById('tq-success').classList.remove('hidden');
    document.getElementById('tq-text').value = '';
    document.getElementById('tq-category').value = '';
  });
}

// ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
function renderNotifications() {
  const card = document.getElementById('notifications-card');
  if (!card) return;
  card.innerHTML = `
    <div class="card-header"><div class="card-title">Notifications</div><span class="badge badge-error">1 new</span></div>
    <div class="card-body">
      <div class="request-item">
        <div class="request-dot dot-approved"></div>
        <div>
          <div class="request-type-badge badge badge-success">Approved</div>
          <div class="request-subject">Substitution Request — Math for AI, Thursday</div>
          <div class="request-details">Your substitution request has been approved. Prof. Swati Joshi (TCH012) will cover the session on Thursday 08:00–09:00.</div>
          <div class="request-meta"><span>🕒 19 Oct 2026, 16:30</span><span>Approved by Dr. Priya Sharma</span></div>
        </div>
      </div>
    </div>`;
}

// ─── KEYBOARD NAV ─────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('keypress', e => { if (e.key === 'Enter' || e.key === ' ') item.click(); });
});

// ─── INIT ─────────────────────────────────────────────────────────────────────
renderTeacherGrid('all');
renderTodaySessions();
renderMyRequests();
renderNotifications();

  // ─── EXPOSE TO WINDOW ────────────────────────────────────────────────────────
  window.showPanel = showPanel;
  window.signOut = signOut;
  window.showToast = showToast;
  window.setTeacherView = setTeacherView;
  window.renderTeacherGrid = renderTeacherGrid;
  window.renderTodaySessions = renderTodaySessions;
  window.renderMyRequests = renderMyRequests;
  window.renderNotifications = renderNotifications;
})();
