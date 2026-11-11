"""TEMPORARY competency data source for Differentiated Homework.

This is the only place in the module that reads competency data. It exists because the
assessment engine doesn't provide a diagnosis interface yet. When it does, replace this
adapter and keep the rest of the module unchanged.

Assumptions about the data it reads:
- Scores come from the live columns on `Student` (lu_score, cu_score, au_score, ct_score)
  and the baseline_* columns. One value per competency, not per subject or topic.
- Those values are written by several paths, some of which use request input, fixed
  increments or simulated grading. Treat them as unverified, not as diagnostic evidence.
- The database doesn't enforce a 0-100 range. Out-of-range values raise a validation error
  here instead of being silently corrected.

This module only reads. It never writes scores.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Student
from backend.app.modules.differentiated_homework.schemas import CompetencyProfile

SOURCE = "student_live_scores"


async def load_competency_profile(db: AsyncSession, student_id: str) -> Optional[CompetencyProfile]:
    """Return the student's competency profile, or None if the student doesn't exist."""
    result = await db.execute(select(Student).filter(Student.id == student_id))
    student = result.scalars().first()
    if student is None:
        return None

    return CompetencyProfile(
        student_id=student.id,
        scores={
            "LU": student.lu_score,
            "CU": student.cu_score,
            "AU": student.au_score,
            "CT": student.ct_score,
        },
        baseline={
            "LU": student.baseline_lu,
            "CU": student.baseline_cu,
            "AU": student.baseline_au,
            "CT": student.baseline_ct,
        },
        source=SOURCE,
    )
