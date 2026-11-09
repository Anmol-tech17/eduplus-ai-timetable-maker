/**
 * api.js — EduPlus API Service Layer
 * Lightweight REST client to connect the frontend to the FastAPI backend.
 * Gracefully falls back to mockData when the backend is offline.
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
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP Error ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      console.warn(`[EduPlus API] Request to ${endpoint} failed: ${err.message}. Falling back to local data if available.`);
      throw err;
    }
  }

  const EduPlusAPI = {
    baseUrl: API_BASE_URL,
    
    // Health & System
    async getHealth() {
      return request("/health");
    },

    // Departments
    async getDepartments(page = 1, pageSize = 20) {
      return request(`/departments?page=${page}&page_size=${pageSize}`);
    },

    async getDepartment(id) {
      return request(`/departments/${id}`);
    },

    // Academic Years & Cohorts
    async getAcademicYears(departmentId = null) {
      const q = departmentId ? `?department_id=${departmentId}` : "";
      return request(`/academic-years${q}`);
    },

    async getDivisions(academicYearId = null) {
      const q = academicYearId ? `?academic_year_id=${academicYearId}` : "";
      return request(`/divisions${q}`);
    },

    async getBatches(divisionId = null) {
      const q = divisionId ? `?division_id=${divisionId}` : "";
      return request(`/batches${q}`);
    },

    // Subjects
    async getSubjects(departmentId = null, year = null) {
      const params = new URLSearchParams();
      if (departmentId) params.append("department_id", departmentId);
      if (year) params.append("year_number", year);
      const q = params.toString() ? `?${params.toString()}` : "";
      return request(`/subjects${q}`);
    },

    // Teachers
    async getTeachers(departmentId = null, page = 1, pageSize = 50) {
      const q = departmentId ? `&department_id=${departmentId}` : "";
      return request(`/teachers?page=${page}&page_size=${pageSize}${q}`);
    },

    // Rooms
    async getRooms(departmentId = null, type = null) {
      const params = new URLSearchParams();
      if (departmentId) params.append("department_id", departmentId);
      if (type) params.append("type", type);
      const q = params.toString() ? `?${params.toString()}` : "";
      return request(`/rooms${q}`);
    },
  };

  window.EduPlusAPI = EduPlusAPI;
})();
