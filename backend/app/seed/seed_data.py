"""
backend/app/seed/seed_data.py
EduPlus AI Timetable Maker — Database Seed Script
Populates the PostgreSQL database with the verified AIML Department baseline.
Guarded against duplicate insertion for idempotent execution.
"""

from datetime import time
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.core.security import get_password_hash
from backend.app.db.session import SessionLocal
from backend.app.models.academic import (
    Department, AcademicYear, Division, Batch, Subject,
    EnrollmentGroup, EnrollmentGroupOverlap
)
from backend.app.models.room import Room, RoomCapability
from backend.app.models.faculty import Teacher
from backend.app.models.scheduling import TimeSlot, WorkingDay, DivisionLunchPolicy
from backend.app.models.security import UserAccount


def seed_database(db: Session = None) -> dict:
    """Seeds foundational AIML department data idempotently."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    stats = {
        "departments": 0,
        "academic_years": 0,
        "divisions": 0,
        "batches": 0,
        "rooms": 0,
        "teachers": 0,
        "subjects": 0,
        "time_slots": 0,
        "working_days": 0,
        "users": 0,
    }

    try:
        # 1. Department
        dept = db.query(Department).filter(Department.code == "AIML").first()
        if not dept:
            dept = Department(
                code="AIML",
                name="Artificial Intelligence & Machine Learning",
                college_name="Example Engineering College"
            )
            db.add(dept)
            db.commit()
            db.refresh(dept)
            stats["departments"] += 1
            logger.info("Created department: AIML")

        # 2. Time Slots (TS1 to TS10, 08:00 - 18:00)
        slot_definitions = [
            ("TS1", time(8, 0), time(9, 0), 1, "08:00 – 09:00"),
            ("TS2", time(9, 0), time(10, 0), 2, "09:00 – 10:00"),
            ("TS3", time(10, 0), time(11, 0), 3, "10:00 – 11:00"),
            ("TS4", time(11, 0), time(12, 0), 4, "11:00 – 12:00"),
            ("TS5", time(12, 0), time(13, 0), 5, "12:00 – 13:00"),
            ("TS6", time(13, 0), time(14, 0), 6, "13:00 – 14:00"),
            ("TS7", time(14, 0), time(15, 0), 7, "14:00 – 15:00"),
            ("TS8", time(15, 0), time(16, 0), 8, "15:00 – 16:00"),
            ("TS9", time(16, 0), time(17, 0), 9, "16:00 – 17:00"),
            ("TS10", time(17, 0), time(18, 0), 10, "17:00 – 18:00"),
        ]
        for code, start, end, idx, label in slot_definitions:
            if not db.query(TimeSlot).filter(TimeSlot.slot_code == code).first():
                db.add(TimeSlot(slot_code=code, start_time=start, end_time=end, slot_index=idx, label=label))
                stats["time_slots"] += 1
        db.commit()

        # 3. Working Days (Monday - Friday active, Saturday optional)
        days = [
            ("Monday", 1, True),
            ("Tuesday", 2, True),
            ("Wednesday", 3, True),
            ("Thursday", 4, True),
            ("Friday", 5, True),
            ("Saturday", 6, False),
        ]
        for day_name, day_idx, is_active in days:
            if not db.query(WorkingDay).filter(
                WorkingDay.department_id == dept.id,
                WorkingDay.day_name == day_name
            ).first():
                db.add(WorkingDay(
                    department_id=dept.id,
                    day_name=day_name,
                    day_index=day_idx,
                    is_active=is_active
                ))
                stats["working_days"] += 1
        db.commit()

        # 4. Rooms (Classrooms & Labs)
        room_data = [
            ("CR101", "classroom", 65, 1),
            ("CR102", "classroom", 65, 1),
            ("CR103", "classroom", 65, 1),
            ("CR201", "classroom", 65, 2),
            ("CR202", "classroom", 65, 2),
            ("CR203", "classroom", 65, 2),
            ("CR301", "classroom", 65, 3),
            ("CR302", "classroom", 65, 3),
            ("CR401", "classroom", 55, 4),
            ("CR402", "classroom", 55, 4),
            ("CR501", "classroom", 120, 5),
            ("LAB01", "laboratory", 25, 1),
            ("LAB02", "laboratory", 25, 1),
            ("LAB03", "laboratory", 25, 2),
            ("LAB04", "laboratory", 30, 2),
            ("LAB05", "laboratory", 30, 3),
            ("LAB06", "laboratory", 25, 3),
        ]
        room_map = {}
        for r_name, r_type, r_cap, r_floor in room_data:
            r = db.query(Room).filter(Room.department_id == dept.id, Room.name == r_name).first()
            if not r:
                r = Room(department_id=dept.id, name=r_name, type=r_type, capacity=r_cap, floor=r_floor)
                db.add(r)
                db.commit()
                db.refresh(r)
                stats["rooms"] += 1
            room_map[r_name] = r

        # 5. Academic Years & Divisions & Batches
        year_configs = [
            (1, "First Year", ["A", "B", "C"]),
            (2, "Second Year", ["A", "B", "C"]),
            (3, "Third Year", ["A", "B"]),
            (4, "Fourth Year", ["A", "B"]),
        ]
        home_room_mapping = {
            (1, "A"): "CR101", (1, "B"): "CR102", (1, "C"): "CR103",
            (2, "A"): "CR201", (2, "B"): "CR202", (2, "C"): "CR203",
            (3, "A"): "CR301", (3, "B"): "CR302",
            (4, "A"): "CR401", (4, "B"): "CR402",
        }

        for yr_num, yr_label, div_names in year_configs:
            ay = db.query(AcademicYear).filter(
                AcademicYear.department_id == dept.id,
                AcademicYear.year_number == yr_num
            ).first()
            if not ay:
                ay = AcademicYear(department_id=dept.id, year_number=yr_num, label=yr_label)
                db.add(ay)
                db.commit()
                db.refresh(ay)
                stats["academic_years"] += 1

            for div_name in div_names:
                div = db.query(Division).filter(
                    Division.academic_year_id == ay.id,
                    Division.name == div_name
                ).first()
                if not div:
                    hr_name = home_room_mapping.get((yr_num, div_name))
                    hr_id = room_map[hr_name].id if hr_name in room_map else None
                    div = Division(
                        academic_year_id=ay.id,
                        name=div_name,
                        strength=58 if yr_num == 3 and div_name == "A" else 60,
                        home_room_id=hr_id,
                    )
                    db.add(div)
                    db.commit()
                    db.refresh(div)
                    stats["divisions"] += 1

                # Batches B1, B2, B3
                batch_names = ["B1", "B2", "B3"] if yr_num < 4 else ["B1", "B2"]
                for b_name in batch_names:
                    if not db.query(Batch).filter(Batch.division_id == div.id, Batch.name == b_name).first():
                        db.add(Batch(division_id=div.id, name=b_name, capacity=20))
                        stats["batches"] += 1
                db.commit()

        # 6. Teachers
        teacher_data = [
            ("Dr. Priya Sharma", "P.Sharma", "Professor", 14, "admin@eduplus.demo"),
            ("Dr. Rajesh Kumar", "R.Kumar", "Associate Professor", 16, "r.kumar@eduplus.demo"),
            ("Dr. Anita Desai", "A.Desai", "Associate Professor", 16, "a.desai@eduplus.demo"),
            ("Dr. Sanjay Patel", "S.Patel", "Associate Professor", 16, "s.patel@eduplus.demo"),
            ("Prof. Arjun Mehta", "A.Mehta", "Assistant Professor", 18, "teacher@eduplus.demo"),
            ("Prof. Kavita Nair", "K.Nair", "Assistant Professor", 18, "k.nair@eduplus.demo"),
            ("Prof. Vikram Singh", "V.Singh", "Assistant Professor", 18, "v.singh@eduplus.demo"),
            ("Prof. Meera Iyer", "M.Iyer", "Assistant Professor", 18, "m.iyer@eduplus.demo"),
            ("Prof. Suresh Babu", "S.Babu", "Assistant Professor", 18, "s.babu@eduplus.demo"),
            ("Prof. Deepa Krishnan", "D.Krishnan", "Assistant Professor", 18, "d.krishnan@eduplus.demo"),
            ("Prof. Rahul Gupta", "R.Gupta", "Assistant Professor", 18, "r.gupta@eduplus.demo"),
            ("Prof. Swati Joshi", "S.Joshi", "Assistant Professor", 18, "s.joshi@eduplus.demo"),
        ]
        for name, short_name, desig, cap, email in teacher_data:
            if not db.query(Teacher).filter(Teacher.email == email).first():
                db.add(Teacher(
                    department_id=dept.id,
                    name=name,
                    short_name=short_name,
                    designation=desig,
                    weekly_workload_cap=cap,
                    email=email,
                ))
                stats["teachers"] += 1
        db.commit()

        # 7. Subjects (Year 3 Core & Electives)
        subject_data = [
            ("AIML301", "Machine Learning", "ML", 3, "3-0-2", False),
            ("AIML302", "Deep Learning", "DL", 3, "3-0-2", False),
            ("AIML303", "Data Engineering", "DE", 3, "3-1-0", False),
            ("AIML304", "Mathematics for AI", "Math", 3, "3-1-0", False),
            ("AIML305", "Elective I: Computer Vision", "CV", 3, "3-0-0", True),
            ("AIML306", "Elective I: Natural Language Processing", "NLP", 3, "3-0-0", True),
            ("AIML307", "Elective I: Robotics", "Robo", 3, "3-0-0", True),
        ]
        for code, s_name, s_short, yr, ltp, is_elec in subject_data:
            if not db.query(Subject).filter(Subject.department_id == dept.id, Subject.code == code).first():
                db.add(Subject(
                    department_id=dept.id,
                    code=code,
                    name=s_name,
                    short_name=s_short,
                    year_number=yr,
                    ltp_credits=ltp,
                    is_elective=is_elec,
                ))
                stats["subjects"] += 1
        db.commit()

        # 8. User Accounts (Mock credentials with secure hashing)
        users = [
            ("admin@eduplus.demo", "admin123", "admin"),
            ("teacher@eduplus.demo", "teacher123", "teacher"),
            ("student@eduplus.demo", "student123", "student"),
        ]
        for u_email, u_pass, u_role in users:
            if not db.query(UserAccount).filter(UserAccount.email == u_email).first():
                db.add(UserAccount(
                    email=u_email,
                    password_hash=get_password_hash(u_pass),
                    role=u_role,
                    department_id=dept.id,
                    is_active=True,
                ))
                stats["users"] += 1
        db.commit()

        # 9. Teaching Assignments & Session Requirements (Year 3 Div A Baseline)
        from backend.app.models.scheduling import TeachingAssignment, SessionRequirement
        stats["teaching_assignments"] = 0
        stats["session_requirements"] = 0
        ay3 = db.query(AcademicYear).filter(AcademicYear.department_id == dept.id, AcademicYear.year_number == 3).first()
        if ay3:
            div3a = db.query(Division).filter(Division.academic_year_id == ay3.id, Division.name == "A").first()
            if div3a:
                existing_tas = db.query(TeachingAssignment).filter(TeachingAssignment.division_id == div3a.id).count()
                if existing_tas == 0:
                    subj_map = {s.code: s for s in db.query(Subject).filter(Subject.department_id == dept.id).all()}
                    tchr_map = {t.email: t for t in db.query(Teacher).filter(Teacher.department_id == dept.id).all()}
                    batches = {b.name: b for b in db.query(Batch).filter(Batch.division_id == div3a.id).all()}

                    ta_specs = [
                        ("AIML301", "admin@eduplus.demo", "lecture", None, 3, 1),
                        ("AIML301", "teacher@eduplus.demo", "practical", "B1", 1, 2),
                        ("AIML301", "teacher@eduplus.demo", "practical", "B2", 1, 2),
                        ("AIML301", "teacher@eduplus.demo", "practical", "B3", 1, 2),
                        ("AIML302", "v.singh@eduplus.demo", "lecture", None, 3, 1),
                        ("AIML302", "v.singh@eduplus.demo", "practical", "B1", 1, 2),
                        ("AIML302", "v.singh@eduplus.demo", "practical", "B2", 1, 2),
                        ("AIML302", "v.singh@eduplus.demo", "practical", "B3", 1, 2),
                        ("AIML303", "s.patel@eduplus.demo", "lecture", None, 3, 1),
                        ("AIML303", "s.patel@eduplus.demo", "tutorial", None, 1, 1),
                        ("AIML304", "a.desai@eduplus.demo", "lecture", None, 3, 1),
                        ("AIML304", "s.joshi@eduplus.demo", "tutorial", None, 1, 1),
                        ("AIML305", "v.singh@eduplus.demo", "lecture", None, 3, 1),
                        ("AIML306", "m.iyer@eduplus.demo", "lecture", None, 3, 1),
                        ("AIML307", "s.babu@eduplus.demo", "lecture", None, 3, 1),
                    ]
                    for code, temail, stype, bname, wcount, dur in ta_specs:
                        s = subj_map.get(code)
                        t = tchr_map.get(temail)
                        b = batches.get(bname) if bname else None
                        if s and t:
                            ta = TeachingAssignment(
                                subject_id=s.id,
                                division_id=div3a.id,
                                teacher_id=t.id,
                                session_type=stype,
                                batch_id=b.id if b else None,
                            )
                            db.add(ta)
                            db.flush()
                            stats["teaching_assignments"] += 1
                            req = SessionRequirement(
                                teaching_assignment_id=ta.id,
                                weekly_count=wcount,
                                duration_hours=dur,
                            )
                            db.add(req)
                            stats["session_requirements"] += 1
                    db.commit()

        logger.info(f"Database seed complete: {stats}")
        return stats

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    result = seed_database()
    print("Seed execution finished:", result)

