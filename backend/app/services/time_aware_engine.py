import uuid
from typing import Dict, List, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.entities import (
    CurriculumDay,
    InstructionalDisruption,
    CurriculumProposal,
    AuditEvent,
    utc_now,
)


def calculate_pacing_metrics(
    total_official_days: int,
    current_day: int,
    disruptions: List[InstructionalDisruption],
    curriculum_days: List[CurriculumDay]
) -> Dict[str, Any]:
    """
    Deterministic Time-Aware Pedagogical Engine.
    Calculates actual instructional contact days left, deficit/buffer, and risk status.
    """
    total_lost_days = sum(d.days_lost for d in disruptions)
    gross_remaining_days = max(0, total_official_days - current_day)
    remaining_instructional_days = max(0.0, gross_remaining_days - total_lost_days)

    pending_days = [
        d for d in curriculum_days
        if d.status in ("pending", "in-progress")
    ]
    core_concepts_remaining = sum(1 for d in pending_days if d.classification == "core")
    supplementary_topics_remaining = sum(1 for d in pending_days if d.classification == "supplementary")

    total_periods_needed = core_concepts_remaining + supplementary_topics_remaining
    pacing_buffer = round(remaining_instructional_days - total_periods_needed, 1)

    if pacing_buffer < -3:
        risk_status = "high"
        risk_label = f"High Pacing Risk (Deficit: {abs(pacing_buffer)} days)"
    elif pacing_buffer <= 3:
        risk_status = "medium"
        risk_label = f"Tight Pacing (Buffer: {pacing_buffer} days)"
    else:
        risk_status = "low"
        risk_label = "On Track (Healthy Buffer)"

    return {
        "total_official_days": total_official_days,
        "current_day": current_day,
        "total_lost_days": total_lost_days,
        "remaining_instructional_days": remaining_instructional_days,
        "core_concepts_remaining": core_concepts_remaining,
        "supplementary_topics_remaining": supplementary_topics_remaining,
        "total_periods_needed_original": total_periods_needed,
        "pacing_buffer": pacing_buffer,
        "risk_status": risk_status,
        "risk_label": risk_label,
    }


def generate_compression_proposal(
    curriculum_days: List[CurriculumDay],
    pacing_metrics: Dict[str, Any],
    school_id: str,
    class_id: str
) -> Tuple[CurriculumProposal, List[CurriculumDay], List[CurriculumDay]]:
    """
    Constructs a 60/40 Syllabus Compression proposal.
    Guarantees 100% of Core Competencies remain protected in live classroom contact hours.
    """
    pending_days = [
        d for d in curriculum_days
        if d.status in ("pending", "in-progress")
    ]
    core_topics = [d for d in pending_days if d.classification == "core"]
    supp_topics = [d for d in pending_days if d.classification == "supplementary"]

    # Reassign ~65% of pending supplementary topics to flipped homework
    reassigned_count = min(len(supp_topics), max(6, round(len(supp_topics) * 0.65)))
    reassigned_topics = supp_topics[:reassigned_count]

    # Integrate a subset via cross-curricular projects
    integrated_count = min(len(supp_topics) - reassigned_count, 4)
    integrated_topics = supp_topics[reassigned_count : reassigned_count + integrated_count]

    days_saved = reassigned_count + (integrated_count // 2) + 3
    original_duration = len(pending_days)
    revised_duration = max(len(core_topics), original_duration - days_saved)

    proposal = CurriculumProposal(
        id=f"prop-{uuid.uuid4().hex[:12]}",
        school_id=school_id,
        class_id=class_id,
        version_number=2,
        original_duration_days=original_duration,
        revised_duration_days=revised_duration,
        days_saved=days_saved,
        topics_preserved_count=len(core_topics),
        topics_reassigned_count=reassigned_count,
        topics_integrated_count=integrated_count,
        status="pending",
        trade_offs_json=[
            "100% of NEP 2020 Core Essential Competencies are strictly protected in classroom contact hours.",
            f"{reassigned_count} exploratory inquiry topics converted to guided flipped homework with parent verification rubrics.",
            "Cross-curricular synergies with Science and Social Studies recover teaching periods without dropping outcomes.",
            "Formative exit tickets will verify self-directed topics before final unit summative exams."
        ],
        remediation_requirements_json=[
            "Provide printed scaffolding guides for low-tech students lacking high-speed internet.",
            "Schedule 15-minute peer mentoring circles for students with Language Understanding (LU) deficits.",
            "Deploy 5-minute mastery checks at the beginning of each core lesson."
        ],
        reassigned_topic_ids=[t.id for t in reassigned_topics],
        integrated_topic_ids=[t.id for t in integrated_topics]
    )

    return proposal, reassigned_topics, integrated_topics

