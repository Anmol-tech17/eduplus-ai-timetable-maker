/**
 * mockData.js
 * EduPlus AI Timetable Maker — Mock Data Layer
 *
 * IMPORTANT: All data in this file is MOCK DATA for demo purposes only.
 * No real scheduling engine, database, or authentication system is connected.
 * Timetables shown are pre-generated illustrative examples, NOT outputs from
 * the CP-SAT constraint solver described in the project specification.
 *
 * Department: AIML — Example Engineering College
 */

(function () {
  "use strict";

// ─── DEMO CREDENTIALS ────────────────────────────────────────────────────────
const DEMO_USERS = [
  {
    id: "USR001",
    email: "admin@eduplus.demo",
    password: "admin123",
    role: "admin",
    name: "Dr. Priya Sharma",
    title: "Head of Department",
    department: "AIML",
  },
  {
    id: "USR002",
    email: "teacher@eduplus.demo",
    password: "teacher123",
    role: "teacher",
    name: "Prof. Arjun Mehta",
    title: "Assistant Professor",
    department: "AIML",
    teacherId: "TCH005",
  },
  {
    id: "USR003",
    email: "student@eduplus.demo",
    password: "student123",
    role: "student",
    name: "Sneha Patel",
    title: "B.Tech III Year",
    department: "AIML",
    studentId: "STU2301045",
    year: 3,
    division: "A",
    batch: "B1",
  },
];

// ─── ACADEMIC STRUCTURE ────────────────────────────────────────────────────────
const DEPARTMENT = {
  id: "DEPT001",
  code: "AIML",
  name: "Artificial Intelligence & Machine Learning",
  college: "Example Engineering College",
  hod: "Dr. Priya Sharma",
};

const YEARS = [
  { id: "YR1", year: 1, label: "First Year", divisions: ["A", "B", "C"] },
  { id: "YR2", year: 2, label: "Second Year", divisions: ["A", "B", "C"] },
  { id: "YR3", year: 3, label: "Third Year", divisions: ["A", "B"] },
  { id: "YR4", year: 4, label: "Fourth Year", divisions: ["A", "B"] },
];

const DIVISIONS = [
  { id: "DIV_1A", year: 1, name: "A", strength: 60, batches: ["B1", "B2", "B3"], homeRoom: "CR101" },
  { id: "DIV_1B", year: 1, name: "B", strength: 60, batches: ["B1", "B2", "B3"], homeRoom: "CR102" },
  { id: "DIV_1C", year: 1, name: "C", strength: 58, batches: ["B1", "B2", "B3"], homeRoom: "CR103" },
  { id: "DIV_2A", year: 2, name: "A", strength: 60, batches: ["B1", "B2", "B3"], homeRoom: "CR201" },
  { id: "DIV_2B", year: 2, name: "B", strength: 60, batches: ["B1", "B2", "B3"], homeRoom: "CR202" },
  { id: "DIV_2C", year: 2, name: "C", strength: 55, batches: ["B1", "B2", "B3"], homeRoom: "CR203" },
  { id: "DIV_3A", year: 3, name: "A", strength: 58, batches: ["B1", "B2", "B3"], homeRoom: "CR301" },
  { id: "DIV_3B", year: 3, name: "B", strength: 56, batches: ["B1", "B2", "B3"], homeRoom: "CR302" },
  { id: "DIV_4A", year: 4, name: "A", strength: 52, batches: ["B1", "B2"], homeRoom: "CR401" },
  { id: "DIV_4B", year: 4, name: "B", strength: 50, batches: ["B1", "B2"], homeRoom: "CR402" },
];

// ─── ROOMS ────────────────────────────────────────────────────────────────────
const ROOMS = [
  { id: "CR101", name: "Room 101", type: "classroom", capacity: 65, floor: 1 },
  { id: "CR102", name: "Room 102", type: "classroom", capacity: 65, floor: 1 },
  { id: "CR103", name: "Room 103", type: "classroom", capacity: 65, floor: 1 },
  { id: "CR201", name: "Room 201", type: "classroom", capacity: 65, floor: 2 },
  { id: "CR202", name: "Room 202", type: "classroom", capacity: 65, floor: 2 },
  { id: "CR203", name: "Room 203", type: "classroom", capacity: 65, floor: 2 },
  { id: "CR301", name: "Room 301", type: "classroom", capacity: 65, floor: 3 },
  { id: "CR302", name: "Room 302", type: "classroom", capacity: 65, floor: 3 },
  { id: "CR401", name: "Room 401", type: "classroom", capacity: 55, floor: 4 },
  { id: "CR402", name: "Room 402", type: "classroom", capacity: 55, floor: 4 },
  { id: "CR501", name: "Seminar Hall", type: "classroom", capacity: 120, floor: 5 },
  { id: "LAB01", name: "AI/ML Lab 1", type: "laboratory", capacity: 25, floor: 1, equipment: ["GPU Workstations", "Python 3.11"] },
  { id: "LAB02", name: "AI/ML Lab 2", type: "laboratory", capacity: 25, floor: 1, equipment: ["GPU Workstations", "Python 3.11"] },
  { id: "LAB03", name: "Data Science Lab", type: "laboratory", capacity: 25, floor: 2, equipment: ["Python 3.11", "R Studio", "MATLAB"] },
  { id: "LAB04", name: "Programming Lab 1", type: "laboratory", capacity: 30, floor: 2, equipment: ["Java 17", "Python 3.11"] },
  { id: "LAB05", name: "Programming Lab 2", type: "laboratory", capacity: 30, floor: 3, equipment: ["Java 17", "Python 3.11"] },
  { id: "LAB06", name: "Network Lab", type: "laboratory", capacity: 25, floor: 3, equipment: ["Cisco Routers", "Wireshark"] },
];

// ─── TEACHERS ────────────────────────────────────────────────────────────────
const TEACHERS = [
  { id: "TCH001", name: "Dr. Priya Sharma", shortName: "P.Sharma", designation: "Professor", specializations: ["Machine Learning", "Deep Learning"] },
  { id: "TCH002", name: "Dr. Rajesh Kumar", shortName: "R.Kumar", designation: "Associate Professor", specializations: ["Data Structures", "Algorithms"] },
  { id: "TCH003", name: "Dr. Anita Desai", shortName: "A.Desai", designation: "Associate Professor", specializations: ["Mathematics", "Statistics"] },
  { id: "TCH004", name: "Dr. Sanjay Patel", shortName: "S.Patel", designation: "Associate Professor", specializations: ["Database Systems", "Data Engineering"] },
  { id: "TCH005", name: "Prof. Arjun Mehta", shortName: "A.Mehta", designation: "Assistant Professor", specializations: ["Python", "Data Analysis"] },
  { id: "TCH006", name: "Prof. Kavita Nair", shortName: "K.Nair", designation: "Assistant Professor", specializations: ["Operating Systems", "Networks"] },
  { id: "TCH007", name: "Prof. Vikram Singh", shortName: "V.Singh", designation: "Assistant Professor", specializations: ["Computer Vision", "Image Processing"] },
  { id: "TCH008", name: "Prof. Meera Iyer", shortName: "M.Iyer", designation: "Assistant Professor", specializations: ["NLP", "Text Mining"] },
  { id: "TCH009", name: "Prof. Suresh Babu", shortName: "S.Babu", designation: "Assistant Professor", specializations: ["Robotics", "Embedded Systems"] },
  { id: "TCH010", name: "Prof. Deepa Krishnan", shortName: "D.Krishnan", designation: "Assistant Professor", specializations: ["Cloud Computing", "DevOps"] },
  { id: "TCH011", name: "Prof. Rahul Gupta", shortName: "R.Gupta", designation: "Assistant Professor", specializations: ["Blockchain", "Cybersecurity"] },
  { id: "TCH012", name: "Prof. Swati Joshi", shortName: "S.Joshi", designation: "Assistant Professor", specializations: ["Probability", "Linear Algebra"] },
];

// ─── SUBJECTS (Year 3 AIML, focused for demo) ─────────────────────────────────
const SUBJECTS = [
  { id: "SUB301", code: "AIML301", name: "Machine Learning", shortName: "ML", type: "theory", year: 3, credits: "3-0-2", weeklyLectures: 3, weeklyPracticals: 1 },
  { id: "SUB302", code: "AIML302", name: "Deep Learning", shortName: "DL", type: "theory", year: 3, credits: "3-0-2", weeklyLectures: 3, weeklyPracticals: 1 },
  { id: "SUB303", code: "AIML303", name: "Data Engineering", shortName: "DE", type: "theory", year: 3, credits: "3-1-0", weeklyLectures: 3, weeklyTutorials: 1 },
  { id: "SUB304", code: "AIML304", name: "Mathematics for AI", shortName: "Math", type: "theory", year: 3, credits: "3-1-0", weeklyLectures: 3, weeklyTutorials: 1 },
  { id: "SUB305", code: "AIML305", name: "Elective I: Computer Vision", shortName: "CV", type: "elective", year: 3, credits: "3-0-0", weeklyLectures: 3, elective: true },
  { id: "SUB306", code: "AIML306", name: "Elective I: Natural Language Processing", shortName: "NLP", type: "elective", year: 3, credits: "3-0-0", weeklyLectures: 3, elective: true },
  { id: "SUB307", code: "AIML307", name: "Elective I: Robotics", shortName: "Robo", type: "elective", year: 3, credits: "3-0-0", weeklyLectures: 3, elective: true },
];

// ─── TEACHING ASSIGNMENTS (Year 3, Division A only — demo) ───────────────────
const TEACHING_ASSIGNMENTS = [
  { id: "TA001", subjectId: "SUB301", divisionId: "DIV_3A", teacherId: "TCH001", sessionType: "lecture" },
  { id: "TA002", subjectId: "SUB301", divisionId: "DIV_3A", teacherId: "TCH005", sessionType: "practical", batchScope: "all" },
  { id: "TA003", subjectId: "SUB302", divisionId: "DIV_3A", teacherId: "TCH007", sessionType: "lecture" },
  { id: "TA004", subjectId: "SUB302", divisionId: "DIV_3A", teacherId: "TCH007", sessionType: "practical", batchScope: "all" },
  { id: "TA005", subjectId: "SUB303", divisionId: "DIV_3A", teacherId: "TCH004", sessionType: "lecture" },
  { id: "TA006", subjectId: "SUB303", divisionId: "DIV_3A", teacherId: "TCH004", sessionType: "tutorial" },
  { id: "TA007", subjectId: "SUB304", divisionId: "DIV_3A", teacherId: "TCH003", sessionType: "lecture" },
  { id: "TA008", subjectId: "SUB304", divisionId: "DIV_3A", teacherId: "TCH012", sessionType: "tutorial" },
  { id: "TA009", subjectId: "SUB305", divisionId: "DIV_3A", teacherId: "TCH007", sessionType: "lecture", enrollmentGroup: "EG_CV" },
  { id: "TA010", subjectId: "SUB306", divisionId: "DIV_3A", teacherId: "TCH008", sessionType: "lecture", enrollmentGroup: "EG_NLP" },
  { id: "TA011", subjectId: "SUB307", divisionId: "DIV_3A", teacherId: "TCH009", sessionType: "lecture", enrollmentGroup: "EG_ROBO" },
];

// ─── ENROLLMENT GROUPS (Electives, Year 3 Div A) ─────────────────────────────
const ENROLLMENT_GROUPS = [
  {
    id: "EG_CV",
    name: "CV Elective Group",
    subjectId: "SUB305",
    divisionId: "DIV_3A",
    studentCount: 28,
    // EG_CV and EG_NLP overlap (students E20–E28 in both)
    // EG_CV and EG_ROBO do NOT overlap
    conflicts: ["EG_NLP"],
  },
  {
    id: "EG_NLP",
    name: "NLP Elective Group",
    subjectId: "SUB306",
    divisionId: "DIV_3A",
    studentCount: 22,
    conflicts: ["EG_CV"],
  },
  {
    id: "EG_ROBO",
    name: "Robotics Elective Group",
    subjectId: "SUB307",
    divisionId: "DIV_3A",
    studentCount: 8,
    // No overlap with EG_CV or EG_NLP → can run simultaneously
    conflicts: [],
  },
];

// ─── TIME SLOTS ───────────────────────────────────────────────────────────────
// Working hours: 08:00–18:00 (10 slots per day)
const TIME_SLOTS = [
  { id: "TS1",  label: "08:00–09:00", startHour: 8,  endHour: 9  },
  { id: "TS2",  label: "09:00–10:00", startHour: 9,  endHour: 10 },
  { id: "TS3",  label: "10:00–11:00", startHour: 10, endHour: 11 },
  { id: "TS4",  label: "11:00–12:00", startHour: 11, endHour: 12 },
  { id: "TS5",  label: "12:00–13:00", startHour: 12, endHour: 13 },
  { id: "TS6",  label: "13:00–14:00", startHour: 13, endHour: 14 },
  { id: "TS7",  label: "14:00–15:00", startHour: 14, endHour: 15 },
  { id: "TS8",  label: "15:00–16:00", startHour: 15, endHour: 16 },
  { id: "TS9",  label: "16:00–17:00", startHour: 16, endHour: 17 },
  { id: "TS10", label: "17:00–18:00", startHour: 17, endHour: 18 },
];

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

// Lunch policy: Division 3A has lunch at 13:00–14:00 (TS6)
// NOTE: Different divisions can have different lunch slots per the spec.
const LUNCH_POLICY = {
  "DIV_3A": { allowedSlots: ["TS6"], assignedSlot: "TS6" },
  "DIV_3B": { allowedSlots: ["TS5", "TS6"], assignedSlot: "TS5" },
};

// ─── MOCK TIMETABLE: Year 3, Division A (PUBLISHED / VALID) ──────────────────
// NOTE: This timetable is a hand-crafted illustrative example.
// It was NOT produced by the CP-SAT constraint solver.
// It is used for demo purposes only.
const MOCK_TIMETABLE_VALID = {
  id: "TT_V1_3A_PUBLISHED",
  version: 1,
  status: "published", // published | draft | diagnostic
  label: "Timetable v1 — Year 3, Division A",
  divisionId: "DIV_3A",
  academicYear: "2026-27",
  semester: 5,
  publishedBy: "Dr. Priya Sharma",
  publishedAt: "2026-10-18T09:00:00",
  isMock: true,
  mockNote: "Pre-generated illustrative timetable. Not produced by the real CP-SAT solver.",
  sessions: [
    // ── MONDAY ──
    { id: "S001", day: "Monday", slot: "TS1", subjectId: "SUB301", teacherId: "TCH001", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S002", day: "Monday", slot: "TS2", subjectId: "SUB302", teacherId: "TCH007", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S003", day: "Monday", slot: "TS3", subjectId: "SUB303", teacherId: "TCH004", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S004", day: "Monday", slot: "TS4", subjectId: "SUB304", teacherId: "TCH003", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    // TS6 = Lunch for DIV_3A
    { id: "S005", day: "Monday", slot: "TS7", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B1", type: "practical", labStart: "TS7", labEnd: "TS8" },
    { id: "S005b", day: "Monday", slot: "TS8", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B1", type: "practical_cont", hidden: true },
    { id: "S006", day: "Monday", slot: "TS9", subjectId: "SUB302", teacherId: "TCH007", roomId: "LAB02", targetGroup: "DIV_3A/B2", type: "practical", labStart: "TS9", labEnd: "TS10" },
    { id: "S006b", day: "Monday", slot: "TS10", subjectId: "SUB302", teacherId: "TCH007", roomId: "LAB02", targetGroup: "DIV_3A/B2", type: "practical_cont", hidden: true },
    // ── TUESDAY ──
    { id: "S007", day: "Tuesday", slot: "TS1", subjectId: "SUB304", teacherId: "TCH003", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S008", day: "Tuesday", slot: "TS2", subjectId: "SUB303", teacherId: "TCH004", roomId: "CR301", targetGroup: "DIV_3A", type: "tutorial" },
    { id: "S009", day: "Tuesday", slot: "TS3", subjectId: "SUB305", teacherId: "TCH007", roomId: "CR302", targetGroup: "EG_CV", type: "lecture" },
    { id: "S010", day: "Tuesday", slot: "TS3", subjectId: "SUB307", teacherId: "TCH009", roomId: "CR501", targetGroup: "EG_ROBO", type: "lecture" },
    // ^ EG_CV and EG_ROBO run simultaneously (no student overlap — valid)
    { id: "S011", day: "Tuesday", slot: "TS4", subjectId: "SUB301", teacherId: "TCH001", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    // TS6 = Lunch
    { id: "S012", day: "Tuesday", slot: "TS7", subjectId: "SUB302", teacherId: "TCH007", roomId: "LAB02", targetGroup: "DIV_3A/B3", type: "practical", labStart: "TS7", labEnd: "TS8" },
    { id: "S012b", day: "Tuesday", slot: "TS8", subjectId: "SUB302", teacherId: "TCH007", roomId: "LAB02", targetGroup: "DIV_3A/B3", type: "practical_cont", hidden: true },
    { id: "S013", day: "Tuesday", slot: "TS9", subjectId: "SUB304", teacherId: "TCH012", roomId: "CR301", targetGroup: "DIV_3A", type: "tutorial" },
    // ── WEDNESDAY ──
    { id: "S014", day: "Wednesday", slot: "TS1", subjectId: "SUB302", teacherId: "TCH007", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S015", day: "Wednesday", slot: "TS2", subjectId: "SUB301", teacherId: "TCH001", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S016", day: "Wednesday", slot: "TS3", subjectId: "SUB306", teacherId: "TCH008", roomId: "CR302", targetGroup: "EG_NLP", type: "lecture" },
    { id: "S017", day: "Wednesday", slot: "TS3", subjectId: "SUB307", teacherId: "TCH009", roomId: "CR501", targetGroup: "EG_ROBO", type: "lecture" },
    { id: "S018", day: "Wednesday", slot: "TS4", subjectId: "SUB303", teacherId: "TCH004", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    // TS6 = Lunch
    { id: "S019", day: "Wednesday", slot: "TS7", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B2", type: "practical", labStart: "TS7", labEnd: "TS8" },
    { id: "S019b", day: "Wednesday", slot: "TS8", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B2", type: "practical_cont", hidden: true },
    { id: "S020", day: "Wednesday", slot: "TS9", subjectId: "SUB302", teacherId: "TCH007", roomId: "LAB02", targetGroup: "DIV_3A/B1", type: "practical", labStart: "TS9", labEnd: "TS10" },
    { id: "S020b", day: "Wednesday", slot: "TS10", subjectId: "SUB302", teacherId: "TCH007", roomId: "LAB02", targetGroup: "DIV_3A/B1", type: "practical_cont", hidden: true },
    // ── THURSDAY ──
    { id: "S021", day: "Thursday", slot: "TS1", subjectId: "SUB304", teacherId: "TCH003", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S022", day: "Thursday", slot: "TS2", subjectId: "SUB302", teacherId: "TCH007", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S023", day: "Thursday", slot: "TS3", subjectId: "SUB305", teacherId: "TCH007", roomId: "CR302", targetGroup: "EG_CV", type: "lecture" },
    { id: "S024", day: "Thursday", slot: "TS4", subjectId: "SUB303", teacherId: "TCH004", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    // TS6 = Lunch
    { id: "S025", day: "Thursday", slot: "TS7", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B3", type: "practical", labStart: "TS7", labEnd: "TS8" },
    { id: "S025b", day: "Thursday", slot: "TS8", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B3", type: "practical_cont", hidden: true },
    { id: "S026", day: "Thursday", slot: "TS9", subjectId: "SUB306", teacherId: "TCH008", roomId: "CR302", targetGroup: "EG_NLP", type: "lecture" },
    // ── FRIDAY ──
    { id: "S027", day: "Friday", slot: "TS1", subjectId: "SUB301", teacherId: "TCH001", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S028", day: "Friday", slot: "TS2", subjectId: "SUB304", teacherId: "TCH003", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "S029", day: "Friday", slot: "TS3", subjectId: "SUB307", teacherId: "TCH009", roomId: "CR501", targetGroup: "EG_ROBO", type: "lecture" },
    { id: "S030", day: "Friday", slot: "TS4", subjectId: "SUB305", teacherId: "TCH007", roomId: "CR302", targetGroup: "EG_CV", type: "lecture" },
    // TS6 = Lunch
    { id: "S031", day: "Friday", slot: "TS7", subjectId: "SUB303", teacherId: "TCH004", roomId: "CR301", targetGroup: "DIV_3A", type: "tutorial" },
    { id: "S032", day: "Friday", slot: "TS9", subjectId: "SUB304", teacherId: "TCH012", roomId: "CR301", targetGroup: "DIV_3A", type: "tutorial" },
  ],
};

// ─── MOCK TIMETABLE: CONFLICT / DIAGNOSTIC (for demo conflict panel) ──────────
// This timetable intentionally has conflicts to demonstrate the conflict panel.
const MOCK_TIMETABLE_CONFLICT = {
  id: "TT_DIAG_3A_DRAFT",
  version: null,
  status: "diagnostic", // INCOMPLETE — cannot be published
  label: "Draft Candidate — Diagnostic (INCOMPLETE)",
  divisionId: "DIV_3A",
  academicYear: "2026-27",
  semester: 5,
  isMock: true,
  mockNote: "Diagnostic draft. Intentionally contains conflicts for demonstration. NOT publishable.",
  sessions: [
    { id: "D001", day: "Monday", slot: "TS1", subjectId: "SUB301", teacherId: "TCH001", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    // CONFLICT: TCH007 assigned to two simultaneous sessions (A02 teacher clash)
    { id: "D002", day: "Monday", slot: "TS2", subjectId: "SUB302", teacherId: "TCH007", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    { id: "D003", day: "Monday", slot: "TS2", subjectId: "SUB305", teacherId: "TCH007", roomId: "CR302", targetGroup: "EG_CV", type: "lecture" },
    // CONFLICT: EG_CV and EG_NLP run simultaneously (student overlap — A03/A04)
    { id: "D004", day: "Monday", slot: "TS3", subjectId: "SUB305", teacherId: "TCH007", roomId: "CR302", targetGroup: "EG_CV", type: "lecture" },
    { id: "D005", day: "Monday", slot: "TS3", subjectId: "SUB306", teacherId: "TCH008", roomId: "CR301", targetGroup: "EG_NLP", type: "lecture" },
    // CONFLICT: Lab span over lunch (A08 violation)
    { id: "D006", day: "Monday", slot: "TS5", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B1", type: "practical", labStart: "TS5", labEnd: "TS6" },
    { id: "D006b", day: "Monday", slot: "TS6", subjectId: "SUB301", teacherId: "TCH005", roomId: "LAB01", targetGroup: "DIV_3A/B1", type: "practical_cont", hidden: true },
    { id: "D007", day: "Tuesday", slot: "TS1", subjectId: "SUB303", teacherId: "TCH004", roomId: "CR301", targetGroup: "DIV_3A", type: "lecture" },
    // Unscheduled: SUB302 practical Batch 3 — requirement not placed
  ],
  conflicts: [
    {
      id: "CONF001",
      ruleId: "A01",
      level: "A",
      severity: "error",
      title: "Teacher Double-Booking",
      description: "Prof. Vikram Singh (TCH007) is assigned to both Machine Learning lecture (DIV-3A, CR301) and Computer Vision elective (EG_CV, CR302) at Monday 09:00–10:00. A teacher cannot teach two sessions simultaneously.",
      affectedSessions: ["D002", "D003"],
      affectedEntities: ["TCH007"],
      canRelax: false,
    },
    {
      id: "CONF002",
      ruleId: "A03/A04",
      level: "A",
      severity: "error",
      title: "Student Group Conflict — Overlapping Electives",
      description: "Computer Vision (EG_CV) and Natural Language Processing (EG_NLP) share students (E20–E28). Both sessions are placed at Monday 10:00–11:00. Students in the overlap group cannot attend both simultaneously.",
      affectedSessions: ["D004", "D005"],
      affectedEntities: ["EG_CV", "EG_NLP"],
      canRelax: false,
      note: "EG_CV and EG_ROBO have no student overlap and may run simultaneously. EG_CV and EG_NLP do overlap and cannot.",
    },
    {
      id: "CONF003",
      ruleId: "A08",
      level: "A",
      severity: "error",
      title: "Lab Session Spans Lunch Break",
      description: "ML Practical for Batch B1 is placed at 12:00–14:00 (TS5–TS6). This lab spans the configured lunch slot (13:00–14:00) for DIV-3A. Rule A08 prohibits labs from spanning a target group's lunch period.",
      affectedSessions: ["D006", "D006b"],
      affectedEntities: ["DIV_3A/B1", "LAB01"],
      canRelax: false,
    },
    {
      id: "WARN001",
      ruleId: "B01",
      level: "B",
      severity: "warning",
      title: "Unscheduled Requirement",
      description: "Deep Learning Practical for Batch B3 has not been placed. The timetable is INCOMPLETE. Publication is blocked until all requirements are assigned.",
      affectedSessions: [],
      affectedEntities: ["SUB302/DIV_3A/B3"],
      canRelax: false,
    },
  ],
};

// ─── TEACHER-VIEW TIMETABLE (Prof. Arjun Mehta — TCH005) ─────────────────────
// Extract sessions assigned to TCH005 from the published timetable
function getTeacherTimetable(teacherId, timetable) {
  return timetable.sessions.filter(
    (s) => s.teacherId === teacherId && !s.hidden
  );
}

// ─── DEMO REQUESTS / NOTIFICATIONS ────────────────────────────────────────────
const DEMO_REQUESTS = [
  {
    id: "REQ001",
    type: "reschedule",
    submittedBy: "TCH005",
    submitterName: "Prof. Arjun Mehta",
    subject: "ML Practical — B1 rescheduling",
    details: "Request to move Monday ML Lab (B1) from 14:00–16:00 to Tuesday 14:00–16:00. Personal appointment on Monday afternoon.",
    status: "pending",
    submittedAt: "2026-10-20T08:30:00",
    priority: "normal",
  },
  {
    id: "REQ002",
    type: "substitution",
    submittedBy: "TCH003",
    submitterName: "Dr. Anita Desai",
    subject: "Mathematics for AI — Thursday lecture",
    details: "Unable to attend Thursday 08:00–09:00 Math lecture. Requesting substitution. Prof. Swati Joshi (TCH012) has confirmed availability.",
    status: "approved",
    submittedAt: "2026-10-19T15:00:00",
    approvedAt: "2026-10-19T16:30:00",
    approvedBy: "Dr. Priya Sharma",
    priority: "normal",
  },
  {
    id: "REQ003",
    type: "cancellation",
    submittedBy: "TCH004",
    submitterName: "Dr. Sanjay Patel",
    subject: "Data Engineering tutorial — Friday",
    details: "Attending departmental faculty meeting on Friday. Requesting cancellation of Friday 14:00–15:00 tutorial. No make-up required per department policy.",
    status: "pending",
    submittedAt: "2026-10-21T07:45:00",
    priority: "high",
  },
];

const DEMO_STUDENT_QUERIES = [
  {
    id: "SQ001",
    submittedBy: "STU2301045",
    submitterName: "Sneha Patel",
    query: "Why was the Deep Learning lab moved from Wednesday to Tuesday this week?",
    status: "pending",
    submittedAt: "2026-10-21T08:15:00",
    mockNote: "Query solving via ML model is planned for a future phase. Not yet implemented.",
  },
];

// ─── SUMMARY STATS (for admin dashboard) ──────────────────────────────────────
const SUMMARY_STATS = {
  totalDivisions: DIVISIONS.length,
  totalTeachers: TEACHERS.length,
  totalRooms: ROOMS.length,
  totalClassrooms: ROOMS.filter((r) => r.type === "classroom").length,
  totalLabs: ROOMS.filter((r) => r.type === "laboratory").length,
  publishedTimetables: 6,
  pendingRequests: DEMO_REQUESTS.filter((r) => r.status === "pending").length,
  totalSessions: MOCK_TIMETABLE_VALID.sessions.filter((s) => !s.hidden).length,
};

// ─── EXPORTS ──────────────────────────────────────────────────────────────────
window.EduPlusData = {
  DEMO_USERS,
  DEPARTMENT,
  YEARS,
  DIVISIONS,
  ROOMS,
  TEACHERS,
  SUBJECTS,
  TEACHING_ASSIGNMENTS,
  ENROLLMENT_GROUPS,
  TIME_SLOTS,
  DAYS,
  LUNCH_POLICY,
  MOCK_TIMETABLE_VALID,
  MOCK_TIMETABLE_CONFLICT,
  DEMO_REQUESTS,
  DEMO_STUDENT_QUERIES,
  SUMMARY_STATS,
  getTeacherTimetable,
};
})();
