/**
 * api.js — EduPlus API Service Layer
 * Lightweight, robust REST client connecting frontend to the FastAPI backend.
 * Provides full support for Phase 0–6 endpoints including JWT Authentication,
 * RBAC, Approval Workflows, User Management, Audit Logs, and Teacher Requests.
 */

(function () {
  "use strict";

  const API_BASE_URL = window.EDUPLUS_API_URL || "http://127.0.0.1:8000/api/v1";

  function getStoredToken() {
    try {
      return sessionStorage.getItem("eduplus_token") || null;
    } catch (_) {
      return null;
    }
  }

  function setStoredAuth(token, user) {
    try {
      if (token) sessionStorage.setItem("eduplus_token", token);
      if (user) {
        const normalized = {
          ...user,
          name: user.full_name || user.name || (user.email ? user.email.split("@")[0] : "User"),
        };
        sessionStorage.setItem("eduplus_user", JSON.stringify(normalized));
      }
    } catch (_) {}
  }

  function clearStoredAuth() {
    try {
      sessionStorage.removeItem("eduplus_token");
      sessionStorage.removeItem("eduplus_user");
    } catch (_) {}
  }

  async function request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    const token = getStoredToken();
    if (token && !options.skipAuth) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, { ...options, headers });
      if (!response.ok) {
        let errMessage = `HTTP Error ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errMessage =
              typeof errorData.detail === "string"
                ? errorData.detail
                : JSON.stringify(errorData.detail);
          } else if (errorData.message) {
            errMessage = errorData.message;
          }
        } catch (_) {}

        // Handle expired or revoked session on protected routes
        if (response.status === 401 && !options.skipAuth && endpoint !== "/auth/login") {
          clearStoredAuth();
          if (!window.location.pathname.endsWith("index.html") && window.location.pathname !== "/") {
            window.location.href = "index.html?reason=session_expired";
          }
        }

        const error = new Error(errMessage);
        error.status = response.status;
        throw error;
      }

      if (response.status === 204) return null;
      return await response.json();
    } catch (err) {
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        console.warn(`[EduPlus API] Network error connecting to ${url}: ${err.message}`);
      }
      throw err;
    }
  }

  const EduPlusAPI = {
    baseUrl: API_BASE_URL,
    getStoredToken,
    setStoredAuth,
    clearStoredAuth,

    // ─── System & Connectivity ──────────────────────────────────────────────
    async getHealth() {
      return request("/health", { skipAuth: true });
    },

    async isBackendLive() {
      try {
        const res = await request("/health", { skipAuth: true });
        return res && res.status === "healthy";
      } catch (_) {
        return false;
      }
    },

    // ─── Phase 6: Authentication ────────────────────────────────────────────
    async login(email, password) {
      const data = await request("/auth/login", {
        method: "POST",
        skipAuth: true,
        body: JSON.stringify({ email, password }),
      });
      if (data && data.access_token) {
        setStoredAuth(data.access_token, data.user);
      }
      return data;
    },

    async logout() {
      try {
        if (getStoredToken()) {
          await request("/auth/logout", { method: "POST" });
        }
      } catch (_) {
        // Always clear local session even if server unreachable
      } finally {
        clearStoredAuth();
      }
    },

    async getMe() {
      return request("/auth/me");
    },

    async changePassword(currentPassword, newPassword) {
      return request("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
    },

    // ─── Academic Entities ──────────────────────────────────────────────────
    async getDepartments(page = 1, pageSize = 20) {
      return request(`/departments?page=${page}&page_size=${pageSize}`);
    },

    async getDepartment(id) {
      return request(`/departments/${id}`);
    },

    async getAcademicYears(departmentId = null) {
      const q = departmentId ? `?department_id=${encodeURIComponent(departmentId)}` : "";
      return request(`/academic-years${q}`);
    },

    async getDivisions(academicYearId = null) {
      const q = academicYearId ? `?academic_year_id=${encodeURIComponent(academicYearId)}` : "";
      return request(`/divisions${q}`);
    },

    async getBatches(divisionId = null) {
      const q = divisionId ? `?division_id=${encodeURIComponent(divisionId)}` : "";
      return request(`/batches${q}`);
    },

    async getSubjects(departmentId = null, year = null) {
      const params = new URLSearchParams();
      if (departmentId) params.append("department_id", departmentId);
      if (year) params.append("year_number", year);
      const q = params.toString() ? `?${params.toString()}` : "";
      return request(`/subjects${q}`);
    },

    async getTeachers(departmentId = null, page = 1, pageSize = 50) {
      const q = departmentId ? `&department_id=${encodeURIComponent(departmentId)}` : "";
      return request(`/teachers?page=${page}&page_size=${pageSize}${q}`);
    },

    async getRooms(departmentId = null, type = null) {
      const params = new URLSearchParams();
      if (departmentId) params.append("department_id", departmentId);
      if (type) params.append("type", type);
      const q = params.toString() ? `?${params.toString()}` : "";
      return request(`/rooms${q}`);
    },

    // ─── Timetable Generation, Approvals & Lifecycle ────────────────────────
    async generateTimetable(payload) {
      return request("/timetable/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    async validateTimetable(payload) {
      return request("/timetable/validate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    async getVersions({ department_id = null, status = null, limit = 50 } = {}) {
      const params = new URLSearchParams();
      if (department_id) params.append("department_id", department_id);
      if (status) params.append("status", status);
      if (limit) params.append("limit", limit);
      const q = params.toString() ? `?${params.toString()}` : "";
      return request(`/timetable/versions${q}`);
    },

    async getVersion(versionId) {
      return request(`/timetable/versions/${encodeURIComponent(versionId)}`);
    },

    async submitVersionForApproval(versionId, comment = null) {
      return request(`/timetable/versions/${encodeURIComponent(versionId)}/submit`, {
        method: "POST",
        body: JSON.stringify({ comment }),
      });
    },

    async approveVersion(versionId, comment = null) {
      return request(`/timetable/versions/${encodeURIComponent(versionId)}/approve`, {
        method: "POST",
        body: JSON.stringify({ comment }),
      });
    },

    async rejectVersion(versionId, comment = null) {
      return request(`/timetable/versions/${encodeURIComponent(versionId)}/reject`, {
        method: "POST",
        body: JSON.stringify({ comment }),
      });
    },

    async publishVersion(versionId) {
      return request(`/timetable/versions/${encodeURIComponent(versionId)}/publish`, {
        method: "POST",
      });
    },

    async compareVersions(versionA, versionB, includeDiffs = true) {
      const params = new URLSearchParams({
        version_a: versionA,
        version_b: versionB,
        include_diffs: includeDiffs,
      });
      return request(`/timetable/compare?${params.toString()}`);
    },

    async repairTimetable(payload) {
      return request("/timetable/repair", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    async getGenerationRun(runId) {
      return request(`/timetable/runs/${encodeURIComponent(runId)}`);
    },

    // ─── Phase 5: AI Assistant & Grounded Explanations ──────────────────────
    async getAIStatus() {
      return request("/ai/status");
    },

    async interpretPrompt(prompt, departmentId = null, academicYearId = null) {
      return request("/ai/interpret", {
        method: "POST",
        body: JSON.stringify({
          prompt,
          department_id: departmentId,
          academic_year_id: academicYearId,
        }),
      });
    },

    async explainTimetable(payload) {
      return request("/ai/explain", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    // ─── Phase 6: Admin Users & Audit Logs ──────────────────────────────────
    async getUsers(page = 1, pageSize = 50, role = null) {
      const params = new URLSearchParams({ page, page_size: pageSize });
      if (role) params.append("role", role);
      return request(`/users?${params.toString()}`);
    },

    async createUser(payload) {
      return request("/users", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    async updateUser(userId, payload) {
      return request(`/users/${encodeURIComponent(userId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },

    async getAuditLogs(page = 1, pageSize = 50, action = null) {
      const params = new URLSearchParams({ page, page_size: pageSize });
      if (action) params.append("action", action);
      return request(`/audit-logs?${params.toString()}`);
    },

    // ─── Phase 6: Teacher Availability & Schedule Requests ──────────────────
    async submitTeacherRequest(payload) {
      return request("/requests", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    async getTeacherRequests(status = null) {
      const q = status ? `?status=${encodeURIComponent(status)}` : "";
      return request(`/requests${q}`);
    },

    async reviewTeacherRequest(requestId, decision, comment = null) {
      return request(`/requests/${encodeURIComponent(requestId)}/review`, {
        method: "POST",
        body: JSON.stringify({ decision, comment }),
      });
    },
  };

  window.EduPlusAPI = EduPlusAPI;
})();
