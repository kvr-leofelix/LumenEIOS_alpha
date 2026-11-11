import pytest
from backend.app.models.entities import (
    CurriculumDay,
    InstructionalDisruption,
)
from backend.app.services.time_aware_engine import (
    calculate_pacing_metrics,
    generate_compression_proposal,
)


def test_calculate_pacing_metrics_healthy_buffer():
    # 220 official days, current day 50, 2 lost days, 100 pending periods (70 core + 30 supp)
    disruptions = [InstructionalDisruption(days_lost=2.0)]
    curriculum_days = [
        CurriculumDay(classification="core", status="pending") for _ in range(70)
    ] + [
        CurriculumDay(classification="supplementary", status="pending") for _ in range(30)
    ]

    metrics = calculate_pacing_metrics(
        total_official_days=220,
        current_day=50,
        disruptions=disruptions,
        curriculum_days=curriculum_days,
    )

    # Remaining = (220 - 50) - 2 = 168
    assert metrics["remaining_instructional_days"] == 168.0
    assert metrics["total_periods_needed_original"] == 100
    assert metrics["pacing_buffer"] == 68.0
    assert metrics["risk_status"] == "low"


def test_calculate_pacing_metrics_deficit():
    # 220 official days, current day 140, 16 lost days, 70 pending periods
    # Remaining = (220 - 140) - 16 = 64 days. Needed = 70. Buffer = -6 (high risk)
    disruptions = [InstructionalDisruption(days_lost=16.0)]
    curriculum_days = [
        CurriculumDay(classification="core", status="pending") for _ in range(50)
    ] + [
        CurriculumDay(classification="supplementary", status="pending") for _ in range(20)
    ]

    metrics = calculate_pacing_metrics(
        total_official_days=220,
        current_day=140,
        disruptions=disruptions,
        curriculum_days=curriculum_days,
    )

    assert metrics["remaining_instructional_days"] == 64.0
    assert metrics["total_periods_needed_original"] == 70
    assert metrics["pacing_buffer"] == -6.0
    assert metrics["risk_status"] == "high"


def test_generate_compression_proposal_preserves_core_competencies():
    # Invariant: 100% of core concepts MUST remain in classroom contact hours
    core_topics = [
        CurriculumDay(id=f"core-{i}", classification="core", status="pending")
        for i in range(50)
    ]
    supp_topics = [
        CurriculumDay(id=f"supp-{i}", classification="supplementary", status="pending")
        for i in range(25)
    ]
    all_topics = core_topics + supp_topics

    metrics = calculate_pacing_metrics(
        total_official_days=220,
        current_day=104,
        disruptions=[InstructionalDisruption(days_lost=16.0)],
        curriculum_days=all_topics,
    )

    proposal, reassigned, integrated = generate_compression_proposal(
        curriculum_days=all_topics,
        pacing_metrics=metrics,
        school_id="school-1",
        class_id="class-8a",
    )

    # Invariant check: core topics preserved count must equal the number of core topics
    assert proposal.topics_preserved_count == len(core_topics)
    # The reassigned topics must only be supplementary topics
    for topic in reassigned:
        assert topic.classification == "supplementary"
    for topic in integrated:
        assert topic.classification == "supplementary"
    # Days saved must be greater than zero
    assert proposal.days_saved > 0
    # Revised duration must accommodate all core topics
    assert proposal.revised_duration_days >= len(core_topics)

