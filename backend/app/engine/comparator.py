"""
backend/app/engine/comparator.py
EduPlus AI Timetable Maker — Timetable Version Comparator

Compares two TimetableVersion objects at the ScheduledSession level and
returns a structured diff: added, removed, moved, and changed sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.timetable import ScheduledSession, TimetableVersion


@dataclass
class SessionDiff:
    """A single session-level difference between two versions."""
    change_type: str    # 'added' | 'removed' | 'moved' | 'unchanged'
    assignment_id: str
    session_type: str
    teacher_id: str
    # Version A details (None for 'added')
    day_a: Optional[str] = None
    slot_a: Optional[str] = None
    room_a: Optional[str] = None
    # Version B details (None for 'removed')
    day_b: Optional[str] = None
    slot_b: Optional[str] = None
    room_b: Optional[str] = None


@dataclass
class VersionComparison:
    version_a_id: str
    version_b_id: str
    total_sessions_a: int
    total_sessions_b: int
    added: List[SessionDiff] = field(default_factory=list)
    removed: List[SessionDiff] = field(default_factory=list)
    moved: List[SessionDiff] = field(default_factory=list)
    unchanged: List[SessionDiff] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        return {
            "version_a_id": self.version_a_id,
            "version_b_id": self.version_b_id,
            "total_sessions_a": self.total_sessions_a,
            "total_sessions_b": self.total_sessions_b,
            "added": len(self.added),
            "removed": len(self.removed),
            "moved": len(self.moved),
            "unchanged": len(self.unchanged),
        }


def compare_versions(
    db: Session,
    version_a_id: str,
    version_b_id: str,
) -> VersionComparison:
    """
    Compare two timetable versions and return a structured diff.

    Matching logic: sessions are matched by assignment_id (same subject/teacher/group).
    Within matched sessions we detect moves (day/slot/room changed).
    """
    sessions_a = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == version_a_id)
        .all()
    )
    sessions_b = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == version_b_id)
        .all()
    )

    # Group by assignment_id — each assignment has potentially multiple sessions (weekly_count)
    # We match them positionally after sorting by (day, slot)
    def key_sort(s: ScheduledSession) -> Tuple:
        return (str(s.teaching_assignment_id), s.day_name, str(s.time_slot_id))

    map_a: Dict[str, List[ScheduledSession]] = {}
    for s in sessions_a:
        aid = str(s.teaching_assignment_id)
        map_a.setdefault(aid, []).append(s)
    for lst in map_a.values():
        lst.sort(key=lambda s: (s.day_name, str(s.time_slot_id)))

    map_b: Dict[str, List[ScheduledSession]] = {}
    for s in sessions_b:
        aid = str(s.teaching_assignment_id)
        map_b.setdefault(aid, []).append(s)
    for lst in map_b.values():
        lst.sort(key=lambda s: (s.day_name, str(s.time_slot_id)))

    all_assignment_ids = set(map_a) | set(map_b)

    result = VersionComparison(
        version_a_id=version_a_id,
        version_b_id=version_b_id,
        total_sessions_a=len(sessions_a),
        total_sessions_b=len(sessions_b),
    )

    for aid in all_assignment_ids:
        list_a = map_a.get(aid, [])
        list_b = map_b.get(aid, [])
        max_len = max(len(list_a), len(list_b))

        for i in range(max_len):
            sa = list_a[i] if i < len(list_a) else None
            sb = list_b[i] if i < len(list_b) else None

            if sa is None:
                # Added in B
                result.added.append(SessionDiff(
                    change_type="added",
                    assignment_id=aid,
                    session_type=sb.session_type,
                    teacher_id=str(sb.teacher_id),
                    day_b=sb.day_name,
                    slot_b=str(sb.time_slot_id),
                    room_b=str(sb.room_id),
                ))
            elif sb is None:
                # Removed from A
                result.removed.append(SessionDiff(
                    change_type="removed",
                    assignment_id=aid,
                    session_type=sa.session_type,
                    teacher_id=str(sa.teacher_id),
                    day_a=sa.day_name,
                    slot_a=str(sa.time_slot_id),
                    room_a=str(sa.room_id),
                ))
            else:
                same_slot = (sa.day_name == sb.day_name and str(sa.time_slot_id) == str(sb.time_slot_id))
                same_room = str(sa.room_id) == str(sb.room_id)
                if same_slot and same_room:
                    result.unchanged.append(SessionDiff(
                        change_type="unchanged",
                        assignment_id=aid,
                        session_type=sa.session_type,
                        teacher_id=str(sa.teacher_id),
                        day_a=sa.day_name,
                        slot_a=str(sa.time_slot_id),
                        room_a=str(sa.room_id),
                        day_b=sb.day_name,
                        slot_b=str(sb.time_slot_id),
                        room_b=str(sb.room_id),
                    ))
                else:
                    result.moved.append(SessionDiff(
                        change_type="moved",
                        assignment_id=aid,
                        session_type=sa.session_type,
                        teacher_id=str(sa.teacher_id),
                        day_a=sa.day_name,
                        slot_a=str(sa.time_slot_id),
                        room_a=str(sa.room_id),
                        day_b=sb.day_name,
                        slot_b=str(sb.time_slot_id),
                        room_b=str(sb.room_id),
                    ))

    return result

