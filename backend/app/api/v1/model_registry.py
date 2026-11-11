from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.models.entities import ModelEvaluation, ModelDeployment, User, AuditEvent, utc_now
from backend.app.schemas.model_registry import (
    ModelEvaluationOut,
    ModelDeploymentOut,
    ModelRollbackRequest,
)
from backend.app.services.model_training_service import check_model_promotion_criteria

router = APIRouter(prefix="/model-registry", tags=["OCR Model Registry & Training"])


@router.get("/evaluations", response_model=List[ModelEvaluationOut])
async def list_model_evaluations(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    res = await db.execute(select(ModelEvaluation).order_by(ModelEvaluation.evaluated_at.desc()))
    return res.scalars().all()


@router.get("/deployments", response_model=List[ModelDeploymentOut])
async def list_model_deployments(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    res = await db.execute(select(ModelDeployment).order_by(ModelDeployment.deployed_at.desc()))
    return res.scalars().all()


@router.post("/deployments/{model_id}/promote")
async def promote_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    eval_res = await db.execute(
        select(ModelEvaluation).filter(ModelEvaluation.model_id == model_id).order_by(ModelEvaluation.evaluated_at.desc())
    )
    evaluation = eval_res.scalars().first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="No evaluation found for candidate model.")

    passed, reason = check_model_promotion_criteria(evaluation.cer, evaluation.wer, evaluation.field_accuracy)
    if not passed:
        raise HTTPException(status_code=400, detail=f"Promotion rejected: {reason}")

    # Deactivate existing active deployment
    active_res = await db.execute(select(ModelDeployment).filter(ModelDeployment.is_active == True))
    for dep in active_res.scalars().all():
        dep.is_active = False

    new_dep = ModelDeployment(
        model_id=model_id,
        model_version=evaluation.model_version,
        provider="trocr-fine-tuned",
        is_active=True,
        deployed_by=admin.name
    )
    db.add(new_dep)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=admin.id,
        user_name=admin.name,
        action="Promoted OCR Model to Production",
        details=f"Promoted {model_id} (CER: {evaluation.cer*100:.1f}%, WER: {evaluation.wer*100:.1f}%)",
        category="system"
    )
    db.add(audit)
    await db.commit()
    return {"message": f"Model {model_id} successfully promoted to production.", "active_version": evaluation.model_version}


@router.post("/deployments/{model_id}/rollback")
async def rollback_model(
    model_id: str,
    req: ModelRollbackRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    res = await db.execute(select(ModelDeployment).filter(ModelDeployment.model_id == model_id, ModelDeployment.is_active == True))
    current_active = res.scalars().first()
    if current_active:
        current_active.is_active = False
        current_active.rollback_reason = req.rollback_reason

    # Activate baseline
    baseline = ModelDeployment(
        model_id="microsoft/trocr-base-handwritten",
        model_version="v1.0-baseline",
        provider="simulated",
        is_active=True,
        deployed_by=admin.name,
        rollback_reason=f"Rollback from {model_id}: {req.rollback_reason}"
    )
    db.add(baseline)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=admin.id,
        user_name=admin.name,
        action="Rolled Back OCR Model",
        details=f"Reverted from {model_id} to baseline. Reason: {req.rollback_reason}",
        category="system"
    )
    db.add(audit)
    await db.commit()
    return {"message": f"Successfully rolled back from {model_id}.", "current_active": "v1.0-baseline"}

