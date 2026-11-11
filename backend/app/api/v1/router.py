from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.schools import router as schools_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.teachers import router as teachers_router
from backend.app.api.v1.classes import router as classes_router
from backend.app.api.v1.calendar import router as calendar_router
from backend.app.api.v1.assessments import router as assessments_router
from backend.app.api.v1.competencies import router as competencies_router
from backend.app.modules.differentiated_homework.router import router as homework_router
from backend.app.api.v1.curriculum import router as curriculum_router
from backend.app.api.v1.time_aware import router as time_aware_router
from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.ocr import router as ocr_router
from backend.app.api.v1.model_registry import router as model_registry_router
from backend.app.api.v1.notifications import router as notifications_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.onboarding import router as onboarding_router
from backend.app.api.v1.subscriptions import router as subscriptions_router
from backend.app.api.v1.assistant import router as assistant_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(schools_router)
api_router.include_router(users_router)
api_router.include_router(teachers_router)
api_router.include_router(classes_router)
api_router.include_router(calendar_router)
api_router.include_router(assessments_router)
api_router.include_router(competencies_router)
api_router.include_router(homework_router)
api_router.include_router(curriculum_router)
api_router.include_router(time_aware_router)
api_router.include_router(documents_router)
api_router.include_router(ocr_router)
api_router.include_router(model_registry_router)
api_router.include_router(notifications_router)
api_router.include_router(reports_router)
api_router.include_router(audit_router)
api_router.include_router(admin_router)
api_router.include_router(onboarding_router)
api_router.include_router(subscriptions_router)
api_router.include_router(assistant_router)

