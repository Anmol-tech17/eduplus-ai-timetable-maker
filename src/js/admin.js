/**
 * admin.js — EduPlus Admin Dashboard Logic
 * Fully integrated with FastAPI backend and Google OR-Tools CP-SAT scheduling engine.
 * Gracefully falls back to demo mock data if the backend is offline.
 */
(function () {
  "use strict";

  // ─── AUTH GUARD ─────────────────────────────────────────────────────────────
  const _adminUser = (() => {
    try {
      const u = JSON.parse(sessionStorage.getItem('eduplus_user') || 'null');
      if (!u || u.role !== 'admin') { window.location.href = 'index.html'; return null; }
      return u;
    } catch (_) { window.location.href = 'index.html'; return null; }
  })();
  if (_adminUser) {
    const usernameEl = document.getElementById('sidebar-username');
    const avatarEl = document.getElementById('sidebar-avatar');
    if (usernameEl) usernameEl.textContent = _adminUser.name;
    if (avatarEl) {
      avatarEl.textContent = _adminUser.name
        .split(' ')
        .map(p => p[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();
    }
  }

  // ─── DATA & FALLBACK ALIASES ────────────────────────────────────────────────
  const D = window.EduPlusData || {};
  const {
    TEACHERS = [],
    ROOMS = [],
    SUBJECTS = [],
    ENROLLMENT_GROUPS = [],
    MOCK_TIMETABLE_VALID = { id: 'mock-valid', sessions: [], conflicts: [] },
    MOCK_TIMETABLE_CONFLICT = { id: 'mock-conflict', sessions: [], conflicts: [] },
    DEMO_REQUESTS = [],
    TIME_SLOTS = [
      { id: "TS1", label: "08:00 – 09:00", index: 1 },
      { id: "TS2", label: "09:00 – 10:00", index: 2 },
      { id: "TS3", label: "10:00 – 11:00", index: 3 },
      { id: "TS4", label: "11:00 – 12:00", index: 4 },
      { id: "TS5", label: "12:00 – 13:00", index: 5 },
      { id: "TS6", label: "13:00 – 14:00", index: 6 },
      { id: "TS7", label: "14:00 – 15:00", index: 7 },
      { id: "TS8", label: "15:00 – 16:00", index: 8 },
      { id: "TS9", label: "16:00 – 17:00", index: 9 },
      { id: "TS10", label: "17:00 – 18:00", index: 10 },
    ],
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    SUMMARY_STATS = { totalDivisions: 10, totalTeachers: 12, totalRooms: 17, pendingRequests: 2, totalSessions: 27 },
  } = D;

  // ─── LIVE STATE ─────────────────────────────────────────────────────────────
  let _isBackendLive = false;
  let _departments = [];
  let _academicYears = [];
  let _divisions = [];
  let _subjects = [];
  let _teachers = [];
  let _rooms = [];
  let _versions = [];
  let _activeVersion = null; // Full TimetableVersionDetail
  let _selectedCandidateId = null;
  let _pinnedSessionIds = new Set();

  let _currentFilterTeacher = '';
  let _currentFilterRoom = '';
  let _currentFilterYear = '3';
  let _currentFilterDivision = 'A';

  const LUNCH_SLOT = 'TS6';

  // ─── PANEL NAVIGATION ───────────────────────────────────────────────────────
  const PANEL_TITLES = {
    overview: 'Dashboard',
    timetable: 'Timetable Grid',
    generate: 'Generate & Validate',
    conflicts: 'Conflict Report',
    compare: 'Version Comparison & Localized Repair',
    teachers: 'Teachers',
    rooms: 'Rooms & Labs',
    requests: 'Request Inbox',
  };

  function showPanel(name) {
    document.querySelectorAll('.panel').forEach(p => {
      p.classList.add('hidden');
      p.classList.remove('active');
    });
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const panel = document.getElementById(`panel-${name}`);
    const navEl = document.getElementById(`nav-${name}`);
    if (panel) {
      panel.classList.remove('hidden');
      panel.classList.add('active');
    }
    if (navEl) navEl.classList.add('active');

    const titleEl = document.getElementById('topbar-title');
    if (titleEl) titleEl.textContent = PANEL_TITLES[name] || name;

    // Render panel content
    if (name === 'timetable') renderCurrentTimetableGrid();
    if (name === 'conflicts') renderConflictPanel();
    if (name === 'compare') renderComparePanel();
    if (name === 'teachers') renderTeachers();
    if (name === 'rooms') renderRooms();
    if (name === 'requests') renderRequests();
    if (name === 'generate') renderGeneratePanel();
  }

  // ─── SIGN OUT ───────────────────────────────────────────────────────────────
  function signOut() {
    sessionStorage.removeItem('eduplus_user');
    window.location.href = 'index.html';
  }

  // ─── TOAST NOTIFICATIONS ────────────────────────────────────────────────────
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');
    const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 350);
    }, 4500);
  }

  // ─── MODAL ──────────────────────────────────────────────────────────────────
  function openModal(title, bodyHTML) {
    const titleEl = document.getElementById('modal-title');
    const bodyEl = document.getElementById('modal-body');
    const modalEl = document.getElementById('session-modal');
    if (titleEl) titleEl.textContent = title;
    if (bodyEl) bodyEl.innerHTML = bodyHTML;
    if (modalEl) modalEl.classList.add('open');
  }
  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('open');
  }

  // ─── BACKEND CONNECTIVITY & BOOTSTRAP ────────────────────────────────────────
  async function initBackendConnection() {
    const statusBadge = document.getElementById('backend-status-badge');
    const banner = document.getElementById('backend-connection-banner');
    const bannerText = document.getElementById('connection-banner-text');
    const bannerIcon = document.getElementById('connection-banner-icon');

    try {
      const isLive = await window.EduPlusAPI.isBackendLive();
      if (isLive) {
        _isBackendLive = true;
        if (statusBadge) {
          statusBadge.className = 'badge badge-live';
          statusBadge.innerHTML = '● Live Backend (FastAPI + CP-SAT)';
        }
        if (banner) {
          banner.className = 'proto-banner alert-success';
          banner.style.background = '#f0fdf4';
          banner.style.borderColor = '#86efac';
        }
        if (bannerIcon) bannerIcon.textContent = '⚡';
        if (bannerText) {
          bannerText.innerHTML = `<strong>Live Backend Connected:</strong> FastAPI backend operational on PostgreSQL (Port 5433). CP-SAT constraint engine and validation rules A01–C02 ready.`;
        }

        // Fetch academic data in parallel
        await loadAcademicMetadata();
        await loadTimetableVersions();
      } else {
        markOfflineMode();
      }
    } catch (err) {
      console.warn('[EduPlus] Backend check failed, running in fallback mode:', err);
      markOfflineMode();
    }
  }

  function markOfflineMode() {
    _isBackendLive = false;
    const statusBadge = document.getElementById('backend-status-badge');
    const banner = document.getElementById('backend-connection-banner');
    const bannerText = document.getElementById('connection-banner-text');
    const bannerIcon = document.getElementById('connection-banner-icon');

    if (statusBadge) {
      statusBadge.className = 'badge badge-warning';
      statusBadge.innerHTML = '⚠ Backend Offline (Demo Mock)';
    }
    if (banner) {
      banner.className = 'proto-banner alert-warning';
    }
    if (bannerIcon) bannerIcon.textContent = '⚠';
    if (bannerText) {
      bannerText.innerHTML = `<strong>Backend Offline:</strong> FastAPI is currently not reachable at ${window.EduPlusAPI.baseUrl}. Displaying cached prototype demo data.`;
    }
  }

  async function loadAcademicMetadata() {
    try {
      const [deptRes, teachersRes, roomsRes, subjectsRes, yearsRes] = await Promise.all([
        window.EduPlusAPI.getDepartments(1, 10).catch(() => ({ items: [] })),
        window.EduPlusAPI.getTeachers(null, 1, 100).catch(() => ({ items: [] })),
        window.EduPlusAPI.getRooms().catch(() => []),
        window.EduPlusAPI.getSubjects().catch(() => []),
        window.EduPlusAPI.getAcademicYears().catch(() => []),
      ]);

      _departments = deptRes.items || [];
      _teachers = teachersRes.items || [];
      _rooms = Array.isArray(roomsRes) ? roomsRes : (roomsRes.items || []);
      _subjects = Array.isArray(subjectsRes) ? subjectsRes : (subjectsRes.items || []);
      _academicYears = Array.isArray(yearsRes) ? yearsRes : (yearsRes.items || []);

      // Populate department select in generate panel
      const deptSel = document.getElementById('param-department');
      if (deptSel && _departments.length > 0) {
        deptSel.innerHTML = _departments.map(d => `<option value="${d.id}">${d.name} (${d.code})</option>`).join('');
      }

      // Populate academic year select in generate panel
      const aySel = document.getElementById('param-year');
      if (aySel && _academicYears.length > 0) {
        aySel.innerHTML = _academicYears.map(y => `<option value="${y.id}">${y.label || `Year ${y.year_number}`}</option>`).join('');
      }

      // Populate filter dropdowns on timetable grid
      populateGridFilterOptions();
    } catch (err) {
      console.warn('[EduPlus] Metadata load failed:', err);
    }
  }

  function populateGridFilterOptions() {
    const teacherSel = document.getElementById('filter-teacher');
    const roomSel = document.getElementById('filter-room');

    if (teacherSel) {
      teacherSel.innerHTML = '<option value="">All Teachers</option>';
      const tList = _teachers.length > 0 ? _teachers : TEACHERS;
      tList.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.short_name || t.shortName || t.name;
        teacherSel.appendChild(opt);
      });
    }

    if (roomSel) {
      roomSel.innerHTML = '<option value="">All Rooms</option>';
      const rList = _rooms.length > 0 ? _rooms : ROOMS;
      rList.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = r.name;
        roomSel.appendChild(opt);
      });
    }
  }

  // ─── TIMETABLE VERSIONS LIFECYCLE ───────────────────────────────────────────
  async function loadTimetableVersions() {
    try {
      const versions = await window.EduPlusAPI.getVersions({ limit: 50 });
      _versions = Array.isArray(versions) ? versions : [];

      const countBadge = document.getElementById('version-count-badge');
      if (countBadge) countBadge.textContent = `${_versions.length} saved`;

      updateVersionDropdowns();

      if (_versions.length > 0) {
        // Find latest published or candidate version
        const published = _versions.find(v => v.status === 'published');
        const selected = published || _versions[0];
        await selectActiveVersion(selected.id);
      } else {
        _activeVersion = null;
        renderCurrentTimetableGrid();
      }
    } catch (err) {
      console.warn('[EduPlus] Failed loading versions:', err);
    }
  }

  function updateVersionDropdowns() {
    const filterVerSel = document.getElementById('filter-version');
    const compASel = document.getElementById('compare-version-a');
    const compBSel = document.getElementById('compare-version-b');
    const repairSel = document.getElementById('repair-source-version');

    const optionsHTML = _versions.map(v => {
      const dateStr = new Date(v.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const repairTag = v.is_repair ? ' [REPAIR]' : '';
      return `<option value="${v.id}">v${v.version_number}: ${v.label} (${v.status.toUpperCase()}${repairTag}) — ${dateStr}</option>`;
    }).join('');

    if (filterVerSel) filterVerSel.innerHTML = optionsHTML || '<option value="">No versions in DB</option>';
    if (compASel) compASel.innerHTML = optionsHTML || '<option value="">No versions</option>';
    if (compBSel) {
      compBSel.innerHTML = optionsHTML || '<option value="">No versions</option>';
      if (compBSel.options.length > 1) compBSel.selectedIndex = 1;
    }
    if (repairSel) repairSel.innerHTML = optionsHTML || '<option value="">No versions</option>';
  }

  async function selectActiveVersion(versionId) {
    if (!versionId) return;
    try {
      const detail = await window.EduPlusAPI.getVersion(versionId);
      _activeVersion = detail;
      _selectedCandidateId = versionId;

      // Update dropdown selection
      const filterVerSel = document.getElementById('filter-version');
      if (filterVerSel && filterVerSel.value !== versionId) {
        filterVerSel.value = versionId;
      }

      // Update header pills
      const ttPill = document.getElementById('topbar-tt-pill');
      const ttLabel = document.getElementById('topbar-tt-label');
      const gridPill = document.getElementById('grid-status-pill');
      const gridText = document.getElementById('grid-status-text');
      const gridSource = document.getElementById('grid-source-badge');

      const isPub = detail.status === 'published';
      const statusText = `v${detail.version_number} — ${detail.status.toUpperCase()}`;

      if (ttLabel) ttLabel.textContent = statusText;
      if (ttPill) ttPill.className = `status-pill ${isPub ? 'status-published' : 'status-diagnostic'}`;
      if (gridText) gridText.textContent = statusText;
      if (gridPill) gridPill.className = `status-pill ${isPub ? 'status-published' : 'status-diagnostic'}`;
      if (gridSource) {
        gridSource.textContent = `Live DB (${detail.total_sessions} sessions)`;
        gridSource.className = 'badge badge-live';
      }

      // Update conflict badges
      const conflictBadge = document.getElementById('conflict-count-badge');
      if (conflictBadge) conflictBadge.textContent = detail.hard_violations || 0;

      renderCurrentTimetableGrid();
      renderCandidateList();
      renderValidationResultView();
    } catch (err) {
      console.error('[EduPlus] Error fetching version detail:', err);
      showToast(`Failed loading timetable version: ${err.message}`, 'error');
    }
  }

  async function onVersionSelected(versionId) {
    if (!versionId) return;
    await selectActiveVersion(versionId);
  }

  // ─── TIMETABLE GRID RENDERER ────────────────────────────────────────────────
  function sessionCSSClass(type, targetGroup) {
    if (type === 'practical') return 'session-practical';
    if (type === 'tutorial') return 'session-tutorial';
    if (targetGroup && (targetGroup.startsWith('EG_') || ['SUB305', 'SUB306', 'SUB307'].includes(targetGroup))) {
      return 'session-elective';
    }
    return 'session-lecture';
  }

  function renderCurrentTimetableGrid() {
    const grid = document.getElementById('tt-grid');
    if (!grid) return;

    // Use live active version sessions if available, else mock data
    let sessions = [];
    let isLiveGrid = false;
    let isConflict = false;

    if (_isBackendLive && _activeVersion && _activeVersion.sessions) {
      isLiveGrid = true;
      sessions = _activeVersion.sessions.map(s => {
        // Normalise slot code: s.slot_index (1..10) -> "TS" + s.slot_index
        const slotCode = s.slot_index ? `TS${s.slot_index}` : (s.slot || 'TS1');
        return {
          id: s.assignment_id || s.id,
          assignment_id: s.assignment_id,
          day: s.day_name || s.day,
          slot: slotCode,
          slot_index: s.slot_index,
          subjectId: s.subject_id || s.subjectId,
          subjectName: s.subject_name || s.subjectId,
          subjectCode: s.subject_code || s.subject_name || s.subjectId,
          teacherId: s.teacher_id || s.teacherId,
          teacherName: s.teacher_name || s.teacherId,
          roomId: s.room_id || s.roomId,
          roomName: s.room_name || s.roomId,
          type: s.session_type || s.type,
          targetGroup: s.target_group_id || s.targetGroup,
          duration: s.duration_slots || 1,
          isFrozen: !!s.is_frozen || _pinnedSessionIds.has(s.assignment_id),
        };
      });
      isConflict = (_activeVersion.hard_violations || 0) > 0;
    } else {
      sessions = MOCK_TIMETABLE_VALID.sessions;
      isConflict = false;
    }

    const ft = _currentFilterTeacher;
    const fr = _currentFilterRoom;

    // Filter notice
    const filterNotice = document.getElementById('filter-notice');
    if (ft || fr) {
      if (filterNotice) filterNotice.classList.remove('hidden');
      const tText = ft ? `Teacher filter active` : '';
      const rText = fr ? `Room filter active` : '';
      const noticeText = document.getElementById('filter-notice-text');
      if (noticeText) noticeText.textContent = `Showing filtered sessions (${[tText, rText].filter(Boolean).join(', ')}).`;
    } else if (filterNotice) {
      filterNotice.classList.add('hidden');
    }

    // Build map: day -> slot -> [sessions]
    const sessionMap = {};
    DAYS.forEach(day => {
      sessionMap[day] = {};
      TIME_SLOTS.forEach(ts => {
        sessionMap[day][ts.id] = [];
      });
    });

    const filtered = sessions.filter(s => {
      if (s.hidden) return false;
      if (ft && s.teacherId !== ft && s.teacherName !== ft) return false;
      if (fr && s.roomId !== fr && s.roomName !== fr) return false;
      return true;
    });

    filtered.forEach(s => {
      if (sessionMap[s.day] && sessionMap[s.day][s.slot] !== undefined) {
        sessionMap[s.day][s.slot].push(s);
      }
    });

    // Render HTML table
    let html = '';
    html += `<div class="tt-header-cell" role="columnheader">Time</div>`;
    DAYS.forEach(d => {
      html += `<div class="tt-header-cell" role="columnheader">${d}</div>`;
    });

    TIME_SLOTS.forEach(ts => {
      const isLunch = ts.id === LUNCH_SLOT;
      html += `<div class="tt-time-cell" role="rowheader" aria-label="${ts.label}">${ts.label}</div>`;

      DAYS.forEach(day => {
        const slotSessions = sessionMap[day][ts.id] || [];

        if (isLunch) {
          html += `<div class="tt-cell lunch-cell" role="cell" aria-label="Lunch break"><div class="tt-lunch-label">🍽 Lunch</div></div>`;
          return;
        }

        if (slotSessions.length === 0) {
          html += `<div class="tt-cell" role="cell"></div>`;
          return;
        }

        const inner = slotSessions.map((s, idx) => {
          const cssClass = sessionCSSClass(s.type, s.targetGroup);
          const pinBadge = s.isFrozen ? `<span title="Pinned session (frozen during repair)" style="font-size:10px;">📌</span> ` : '';
          const labBadge = s.type === 'practical'
            ? `<div class="tt-session-type">⚗ Lab ${s.targetGroup ? String(s.targetGroup).slice(-2) : ''}</div>`
            : `<div class="tt-session-type">${s.type === 'tutorial' ? '✏ Tutorial' : '📖 Lecture'}</div>`;

          const dispSubj = s.subjectCode || s.subjectName || s.subjectId;
          const dispTeacher = s.teacherName || s.teacherId;
          const dispRoom = s.roomName || s.roomId;

          return `
            <div class="tt-session ${cssClass}"
                 role="button" tabindex="0"
                 onclick="showLiveSessionModal('${s.id || idx}', '${day}', '${ts.id}')"
                 aria-label="${dispSubj} ${s.type}">
              ${labBadge}
              <div class="tt-session-code">${pinBadge}${dispSubj}</div>
              <div class="tt-session-teacher">${dispTeacher}</div>
              <div class="tt-session-room">${dispRoom}</div>
            </div>`;
        }).join('');

        html += `<div class="tt-cell" role="cell">${inner}</div>`;
      });
    });

    grid.innerHTML = html;
  }

  function showLiveSessionModal(sessionId, day, slotId) {
    if (!_activeVersion || !_activeVersion.sessions) {
      // Fallback to mock session modal
      showSessionModal(sessionId, 'mock');
      return;
    }

    const s = _activeVersion.sessions.find(x => x.assignment_id === sessionId || x.id === sessionId);
    if (!s) return;

    const ts = TIME_SLOTS.find(t => t.id === slotId || t.index === s.slot_index);
    const isFrozen = s.is_frozen || _pinnedSessionIds.has(s.assignment_id);

    const bodyHTML = `
      <table style="font-size: var(--text-sm); width:100%;">
        <tr><td style="padding:6px 0; color:var(--gray-500); width:140px;">Subject</td><td style="font-weight:600;">${s.subject_name || s.subject_code || s.subject_id}</td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Session Type</td><td><span class="badge ${s.session_type === 'practical' ? 'badge-success' : s.session_type === 'tutorial' ? 'badge-info' : 'badge-brand'}">${s.session_type}</span></td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Teacher</td><td style="font-weight:600;">${s.teacher_name || s.teacher_id}</td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Room</td><td style="font-weight:600;">${s.room_name || s.room_id}</td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Target Group</td><td style="font-weight:600; font-family: var(--font-mono); font-size: var(--text-xs);">${s.target_group_type}: ${s.target_group_id}</td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Day & Time</td><td style="font-weight:600;">${s.day_name}, ${ts?.label || `Slot ${s.slot_index}`}</td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Freeze / Pin Status</td><td><span class="badge ${isFrozen ? 'badge-orange' : 'badge-neutral'}">${isFrozen ? '📌 Frozen (Pinned)' : 'Free to Reschedule'}</span></td></tr>
        <tr><td style="padding:6px 0; color:var(--gray-500);">Assignment ID</td><td style="font-family: var(--font-mono); font-size: 11px; color: var(--gray-400);">${s.assignment_id}</td></tr>
      </table>
      <div style="margin-top: 16px; display:flex; gap: 8px;">
        <button class="btn btn-sm ${isFrozen ? 'btn-secondary' : 'btn-orange'}" onclick="toggleSessionPin('${s.assignment_id}')">
          ${isFrozen ? '🔓 Unpin Session' : '📌 Pin Session (Preserve During Repair)'}
        </button>
      </div>
    `;

    openModal(`Session Details — ${s.day_name} ${ts?.label || ''}`, bodyHTML);
  }

  function toggleSessionPin(assignmentId) {
    if (_pinnedSessionIds.has(assignmentId)) {
      _pinnedSessionIds.delete(assignmentId);
      showToast('Session unpinned.', 'info');
    } else {
      _pinnedSessionIds.add(assignmentId);
      showToast('Session pinned! It will be preserved during localized repair.', 'success');
    }
    closeModal('session-modal');
    renderCurrentTimetableGrid();
  }

  // ─── FILTER CONTROLS ────────────────────────────────────────────────────────
  function applyFilters() {
    _currentFilterTeacher = document.getElementById('filter-teacher').value;
    _currentFilterRoom = document.getElementById('filter-room').value;
    _currentFilterYear = document.getElementById('filter-year').value;
    _currentFilterDivision = document.getElementById('filter-division').value;
    renderCurrentTimetableGrid();
  }

  function resetFilters() {
    const ft = document.getElementById('filter-teacher');
    const fr = document.getElementById('filter-room');
    const fy = document.getElementById('filter-year');
    const fd = document.getElementById('filter-division');

    if (ft) ft.value = '';
    if (fr) fr.value = '';
    if (fy) fy.value = '3';
    if (fd) fd.value = 'A';

    _currentFilterTeacher = '';
    _currentFilterRoom = '';
    _currentFilterYear = '3';
    _currentFilterDivision = 'A';
    renderCurrentTimetableGrid();
  }

  // ─── GENERATE PANEL & SOLVER INVOCATION ─────────────────────────────────────
  function renderGeneratePanel() {
    renderCandidateList();
    renderValidationResultView();
  }

  function renderCandidateList() {
    const container = document.getElementById('candidates-container');
    if (!container) return;

    if (!_isBackendLive || _versions.length === 0) {
      container.innerHTML = `
        <div class="version-card ${_selectedCandidateId === 'valid' ? 'selected' : ''}" onclick="selectCandidate('valid')">
          <div>
            <div class="version-num">Candidate 1 (Mock)</div>
            <div class="version-meta">Status: COMPLETE &bull; 27 sessions &bull; 0 violations</div>
          </div>
          <span class="status-pill status-published"><span class="status-dot"></span> Valid</span>
        </div>
        <div class="version-card ${_selectedCandidateId === 'conflict' ? 'selected' : ''}" onclick="selectCandidate('conflict')">
          <div>
            <div class="version-num">Candidate 2 (Mock Diagnostic)</div>
            <div class="version-meta">Status: INCOMPLETE &bull; 3 hard violations</div>
          </div>
          <span class="status-pill status-diagnostic"><span class="status-dot"></span> Diagnostic</span>
        </div>`;
      return;
    }

    container.innerHTML = _versions.map(v => {
      const isSelected = _activeVersion && _activeVersion.id === v.id;
      const dateStr = new Date(v.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const hardViol = v.hard_violations || 0;
      const isPub = v.status === 'published';

      return `
        <div class="version-card ${isSelected ? 'selected' : ''}"
             onclick="selectActiveVersion('${v.id}')"
             role="button" tabindex="0"
             aria-label="Version ${v.version_number}">
          <div>
            <div class="version-num">Version ${v.version_number}: ${v.label}</div>
            <div class="version-meta">${v.total_sessions || 0} sessions &bull; ${hardViol} hard violations &bull; ${dateStr}</div>
          </div>
          <span class="status-pill ${isPub ? 'status-published' : hardViol === 0 ? 'status-published' : 'status-diagnostic'}">
            <span class="status-dot"></span> ${v.status.toUpperCase()}
          </span>
        </div>`;
    }).join('');
  }

  function renderValidationResultView() {
    const subtitle = document.getElementById('validation-subtitle');
    const chip = document.getElementById('validation-status-chip');
    const body = document.getElementById('validation-body');
    const gate = document.getElementById('publish-gate-panel');
    const pubBtn = document.getElementById('btn-publish');

    if (!_activeVersion) {
      if (subtitle) subtitle.textContent = 'No active version selected';
      if (chip) chip.innerHTML = '<span class="badge badge-neutral">No selection</span>';
      if (body) body.innerHTML = '<p class="text-muted">Click "Generate New Timetable" to trigger the CP-SAT engine.</p>';
      if (gate) gate.innerHTML = '';
      if (pubBtn) pubBtn.disabled = true;
      return;
    }

    const v = _activeVersion;
    const hardCount = v.hard_violations || (v.violations ? v.violations.filter(x => x.level === 'A').length : 0);
    const softCount = v.violations ? v.violations.filter(x => x.level !== 'A').length : 0;
    const isOptimal = hardCount === 0;

    if (subtitle) subtitle.textContent = `v${v.version_number}: ${v.label}`;

    if (chip) {
      chip.innerHTML = isOptimal
        ? `<span class="solver-status solver-feasible">✓ 0 Hard Violations</span>`
        : `<span class="solver-status solver-infeasible">⛔ ${hardCount} Hard Violations</span>`;
    }

    if (body) {
      body.innerHTML = `
        <div class="alert ${isOptimal ? 'alert-success' : 'alert-error'}" style="margin-bottom:12px;">
          <span class="alert-icon">${isOptimal ? '✓' : '⛔'}</span>
          <span>
            <strong>${isOptimal ? 'Valid & Publication Eligible' : 'Violations Detected'}</strong>: 
            ${v.total_sessions} scheduled sessions. ${hardCount} Level A violations. ${softCount} soft quality warnings.
          </span>
        </div>
        <table style="font-size: var(--text-xs); width:100%;">
          <tr><td style="color:var(--gray-500);padding:4px 0;">Version ID</td><td style="font-family:var(--font-mono); font-size:10px;">${v.id}</td></tr>
          <tr><td style="color:var(--gray-500);padding:4px 0;">Status</td><td style="font-weight:700;">${v.status.toUpperCase()}</td></tr>
          <tr><td style="color:var(--gray-500);padding:4px 0;">Total Sessions</td><td style="font-weight:600;">${v.total_sessions}</td></tr>
          <tr><td style="color:var(--gray-500);padding:4px 0;">Hard Violations (Level A)</td><td style="font-weight:700; color: ${hardCount === 0 ? 'var(--success-500)' : 'var(--error-500)'};">${hardCount}</td></tr>
          <tr><td style="color:var(--gray-500);padding:4px 0;">Soft Warnings (Level B/C)</td><td style="font-weight:600;">${softCount}</td></tr>
          <tr><td style="color:var(--gray-500);padding:4px 0;">Is Localized Repair</td><td>${v.is_repair ? '<span class="badge badge-orange">Yes (Pinned Base)</span>' : 'Standard'}</td></tr>
        </table>
      `;
    }

    if (gate) {
      if (!isOptimal) {
        gate.innerHTML = `
          <div class="publish-gate" style="margin-top: 12px;" role="alert">
            <div class="publish-gate-title">🔒 Publication Blocked — Level A Violations</div>
            <p style="font-size: var(--text-xs); color: #7f1d1d; margin-top:4px;">
              Hard constraints cannot be relaxed or published. Run localized repair to resolve remaining conflicts.
            </p>
          </div>`;
      } else {
        gate.innerHTML = '';
      }
    }

    if (pubBtn) {
      pubBtn.disabled = !isOptimal;
      pubBtn.style.opacity = isOptimal ? '1' : '0.5';
    }
  }

  async function triggerRealGeneration() {
    if (!_isBackendLive) {
      simulateGenerate();
      return;
    }

    const btn = document.getElementById('btn-generate-new');
    const icon = document.getElementById('gen-btn-icon');
    const text = document.getElementById('gen-btn-text');

    const deptId = document.getElementById('param-department')?.value || (_departments[0]?.id);
    const ayId = document.getElementById('param-year')?.value;
    const label = document.getElementById('param-label')?.value || 'AY2026-27 Sem 5 - Automated Schedule';
    const timeout = parseInt(document.getElementById('param-timeout')?.value || '30', 10);
    const checkSoft = document.getElementById('param-check-soft')?.checked ?? true;

    if (!deptId) {
      showToast('Please select a department.', 'warning');
      return;
    }

    btn.classList.add('loading');
    btn.disabled = true;
    if (icon) icon.innerHTML = '<span class="spinner">⟳</span>';
    if (text) text.textContent = 'Solving with CP-SAT…';

    try {
      const payload = {
        department_id: deptId,
        academic_year_ids: ayId ? [ayId] : null,
        label: label,
        academic_year_code: "2026-27",
        semester: 1,
        time_limit_seconds: Math.max(5, Math.min(300, timeout)),
        check_soft_constraints: checkSoft,
      };

      const result = await window.EduPlusAPI.generateTimetable(payload);

      showToast(`CP-SAT solver finished in ${result.solver_time_ms}ms with status ${result.status}! (${result.total_sessions} sessions)`, 'success');

      // Refresh versions list and select the new one
      await loadTimetableVersions();
      if (result.version_id) {
        await selectActiveVersion(result.version_id);
      }
    } catch (err) {
      console.error('[EduPlus] Generation failed:', err);
      showToast(`Generation failed: ${err.message}`, 'error');
    } finally {
      btn.classList.remove('loading');
      btn.disabled = false;
      if (icon) icon.textContent = '⚙';
      if (text) text.textContent = 'Generate New Timetable';
    }
  }

  async function publishCurrentCandidate() {
    if (!_isBackendLive) {
      simulatePublish();
      return;
    }

    if (!_activeVersion) {
      showToast('No active version selected for publication.', 'warning');
      return;
    }

    if ((_activeVersion.hard_violations || 0) > 0) {
      showToast('Cannot publish version with unresolved Level A hard violations.', 'error');
      return;
    }

    try {
      const updated = await window.EduPlusAPI.publishVersion(_activeVersion.id);
      showToast(`Timetable Version ${updated.version_number} (${updated.label}) published successfully!`, 'success');
      await loadTimetableVersions();
      await selectActiveVersion(_activeVersion.id);
    } catch (err) {
      console.error('[EduPlus] Publish failed:', err);
      showToast(`Publish failed: ${err.message}`, 'error');
    }
  }

  async function revalidateActiveVersion() {
    if (!_isBackendLive || !_activeVersion) {
      showToast('Backend is offline or no active version loaded.', 'warning');
      return;
    }

    try {
      const res = await window.EduPlusAPI.validateTimetable({
        version_id: _activeVersion.id,
        check_soft: true,
      });

      showToast(`Re-validated v${_activeVersion.version_number}: ${res.hard_violations} hard, ${res.soft_violations} soft violations.`, res.hard_violations === 0 ? 'success' : 'warning');

      await selectActiveVersion(_activeVersion.id);
      showPanel('conflicts');
    } catch (err) {
      console.error('[EduPlus] Validation failed:', err);
      showToast(`Validation failed: ${err.message}`, 'error');
    }
  }

  // ─── CONFLICT REPORT PANEL ──────────────────────────────────────────────────
  function renderConflictPanel() {
    const list = document.getElementById('conflict-list');
    const summary = document.getElementById('conflict-summary');
    if (!list || !summary) return;

    let violations = [];
    if (_isBackendLive && _activeVersion && _activeVersion.violations) {
      violations = _activeVersion.violations;
    } else {
      // Mock diagnostic fallback
      violations = (MOCK_TIMETABLE_CONFLICT.conflicts || []).map(c => ({
        rule_id: c.ruleId,
        level: c.level,
        severity: c.severity,
        description: c.description,
        affected_session_ids: c.affectedSessions || [],
        affected_entity_ids: [],
        suggestion: c.note || null,
      }));
    }

    const errors = violations.filter(v => v.level === 'A' || v.severity === 'error');
    const warnings = violations.filter(v => v.level !== 'A' && v.severity !== 'error');

    // Summary panel
    summary.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size: var(--text-sm); font-weight:600;">Hard Violations (Level A)</span>
        <span class="badge ${errors.length > 0 ? 'badge-error' : 'badge-success'}">${errors.length}</span>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size: var(--text-sm); font-weight:600;">Policy &amp; Quality Warnings (Level B/C)</span>
        <span class="badge badge-warning">${warnings.length}</span>
      </div>
      <div class="divider" style="margin: 8px 0;"></div>
      ${errors.length > 0 ? `
        <div class="publish-gate">
          <div class="publish-gate-title">🔒 Publication Blocked</div>
          <ul class="publish-gate-reasons">
            ${errors.map(e => `<li>${e.rule_id}: ${e.description}</li>`).join('')}
          </ul>
          <div style="font-size: var(--text-xs); color: #7f1d1d; margin-top: 4px;">
            Level A violations must be resolved before publication.
          </div>
        </div>` : `
        <div class="alert alert-success" style="margin-top: 8px;">
          <span>✓ No hard violations. Schedule satisfies all institutional constraints.</span>
        </div>`
      }
    `;

    // Violations list
    if (violations.length === 0) {
      list.innerHTML = `
        <div class="alert alert-success" role="note">
          <span class="alert-icon">✓</span>
          <div>
            <strong>0 Conflicts Detected:</strong> The active timetable version satisfies all Level A hard constraints and Level B/C policies.
          </div>
        </div>`;
      return;
    }

    list.innerHTML = violations.map(v => {
      const isHard = v.level === 'A' || v.severity === 'error';
      return `
        <div class="conflict-item ${isHard ? 'conflict-error' : 'conflict-warning'}" role="article">
          <div class="conflict-header">
            <div>
              <div class="conflict-rule">Rule ${v.rule_id} &bull; Level ${v.level}</div>
              <div class="conflict-title">${isHard ? '⛔' : '⚠'} ${v.rule_id} — ${isHard ? 'Hard Constraint Violation' : 'Policy Warning'}</div>
            </div>
            <span class="badge ${isHard ? 'badge-error' : 'badge-warning'}">
              ${isHard ? 'Blocking' : 'Soft'}
            </span>
          </div>
          <div class="conflict-desc">${v.description}</div>
          ${v.suggestion ? `<div style="font-size: var(--text-xs); color: var(--gray-600); margin-top: 6px; font-style: italic;">💡 Suggestion: ${v.suggestion}</div>` : ''}
          ${(v.affected_session_ids && v.affected_session_ids.length > 0) ? `
            <div style="font-size: 10px; color: var(--gray-500); margin-top: 6px; font-family: var(--font-mono);">
              Affected sessions: ${v.affected_session_ids.join(', ')}
            </div>` : ''}
        </div>`;
    }).join('');
  }

  // ─── VERSION COMPARISON & DIFF ENGINE ───────────────────────────────────────
  function renderComparePanel() {
    updateVersionDropdowns();
  }

  async function runVersionComparison() {
    const verA = document.getElementById('compare-version-a')?.value;
    const verB = document.getElementById('compare-version-b')?.value;

    if (!verA || !verB) {
      showToast('Please select both Version A and Version B to compare.', 'warning');
      return;
    }

    if (verA === verB) {
      showToast('Version A and Version B are the same version.', 'info');
    }

    const btn = document.getElementById('btn-run-compare');
    if (btn) btn.disabled = true;

    try {
      const comp = await window.EduPlusAPI.compareVersions(verA, verB, true);

      // Show stats cards
      const statsContainer = document.getElementById('compare-stats');
      const diffCard = document.getElementById('compare-diff-card');
      const diffSubtitle = document.getElementById('compare-diff-subtitle');
      const tbody = document.getElementById('compare-diff-tbody');

      if (statsContainer) statsContainer.style.display = 'grid';
      if (diffCard) diffCard.style.display = 'block';

      document.getElementById('diff-added-count').textContent = comp.added;
      document.getElementById('diff-moved-count').textContent = comp.moved;
      document.getElementById('diff-removed-count').textContent = comp.removed;
      document.getElementById('diff-unchanged-count').textContent = comp.unchanged;

      if (diffSubtitle) {
        diffSubtitle.textContent = `Version A: ${comp.total_sessions_a} sessions ➔ Version B: ${comp.total_sessions_b} sessions (${comp.diffs.length} total changes)`;
      }

      if (tbody) {
        if (!comp.diffs || comp.diffs.length === 0) {
          tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 24px; color: var(--gray-500);">No session differences found between these two versions.</td></tr>`;
        } else {
          tbody.innerHTML = comp.diffs.map(d => {
            const badgeClass = d.change_type === 'added' ? 'diff-added'
              : d.change_type === 'removed' ? 'diff-removed'
              : d.change_type === 'moved' ? 'diff-moved' : 'diff-same';

            return `
              <tr>
                <td><span class="diff-badge ${badgeClass}">${d.change_type.toUpperCase()}</span></td>
                <td><code style="font-size:11px;">${d.assignment_id}</code> (${d.session_type})</td>
                <td><code>${d.teacher_id}</code></td>
                <td>${d.day_a ? `${d.day_a} Slot ${d.slot_a} (${d.room_a})` : '—'}</td>
                <td>${d.day_b ? `<strong>${d.day_b} Slot ${d.slot_b}</strong> (${d.room_b})` : '—'}</td>
              </tr>`;
          }).join('');
        }
      }

      showToast(`Comparison complete: ${comp.added} added, ${comp.moved} moved, ${comp.removed} removed.`, 'success');
    } catch (err) {
      console.error('[EduPlus] Comparison failed:', err);
      showToast(`Comparison failed: ${err.message}`, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ─── LOCALIZED REPAIR ───────────────────────────────────────────────────────
  async function runLocalizedRepair() {
    const sourceVerId = document.getElementById('repair-source-version')?.value;
    const label = document.getElementById('repair-label')?.value || 'AY2026-27 Sem 5 - Repaired Schedule';

    if (!sourceVerId) {
      showToast('Please select a source version to repair.', 'warning');
      return;
    }

    const btn = document.getElementById('btn-run-repair');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Repairing with CP-SAT…';
    }

    try {
      const payload = {
        source_version_id: sourceVerId,
        label: label,
        affected_assignment_ids: null, // solver repairs unfrozen while preserving pinned
        time_limit_seconds: 45,
      };

      const result = await window.EduPlusAPI.repairTimetable(payload);

      showToast(`Localized repair complete! Created new repair version in ${result.solver_time_ms}ms with status ${result.status}.`, 'success');

      await loadTimetableVersions();
      if (result.version_id) {
        await selectActiveVersion(result.version_id);
        showPanel('timetable');
      }
    } catch (err) {
      console.error('[EduPlus] Repair failed:', err);
      showToast(`Localized repair failed: ${err.message}`, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '🔧 Run Localized Repair';
      }
    }
  }

  // ─── TEACHERS & ROOMS TABLES ────────────────────────────────────────────────
  function renderTeachers() {
    const tbody = document.getElementById('teachers-tbody');
    if (!tbody || tbody.children.length > 0) return;

    const tList = _teachers.length > 0 ? _teachers : TEACHERS;
    tbody.innerHTML = tList.map(t => {
      const specs = t.specializations || [];
      return `
        <tr>
          <td><code style="font-size: var(--text-xs); color: var(--gray-500);">${t.id}</code></td>
          <td><strong>${t.name}</strong></td>
          <td>${t.designation || 'Faculty'}</td>
          <td>${specs.map(s => `<span class="badge badge-neutral" style="margin-right:2px;">${s}</span>`).join('') || '<span class="text-muted">—</span>'}</td>
          <td><span class="badge badge-brand">${t.weekly_workload_cap || 16} hrs cap</span></td>
        </tr>`;
    }).join('');
  }

  function renderRooms() {
    const classroomsTbody = document.getElementById('classrooms-tbody');
    const labsTbody = document.getElementById('labs-tbody');

    const rList = _rooms.length > 0 ? _rooms : ROOMS;

    if (classroomsTbody && classroomsTbody.children.length === 0) {
      const classrooms = rList.filter(r => r.type === 'classroom');
      classroomsTbody.innerHTML = classrooms.map(r => `
        <tr>
          <td><code style="font-size: var(--text-xs);">${r.id}</code></td>
          <td>${r.name}</td>
          <td>${r.capacity}</td>
          <td>Floor ${r.floor || 1}</td>
          <td><span class="badge badge-brand">Classroom</span></td>
        </tr>`).join('');
    }

    if (labsTbody && labsTbody.children.length === 0) {
      const labs = rList.filter(r => r.type === 'laboratory');
      labsTbody.innerHTML = labs.map(r => `
        <tr>
          <td><code style="font-size: var(--text-xs);">${r.id}</code></td>
          <td>${r.name}</td>
          <td>${r.capacity}</td>
          <td>Floor ${r.floor || 1}</td>
          <td><span class="badge badge-orange">Laboratory</span></td>
        </tr>`).join('');
    }
  }

  function showRoomTab(tab) {
    ['classrooms', 'labs'].forEach(t => {
      const panel = document.getElementById(`rooms-tab-${t}`);
      const btn = document.getElementById(`tab-${t}`);
      if (panel) {
        panel.classList.toggle('active', t === tab);
        panel.classList.toggle('hidden', t !== tab);
      }
      if (btn) {
        btn.classList.toggle('active', t === tab);
        btn.setAttribute('aria-selected', String(t === tab));
      }
    });
  }

  // ─── REQUEST INBOX ──────────────────────────────────────────────────────────
  let _requests = [...DEMO_REQUESTS];
  function renderRequests() {
    const list = document.getElementById('requests-list');
    if (!list) return;
    const pending = _requests.filter(r => r.status === 'pending');
    const badge = document.getElementById('request-count-badge');
    if (badge) badge.textContent = pending.length;

    const statReq = document.getElementById('stat-requests');
    if (statReq) statReq.textContent = pending.length;

    list.innerHTML = _requests.map(r => `
      <div class="request-item" id="req-item-${r.id}">
        <div class="request-dot dot-${r.status}"></div>
        <div style="flex:1;">
          <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
            <span class="request-type-badge badge ${r.type === 'reschedule' ? 'badge-brand' : 'badge-info'}">${r.type}</span>
            <span style="font-size: var(--text-xs); color: var(--gray-500);">from ${r.submitterName}</span>
          </div>
          <div class="request-subject">${r.subject}</div>
          <div class="request-details">${r.details}</div>
          ${r.status === 'pending' ? `
            <div style="display:flex; gap: 8px; margin-top: 10px;">
              <button class="btn btn-success btn-sm" onclick="handleRequest('${r.id}','approved')">✓ Approve</button>
              <button class="btn btn-danger btn-sm" onclick="handleRequest('${r.id}','rejected')">✕ Reject</button>
            </div>` : `
            <div style="margin-top: 8px;">
              <span class="status-pill ${r.status === 'approved' ? 'status-published' : 'status-diagnostic'}">
                <span class="status-dot"></span> ${r.status.toUpperCase()}
              </span>
            </div>`
          }
        </div>
      </div>`).join('');
  }

  function handleRequest(id, action) {
    const req = _requests.find(r => r.id === id);
    if (!req) return;
    req.status = action;
    renderRequests();
    showToast(`Request "${req.subject}" ${action}.`, action === 'approved' ? 'success' : 'warning');
  }

  // ─── LEGACY / FALLBACK SIMULATION STUBS ──────────────────────────────────────
  function selectCandidate(which) {
    _selectedCandidateId = which;
    const candValid = document.getElementById('candidate-valid');
    const candConflict = document.getElementById('candidate-conflict');
    if (candValid) candValid.classList.toggle('selected', which === 'valid');
    if (candConflict) candConflict.classList.toggle('selected', which === 'conflict');

    const subtitle = document.getElementById('validation-subtitle');
    const chip = document.getElementById('validation-status-chip');
    const body = document.getElementById('validation-body');
    const pubBtn = document.getElementById('btn-publish');

    if (which === 'valid') {
      if (subtitle) subtitle.textContent = 'Candidate 1 — Valid';
      if (chip) chip.innerHTML = '<span class="solver-status solver-feasible">✓ All checks passed</span>';
      if (body) {
        body.innerHTML = `
          <div class="alert alert-success" style="margin-bottom:12px;">
            <span>✓ Candidate passes all checks. 27 sessions placed. 0 hard violations.</span>
          </div>`;
      }
      if (pubBtn) pubBtn.disabled = false;
    } else {
      if (subtitle) subtitle.textContent = 'Candidate 2 — Diagnostic';
      if (chip) chip.innerHTML = '<span class="solver-status solver-infeasible">⛔ Violations found</span>';
      if (body) {
        body.innerHTML = `
          <div class="alert alert-error" style="margin-bottom:12px;">
            <span>⛔ Candidate contains 3 hard violations (Level A).</span>
          </div>`;
      }
      if (pubBtn) pubBtn.disabled = true;
    }
  }

  function simulateGenerate() {
    const btn = document.getElementById('btn-generate-new');
    const icon = document.getElementById('gen-btn-icon');
    const text = document.getElementById('gen-btn-text');
    if (btn) btn.classList.add('loading');
    if (icon) icon.innerHTML = '<span class="spinner">⟳</span>';
    if (text) text.textContent = 'Simulating…';

    setTimeout(() => {
      if (btn) btn.classList.remove('loading');
      if (icon) icon.textContent = '⚙';
      if (text) text.textContent = 'Generate New Timetable';
      showToast('Mock candidate loaded (backend offline).', 'info');
      selectCandidate('valid');
    }, 1200);
  }

  function simulatePublish() {
    showToast('Mock publish complete (backend offline).', 'info');
  }

  // ─── OVERVIEW STATS ─────────────────────────────────────────────────────────
  function initOverview() {
    const divEl = document.getElementById('stat-divisions');
    const tchrEl = document.getElementById('stat-teachers');
    const rmEl = document.getElementById('stat-rooms');
    const sessEl = document.getElementById('overview-sessions');

    if (divEl) divEl.textContent = SUMMARY_STATS.totalDivisions;
    if (tchrEl) tchrEl.textContent = SUMMARY_STATS.totalTeachers;
    if (rmEl) rmEl.textContent = SUMMARY_STATS.totalRooms;
    if (sessEl) sessEl.textContent = SUMMARY_STATS.totalSessions;
  }

  // ─── INIT EXECUTION ─────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    initOverview();
    initBackendConnection();
  });

  // Also execute immediately in case script loaded after DOMContentLoaded
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initOverview();
    initBackendConnection();
  }

  // ─── EXPOSE FUNCTIONS TO WINDOW ─────────────────────────────────────────────
  window.showPanel = showPanel;
  window.signOut = signOut;
  window.showToast = showToast;
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.showLiveSessionModal = showLiveSessionModal;
  window.toggleSessionPin = toggleSessionPin;
  window.applyFilters = applyFilters;
  window.resetFilters = resetFilters;
  window.onVersionSelected = onVersionSelected;
  window.selectActiveVersion = selectActiveVersion;
  window.triggerRealGeneration = triggerRealGeneration;
  window.publishCurrentCandidate = publishCurrentCandidate;
  window.revalidateActiveVersion = revalidateActiveVersion;
  window.runVersionComparison = runVersionComparison;
  window.runLocalizedRepair = runLocalizedRepair;
  window.renderConflictPanel = renderConflictPanel;
  window.renderTeachers = renderTeachers;
  window.renderRooms = renderRooms;
  window.showRoomTab = showRoomTab;
  window.renderRequests = renderRequests;
  window.handleRequest = handleRequest;
  window.selectCandidate = selectCandidate;
  window.simulateGenerate = simulateGenerate;
  window.simulatePublish = simulatePublish;
})();
