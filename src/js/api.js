/**
 * api.js — EduPlus API Service Layer
 * Lightweight, robust REST client connecting frontend to the FastAPI backend.
 * Provides full support for Phase 0/1 Academic CRUD and Phase 2/3 Timetable Engine endpoints.
 */

(function () {
  "use strict";

  const API_BASE_URL = window.EDUPLUS_API_URL || "http://127.0.0.1:8000/api/v1";

  async function request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    try {
      const response = await fetch(url, { ...options, headers });
      if (!response.ok) {
        let errMessage = `HTTP Error ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errMessage = typeof errorData.detail === "string" 
              ? errorData.detail 
              : JSON.stringify(errorData.detail);
          } else if (errorData.message) {
            errMessage = errorData.message;
          }
        } catch (_) {}
        const error = new Error(errMessage);
        error.status = response.status;
        throw error;
      }
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

    // ─── System & Connectivity ──────────────────────────────────────────────
    async getHealth() {
      return request("/health");
    },

    async isBackendLive() {
      try {
        const res = await request("/health");
        return res && res.status === "healthy";
      } catch (_) {
        return false;
      }
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

    // ─── Timetable Generation & Engine ───────────────────────────────────────
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

    // ─── Phase 5: AI Assistant & Grounded Explanations ───────────────────────
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
  };

  window.EduPlusAPI = EduPlusAPI;
})();
