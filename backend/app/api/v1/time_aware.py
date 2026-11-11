from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.models.entities import (
    ClassSection,
    InstructionalDisruption,
    CurriculumDay,
    CurriculumProposal,
    CrossCurricularProposal,
    User,
    AuditEvent,
    Notification,
    utc_now,
)
from backend.app.schemas.time_aware import (
    CalculatePacingRequest,
    PacingMetricsOut,
    CompressionProposalOut,
    TopicSummary,
    ProposalDecisionRequest,
    CrossCurricularProposalOut,
)
from backend.app.services.time_aware_engine import (
    calculate_pacing_metrics,
    generate_compression_proposal,
)

router = APIRouter(tags=["Time-Aware Pedagogical Engine"])


@router.post("/classes/{class_id}/time-aware/calculate", response_model=PacingMetricsOut)
async def calculate_class_pacing(
    class_id: str,
    req: CalculatePacingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cls_res = await db.execute(select(ClassSection).filter(ClassSection.id == class_id))
    cls = cls_res.scalars().first()
    school_id = cls.school_id if cls else "school-1"

    disruptions_res = await db.execute(select(InstructionalDisruption).filter(InstructionalDisruption.school_id == school_id))
    disruptions = disruptions_res.scalars().all()

    curriculum_res = await db.execute(select(CurriculumDay).filter(CurriculumDay.class_id == class_id))
    curriculum = curriculum_res.scalars().all()

    metrics = calculate_pacing_metrics(req.total_official_days, req.current_day, disruptions, curriculum)
    return PacingMetricsOut(**metrics)


@router.post("/classes/{class_id}/time-aware/compression-preview", response_model=CompressionProposalOut)
async def preview_syllabus_compression(
    class_id: str,
    req: CalculatePacingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher"))
):
    cls_res = await db.execute(select(ClassSection).filter(ClassSection.id == class_id))
    cls = cls_res.scalars().first()
    school_id = cls.school_id if cls else "school-1"

    disruptions_res = await db.execute(select(InstructionalDisruption).filter(InstructionalDisruption.school_id == school_id))
    disruptions = disruptions_res.scalars().all()

    curriculum_res = await db.execute(select(CurriculumDay).filter(CurriculumDay.class_id == class_id))
    curriculum = curriculum_res.scalars().all()

    metrics = calculate_pacing_metrics(req.total_official_days, req.current_day, disruptions, curriculum)
    proposal, reassigned, integrated = generate_compression_proposal(curriculum, metrics, school_id, class_id)

    # Persist or update pending proposal
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    return CompressionProposalOut(
        proposal_id=proposal.id,
        original_duration_days=proposal.original_duration_days,
        revised_duration_days=proposal.revised_duration_days,
        days_saved=proposal.days_saved,
        topics_preserved_count=proposal.topics_preserved_count,
        topics_reassigned_count=proposal.topics_reassigned_count,
        topics_integrated_count=proposal.topics_integrated_count,
        preserved_core_count=proposal.topics_preserved_count,
        reassigned_topics=[
            TopicSummary(
                id=t.id,
                day_number=t.day_number,
                topic=t.topic,
                objective=t.objective,
                classification=t.classification,
                estimated_duration_mins=t.estimated_duration_mins
            ) for t in reassigned
        ],
        integrated_topics=[
            TopicSummary(
                id=t.id,
                day_number=t.day_number,
                topic=t.topic,
                objective=t.objective,
                classification=t.classification,
                estimated_duration_mins=t.estimated_duration_mins
            ) for t in integrated
        ],
        trade_off_analysis=proposal.trade_offs_json,
        remediation_requirements=proposal.remediation_requirements_json,
    )


@router.post("/curriculum-proposals/{proposal_id}/approve")
async def approve_compression_proposal(
    proposal_id: str,
    req: ProposalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    res = await db.execute(select(CurriculumProposal).filter(CurriculumProposal.id == proposal_id))
    proposal = res.scalars().first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    proposal.status = "approved"
    proposal.approved_by = educator.name
    proposal.approved_at = utc_now()

    # Apply topic status updates in curriculum
    reassigned_set = set(proposal.reassigned_topic_ids)
    integrated_set = set(proposal.integrated_topic_ids)

    curriculum_res = await db.execute(select(CurriculumDay).filter(CurriculumDay.class_id == proposal.class_id))
    for day in curriculum_res.scalars().all():
        if day.id in reassigned_set:
            day.status = "compressed_to_homework"
        elif day.id in integrated_set:
            day.status = "integrated"

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Approved Time-Aware Syllabus Compression",
        details=f"Applied 60/40 compaction saving {proposal.days_saved} days. Preserved {proposal.topics_preserved_count} core concepts.",
        category="curriculum"
    )
    db.add(audit)

    notif = Notification(
        user_id="user-principal-1",
        title="Syllabus Compression Approved",
        message=f"{educator.name} approved compaction recovering {proposal.days_saved} instructional periods.",
        type="success",
        link="/principal/dashboard"
    )
    db.add(notif)

    await db.commit()
    return {
        "status": "approved",
        "proposal_id": proposal.id,
        "message": "Syllabus compression approved and applied transactionally.",
        "days_saved": proposal.days_saved,
    }


@router.post("/curriculum-proposals/{proposal_id}/reject")
async def reject_compression_proposal(
    proposal_id: str,
    req: ProposalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    res = await db.execute(select(CurriculumProposal).filter(CurriculumProposal.id == proposal_id))
    proposal = res.scalars().first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    proposal.status = "rejected"
    await db.commit()
    return {"message": "Proposal rejected."}


@router.get("/classes/{class_id}/curriculum/cross-curricular-proposals", response_model=List[CrossCurricularProposalOut])
async def list_cross_curricular_proposals(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(CrossCurricularProposal))
    proposals = res.scalars().all()
    return [
        CrossCurricularProposalOut(
            id=p.id,
            title=p.title,
            subject_ids=p.subject_ids_json,
            subject_names=p.subject_names_json,
            target_day_numbers=p.target_day_numbers_json,
            learning_objectives=p.learning_objectives_json,
            activity=p.activity,
            vark_modality=p.vark_modality,
            bloom_level=p.bloom_level,
            estimated_duration_hours=p.estimated_duration_hours,
            time_saved_hours=p.time_saved_hours,
            status=p.status
        ) for p in proposals
    ]


@router.post("/cross-curricular-proposals/{proposal_id}/accept")
async def accept_cross_curricular_proposal(
    proposal_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    res = await db.execute(select(CrossCurricularProposal).filter(CrossCurricularProposal.id == proposal_id))
    prop = res.scalars().first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    prop.status = "accepted"

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Approved Cross-Curricular Integration",
        details=f"Merged synergy project '{prop.title}', saving {prop.time_saved_hours} hours.",
        category="curriculum"
    )
    db.add(audit)
    await db.commit()
    return {"message": f"Proposal '{prop.title}' accepted.", "hours_saved": prop.time_saved_hours}


@router.post("/cross-curricular-proposals/{proposal_id}/reject")
async def reject_cross_curricular_proposal(
    proposal_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    res = await db.execute(select(CrossCurricularProposal).filter(CrossCurricularProposal.id == proposal_id))
    prop = res.scalars().first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    prop.status = "rejected"
    await db.commit()
    return {"message": "Proposal rejected."}
