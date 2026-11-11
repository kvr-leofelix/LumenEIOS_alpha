"""Read-only access to the question bank for Differentiated Homework.

load_candidate_questions loads only the fields the selector needs: correct answers, rubrics
and options are never loaded, so they can't leak into homework selections.
load_question_snapshots loads full copies (including answers) for saving into a draft only.
Questions are never modified.

School and subject filters are applied in the SQL query, not after loading.

Rows whose stored values have the wrong type (SQLite doesn't enforce column types) are
skipped and their IDs reported, so one bad row can't block selection for everyone.

Known data limits (as of this version):
- No topic, difficulty or review/approval field exists, so none is used.
- `competency` is free text; the selector normalises it and reports unsupported values.
- `subject_id` is not a foreign key, so an unknown subject simply matches nothing.
"""
import logging
from typing import Dict, List

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import QuestionBankItem
from backend.app.modules.differentiated_homework.schemas import (
    CandidateQuestion,
    QuestionBankLoad,
    QuestionSnapshot,
)

logger = logging.getLogger(__name__)


async def load_candidate_questions(db: AsyncSession, school_id: str, subject_id: str) -> QuestionBankLoad:
    """Return the school's questions for one subject, ordered by question ID."""
    result = await db.execute(
        select(
            QuestionBankItem.id,
            QuestionBankItem.school_id,
            QuestionBankItem.subject_id,
            QuestionBankItem.text,
            QuestionBankItem.type,
            QuestionBankItem.marks,
            QuestionBankItem.competency,
            QuestionBankItem.bloom_level,
            QuestionBankItem.is_ai_generated,
        )
        .filter(QuestionBankItem.school_id == school_id, QuestionBankItem.subject_id == subject_id)
        .order_by(QuestionBankItem.id)
    )

    candidates, malformed = [], []
    for row in result.all():
        try:
            candidates.append(CandidateQuestion(**row._mapping))
        except ValidationError:
            malformed.append(str(row.id))

    if malformed:
        logger.warning("Skipped %d malformed question bank row(s).", len(malformed))
    return QuestionBankLoad(candidates=candidates, malformed_question_ids=malformed)


async def load_question_snapshots(
    db: AsyncSession, question_ids: List[str], school_id: str, subject_id: str
) -> Dict[str, QuestionSnapshot]:
    """Load full copies of specific questions, for saving into a draft.

    Unlike load_candidate_questions, this includes options, the answer key and the rubric,
    because a saved draft must keep a complete copy. Callers must never return those two
    fields in an API response. Questions outside the school or subject, missing questions and
    malformed rows are simply absent from the result.
    """
    if not question_ids:
        return {}
    result = await db.execute(
        select(
            QuestionBankItem.id,
            QuestionBankItem.text,
            QuestionBankItem.type,
            QuestionBankItem.options_json,
            QuestionBankItem.marks,
            QuestionBankItem.competency,
            QuestionBankItem.bloom_level,
            QuestionBankItem.is_ai_generated,
            QuestionBankItem.correct_answer,
            QuestionBankItem.marking_rubric,
        ).filter(
            QuestionBankItem.id.in_(question_ids),
            QuestionBankItem.school_id == school_id,
            QuestionBankItem.subject_id == subject_id,
        )
    )
    snapshots: Dict[str, QuestionSnapshot] = {}
    for row in result.all():
        try:
            snapshots[row.id] = QuestionSnapshot(**row._mapping)
        except ValidationError:
            logger.warning("Skipped a malformed question bank row while saving a draft.")
    return snapshots
