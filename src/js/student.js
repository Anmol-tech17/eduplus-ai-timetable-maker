/**
 * student.js — EduPlus Student Dashboard Logic
 * Mock data only. No real backend, solver, ML model, or authentication connected.
 */
(function () {
  "use strict";

// ─── AUTH GUARD ───────────────────────────────────────────────────────────────
const _studentUser = (() => {
  try {
    const u = JSON.parse(sessionStorage.getItem('eduplus_user') || 'null');
    if (!u || u.role !== 'student') { window.location.href = 'index.html'; return null; }
    return u;
  } catch (_) { window.location.href = 'index.html'; return null; }
})();
if (_studentUser) {
  document.getElementById('sidebar-username').textContent = _studentUser.name;
  document.getElementById('sidebar-avatar').textContent =
    _studentUser.name.split(' ').map(p => p[0]).join('').slice(0,2).toUpperCase();
}

const D = window.EduPlusData;
const { MOCK_TIMETABLE_VALID, SUBJECTS, ROOMS, TIME_SLOTS, DAYS, ENROLLMENT_GROUPS } = D;

// Student's context from mock user
const STUDENT_DIV  = _studentUser?.division || 'A';
const STUDENT_YEAR = _studentUser?.year || 3;
const STUDENT_BATCH = _studentUser?.batch || 'B1';
const STUDENT_ELECTIVE_GROUP = 'EG_CV'; // Sneha Patel is in CV group

const SUBJECT_MAP = {};
SUBJECTS.forEach(s => { SUBJECT_MAP[s.id] = s; });
const TEACHER_MAP_S = {};
D.TEACHERS.forEach(t => { TEACHER_MAP_S[t.id] = t; });
const ROOM_MAP_S = {};
ROOMS.forEach(r => { ROOM_MAP_S[r.id] = r; });

const LUNCH_SLOT = 'TS6';

let _liveStudentSessions = null;

async function initStudentLiveTimetable() {
  if (!window.EduPlusAPI) return;
  try {
    const isLive = await window.EduPlusAPI.isBackendLive();
    if (!isLive) return;

    const versions = await window.EduPlusAPI.getVersions({ limit: 10 });
    if (!versions || versions.length === 0) return;

    const targetVer = versions.find(v => v.status === 'published') || versions[0];
    const detail = await window.EduPlusAPI.getVersion(targetVer.id);

    if (detail.sessions && detail.sessions.length > 0) {
      _liveStudentSessions = detail.sessions.map(s => ({
        id: s.assignment_id,
        day: s.day_name,
        slot: `TS${s.slot_index || 1}`,
        slot_index: s.slot_index,
        subjectId: s.subject_id,
        subjectName: s.subject_name || s.subject_code || s.subject_id,
        subjectShort: s.subject_code || s.subject_name || s.subject_id,
        teacherId: s.teacher_id,
        teacherName: s.teacher_name || s.teacher_id,
        roomId: s.room_id,
        roomName: s.room_name || s.room_id,
        type: s.session_type,
        targetGroup: s.target_group_type === 'batch' ? `DIV_${STUDENT_YEAR}${STUDENT_DIV}/${STUDENT_BATCH}` : `DIV_${STUDENT_YEAR}${STUDENT_DIV}`,
      }));
      renderStudentGrid();
    }
  } catch (err) {
    console.warn('[Student Dashboard] Failed fetching live timetable:', err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initStudentLiveTimetable();
});
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  initStudentLiveTimetable();
}

// ─── PANEL NAVIGATION ─────────────────────────────────────────────────────────
const PANEL_TITLES = {
  'student-home':      'Overview',
  'student-timetable': 'My Timetable',
  'student-today':     "Today's Classes",
  'student-notices':   'Notices',
  'student-query':     'Submit Query',
};

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => { p.classList.add('hidden'); p.classList.remove('active'); });
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById(`panel-${name}`);
  const nav   = document.getElementById(`nav-${name}`);
  if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
  if (nav)   nav.classList.add('active');
  document.getElementById('topbar-title').textContent = PANEL_TITLES[name] || name;
  if (name === 'student-timetable') renderStudentGrid();
  if (name === 'student-today')     renderStudentToday();
  if (name === 'student-home')      renderStudentHome();
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

// ─── SESSION FILTER FOR STUDENT ───────────────────────────────────────────────
// Student sees: whole-division sessions (DIV_3A), their batch sessions (DIV_3A/B1),
// and their elective group (EG_CV).
function isSessionForStudent(session) {
  if (session.hidden) return false;
  const tg = session.targetGroup;
  if (!tg) return false;
  if (tg === `DIV_${STUDENT_YEAR}${STUDENT_DIV}`) return true;
  if (tg === `DIV_${STUDENT_YEAR}${STUDENT_DIV}/${STUDENT_BATCH}`) return true;
  if (tg === STUDENT_ELECTIVE_GROUP) return true;
  return false;
}

function sessionCSSForStudent(session) {
  if (session.targetGroup === STUDENT_ELECTIVE_GROUP) return 'session-elective';
  if (session.targetGroup?.includes('/')) return 'session-practical';
  if (session.type === 'tutorial') return 'session-tutorial';
  return 'session-lecture';
}

function targetGroupBadge(session) {
  const tg = session.targetGroup;
  if (tg === STUDENT_ELECTIVE_GROUP) return `<span style="font-size:9px;background:rgba(139,92,246,0.15);color:#5b21b6;border-radius:3px;padding:1px 4px;">CV</span>`;
  if (tg?.includes('/')) return `<span style="font-size:9px;background:rgba(16,185,129,0.15);color:#065f46;border-radius:3px;padding:1px 4px;">B1</span>`;
  return `<span style="font-size:9px;background:rgba(34,85,164,0.1);color:#1a3a6e;border-radius:3px;padding:1px 4px;">Div A</span>`;
}

// ─── STUDENT TIMETABLE GRID ───────────────────────────────────────────────────
function renderStudentGrid() {
  const grid = document.getElementById('student-tt-grid');
  if (!grid) return;

  const baseSessions = _liveStudentSessions || MOCK_TIMETABLE_VALID.sessions;
  const mySessions = baseSessions.filter(isSessionForStudent);

  // Build session map
  const sessionMap = {};
  DAYS.forEach(day => { sessionMap[day] = {}; TIME_SLOTS.forEach(ts => { sessionMap[day][ts.id] = []; }); });
  mySessions.forEach(s => { if (sessionMap[s.day]) sessionMap[s.day][s.slot].push(s); });

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
      const slotSessions = sessionMap[day][ts.id] || [];
      if (slotSessions.length === 0) {
        html += `<div class="tt-cell" role="cell" style="background: var(--gray-50);"></div>`;
        return;
      }
      const inner = slotSessions.map(s => {
        const subj    = SUBJECT_MAP[s.subjectId];
        const teacher = TEACHER_MAP_S[s.teacherId];
        const room    = ROOM_MAP_S[s.roomId];
        const css     = sessionCSSForStudent(s);
        return `<div class="tt-session ${css}" tabindex="0" aria-label="${subj?.shortName} ${day} ${ts.label}">
          <div class="tt-session-type">${s.type === 'practical' ? '⚗ Lab' : s.type === 'tutorial' ? '✏ Tut' : '📖 Lec'}</div>
          <div class="tt-session-code">${subj?.shortName || s.subjectId} ${targetGroupBadge(s)}</div>
          <div class="tt-session-teacher">${teacher?.shortName || ''}</div>
          <div class="tt-session-room">${room?.name || s.roomId}</div>
        </div>`;
      }).join('');
      html += `<div class="tt-cell" role="cell">${inner}</div>`;
    });
  });
  grid.innerHTML = html;
}

