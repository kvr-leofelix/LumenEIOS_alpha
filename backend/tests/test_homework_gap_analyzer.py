import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.app.models.entities import Student, StudentCompetencySnapshot
from backend.app.modules.differentiated_homework.competency_adapter import (
    SOURCE,
    load_competency_profile,
)
from backend.app.modules.differentiated_homework.gap_analyzer import analyze_gaps
from backend.app.modules.differentiated_homework.schemas import CompetencyProfile


def make_profile(lu, cu, au, ct, baseline=None):
    return CompetencyProfile(
        student_id="student-test",
        scores={"LU": lu, "CU": cu, "AU": au, "CT": ct},
        baseline=baseline,
        source="test",
    )


# --- Gap Analyzer: pure logic -------------------------------------------------


def test_single_weakest_competency():
    result = analyze_gaps(make_profile(lu=48, cu=74, au=62, ct=50))

    assert result.weakest == ["LU"]
    assert result.has_single_weakest is True
    assert [g.competency for g in result.ranked] == ["LU", "CT", "AU", "CU"]
    assert [g.rank for g in result.ranked] == [1, 2, 3, 4]
    assert (result.lowest_score, result.highest_score, result.spread) == (48, 74, 26)
    assert result.notes == []


def test_tie_reports_every_tied_competency():
    result = analyze_gaps(make_profile(lu=50, cu=70, au=80, ct=50))

    assert result.weakest == ["LU", "CT"]
    assert result.has_single_weakest is False
    assert [(g.competency, g.rank) for g in result.ranked] == [("LU", 1), ("CT", 1), ("CU", 3), ("AU", 4)]
    assert "tie" in result.notes[0]


def test_all_equal_scores_have_no_weakest():
    result = analyze_gaps(make_profile(lu=70, cu=70, au=70, ct=70))

    assert result.weakest == []
    assert result.has_single_weakest is False
    assert result.spread == 0
    assert all(g.rank == 1 for g in result.ranked)
    assert "equal" in result.notes[0]


def test_a_high_weakest_score_is_still_reported_without_a_threshold():
    # No "needs support" threshold is applied: weakness is relative only.
    result = analyze_gaps(make_profile(lu=95, cu=97, au=98, ct=99))

    assert result.weakest == ["LU"]
    assert result.lowest_score == 95


def test_change_from_baseline():
    baseline = {"LU": 60, "CU": 80, "AU": 50, "CT": 50}
    result = analyze_gaps(make_profile(lu=48, cu=74, au=62, ct=50, baseline=baseline))
    by_name = {g.competency: g for g in result.ranked}

    assert by_name["LU"].change_from_baseline == -12
    assert by_name["CU"].change_from_baseline == -6
    assert by_name["AU"].change_from_baseline == 12
    assert by_name["CT"].change_from_baseline == 0


def test_baseline_fields_are_empty_when_no_baseline():
    result = analyze_gaps(make_profile(lu=48, cu=74, au=62, ct=50))

    assert all(g.baseline is None and g.change_from_baseline is None for g in result.ranked)


def test_boundary_scores_are_accepted():
    result = analyze_gaps(make_profile(lu=0, cu=100, au=50, ct=100))

    assert result.weakest == ["LU"]
    assert result.spread == 100


def test_source_is_carried_through():
    assert analyze_gaps(make_profile(lu=1, cu=2, au=3, ct=4)).source == "test"


# --- Input validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "scores",
    [
        {"LU": 101, "CU": 70, "AU": 70, "CT": 70},  # above range
        {"LU": -1, "CU": 70, "AU": 70, "CT": 70},  # below range
        {"LU": 70.5, "CU": 70, "AU": 70, "CT": 70},  # not an integer
        {"LU": "70", "CU": 70, "AU": 70, "CT": 70},  # text, not converted
        {"LU": True, "CU": 70, "AU": 70, "CT": 70},  # boolean, not converted
        {"LU": 70, "CU": 70, "AU": 70},  # missing CT
        {"LU": 70, "CU": 70, "AU": 70, "CT": 70, "XX": 70},  # unknown competency
    ],
)
def test_invalid_scores_are_rejected(scores):
    with pytest.raises(ValidationError):
        CompetencyProfile(student_id="s", scores=scores, source="test")


def test_incomplete_baseline_is_rejected():
    with pytest.raises(ValidationError):
        make_profile(lu=1, cu=2, au=3, ct=4, baseline={"LU": 60})


def test_profile_cannot_be_modified_after_creation():
    profile = make_profile(lu=1, cu=2, au=3, ct=4)
    with pytest.raises(ValidationError):
        profile.student_id = "someone-else"


# --- Adapter: reads existing Student data (temporary database) ---------------


def new_student(**scores):
    return Student(
        id=f"gap-test-{uuid.uuid4().hex[:10]}",
        school_id="school-1",
        class_id="class-8a",
        class_name="Class 8-A",
        name="Gap Analyzer Test Student",
        roll_no=999,
        **scores,
    )


@pytest.mark.asyncio
async def test_adapter_returns_none_for_unknown_student(db_session):
    assert await load_competency_profile(db_session, "no-such-student") is None


@pytest.mark.asyncio
async def test_adapter_reads_scores_and_baseline_without_writing(db_session):
    student = new_student(
        lu_score=48, cu_score=74, au_score=62, ct_score=50, overall_score=59,
        baseline_lu=60, baseline_cu=80, baseline_au=50, baseline_ct=50, baseline_overall=60,
    )
    db_session.add(student)
    await db_session.commit()
    snapshots_before = await db_session.scalar(select(func.count()).select_from(StudentCompetencySnapshot))

    try:
        profile = await load_competency_profile(db_session, student.id)

        assert profile.source == SOURCE
        assert profile.scores == {"LU": 48, "CU": 74, "AU": 62, "CT": 50}
        assert profile.baseline == {"LU": 60, "CU": 80, "AU": 50, "CT": 50}
        assert analyze_gaps(profile).weakest == ["LU"]

        # Read-only: nothing pending, scores unchanged, no snapshot written.
        assert not db_session.new and not db_session.dirty
        await db_session.refresh(student)
        assert (student.lu_score, student.cu_score, student.au_score, student.ct_score) == (48, 74, 62, 50)
        snapshots_after = await db_session.scalar(select(func.count()).select_from(StudentCompetencySnapshot))
        assert snapshots_after == snapshots_before
    finally:
        await db_session.delete(student)
        await db_session.commit()


@pytest.mark.asyncio
async def test_adapter_rejects_out_of_range_stored_scores(db_session):
    # The database has no range constraint, so bad data must fail loudly, not be clamped.
    student = new_student(lu_score=150, cu_score=70, au_score=70, ct_score=70)
    db_session.add(student)
    await db_session.commit()

    try:
        with pytest.raises(ValidationError):
            await load_competency_profile(db_session, student.id)
    finally:
        await db_session.delete(student)
        await db_session.commit()