// ─── STUDENT TODAY (Wednesday) ────────────────────────────────────────────────
function renderStudentToday() {
  const container = document.getElementById('student-today-list');
  if (!container) return;
  const todaySessions = MOCK_TIMETABLE_VALID.sessions
    .filter(s => s.day === 'Wednesday' && isSessionForStudent(s))
    .sort((a, b) => TIME_SLOTS.findIndex(t => t.id === a.slot) - TIME_SLOTS.findIndex(t => t.id === b.slot));

  container.innerHTML = todaySessions.map(s => {
    const subj    = SUBJECT_MAP[s.subjectId];
    const teacher = TEACHER_MAP_S[s.teacherId];
    const room    = ROOM_MAP_S[s.roomId];
    const ts      = TIME_SLOTS.find(t => t.id === s.slot);
    const groupLabel = s.targetGroup === STUDENT_ELECTIVE_GROUP ? '(CV Elective)' : s.targetGroup?.includes('/') ? `(Batch ${STUDENT_BATCH})` : '(Division A)';
    return `
      <div class="today-class-item">
        <div class="today-class-time">${ts?.label || s.slot}</div>
        <div class="today-class-info">
          <div class="today-class-name">${subj?.name || s.subjectId} <span style="font-size: var(--text-xs); color: var(--gray-500);">${groupLabel}</span></div>
          <div class="today-class-sub">${s.type === 'practical' ? '⚗ Lab Practical · ' : '📖 ' + s.type.charAt(0).toUpperCase() + s.type.slice(1) + ' · '}${room?.name || s.roomId} · ${teacher?.shortName || ''}</div>
        </div>
        <span class="badge ${s.type === 'practical' ? 'badge-success' : s.targetGroup === STUDENT_ELECTIVE_GROUP ? 'badge-neutral' : 'badge-brand'}" style="${s.targetGroup === STUDENT_ELECTIVE_GROUP ? 'background:#f3e8ff;color:#5b21b6;' : ''}">${s.type}</span>
      </div>`;
  }).join('');
}

// ─── STUDENT HOME — OVERVIEW ──────────────────────────────────────────────────
function renderStudentHome() {
  renderStudentHomeSessions();
  renderStudentSubjects();
}

function renderStudentHomeSessions() {
  const container = document.getElementById('student-home-today');
  if (!container) return;
  const todaySessions = MOCK_TIMETABLE_VALID.sessions
    .filter(s => s.day === 'Wednesday' && isSessionForStudent(s))
    .sort((a, b) => TIME_SLOTS.findIndex(t => t.id === a.slot) - TIME_SLOTS.findIndex(t => t.id === b.slot))
    .slice(0, 4);
  container.innerHTML = todaySessions.map(s => {
    const subj = SUBJECT_MAP[s.subjectId];
    const ts   = TIME_SLOTS.find(t => t.id === s.slot);
    const room = ROOM_MAP_S[s.roomId];
    return `
      <div class="today-class-item">
        <div class="today-class-time">${ts?.label || s.slot}</div>
        <div class="today-class-info">
          <div class="today-class-name">${subj?.shortName || s.subjectId}</div>
          <div class="today-class-sub">${room?.name || s.roomId}</div>
        </div>
        <span class="badge ${s.type === 'practical' ? 'badge-success' : 'badge-brand'}" style="font-size:9px;">${s.type}</span>
      </div>`;
  }).join('');
}

function renderStudentSubjects() {
  const container = document.getElementById('student-subjects-list');
  if (!container) return;
  // Year 3 subjects plus elective
  const studentSubjects = SUBJECTS.filter(s => s.year === STUDENT_YEAR);
  container.innerHTML = studentSubjects.map(s => {
    const isMyElective = s.id === 'SUB305'; // CV
    const isOtherElective = s.elective && !isMyElective;
    return `
      <div style="display:flex; align-items:center; justify-content:space-between; padding: 6px 0; border-bottom: 1px solid var(--gray-100);">
        <div>
          <div style="font-size: var(--text-sm); font-weight: 600; color: ${isOtherElective ? 'var(--gray-400)' : 'var(--gray-900)'};">${s.name}</div>
          <div style="font-size: var(--text-xs); color: var(--gray-400);">${s.code} &bull; ${s.credits}</div>
        </div>
        ${isMyElective ? `<span class="badge badge-neutral" style="background:#f3e8ff;color:#5b21b6;">Your Elective</span>` : 
          isOtherElective ? `<span class="badge badge-neutral" style="opacity:0.5;">Other Elective</span>` :
          `<span class="badge badge-brand">Enrolled</span>`}
      </div>`;
  }).join('');
}

// ─── QUERY FORM ───────────────────────────────────────────────────────────────
let _studentQueries = [...D.DEMO_STUDENT_QUERIES];

const sqForm = document.getElementById('student-query-form');
if (sqForm) {
  sqForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const text = document.getElementById('sq-text').value.trim();
    const cat  = document.getElementById('sq-category').value;
    if (!text) { showToast('Please enter your question.', 'error'); return; }

    const newQuery = {
      id: `SQ${Date.now()}`,
      submittedBy: _studentUser?.studentId || 'STU2301045',
      submitterName: _studentUser?.name || 'Sneha Patel',
      query: text,
      category: cat,
      status: 'pending',
      submittedAt: new Date().toISOString(),
      mockNote: 'Query solving via ML model is planned for a future phase.',
    };
    _studentQueries.unshift(newQuery);

    document.getElementById('sq-success').classList.remove('hidden');
    sqForm.reset();
    renderQueryHistory();
  });
}

function renderQueryHistory() {
  const container = document.getElementById('sq-history');
  if (!container || _studentQueries.length === 0) return;
  container.innerHTML = `
    <div style="font-size: var(--text-xs); font-weight: 700; color: var(--gray-500); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">Your Queries</div>
    ${_studentQueries.map(q => `
      <div style="padding: 8px 0; border-bottom: 1px solid var(--gray-100);">
        <div style="display:flex; justify-content: space-between; align-items:flex-start; gap: 8px;">
          <div style="font-size: var(--text-xs); color: var(--gray-700); line-height: 1.5; flex:1;">${q.query}</div>
          <span class="status-pill status-pending" style="flex-shrink:0; font-size: 9px;">
            <span class="status-dot"></span> Pending
          </span>
        </div>
        <div style="font-size: 10px; color: var(--gray-400); margin-top: 4px;">
          ${new Date(q.submittedAt).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}
          &bull; <em>${q.mockNote || 'Automated ML responses not yet available.'}</em>
        </div>
      </div>`).join('')}`;
}

// ─── KEYBOARD NAV ─────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('keypress', e => { if (e.key === 'Enter' || e.key === ' ') item.click(); });
});

// ─── INIT ─────────────────────────────────────────────────────────────────────
renderStudentHome();
renderStudentGrid();
renderStudentToday();
renderQueryHistory();

  // ─── EXPOSE TO WINDOW ────────────────────────────────────────────────────────
  window.showPanel = showPanel;
  window.signOut = signOut;
  window.showToast = showToast;
  window.renderStudentHome = renderStudentHome;
  window.renderStudentGrid = renderStudentGrid;
  window.renderStudentToday = renderStudentToday;
  window.renderQueryHistory = renderQueryHistory;
})();
