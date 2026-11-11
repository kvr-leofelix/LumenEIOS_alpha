import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
    JSON
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)  # admin, principal, teacher, student, parent
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    designation = Column(String(255), nullable=True)
    avatar = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    memberships = relationship("SchoolMembership", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    phone = Column(String(40), nullable=True)
    address = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)


class School(Base):
    __tablename__ = "schools"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False)
    state = Column(String(100), nullable=False, index=True)
    infrastructure_tier = Column(String(50), nullable=False)  # high-tech, standard, low-tech
    academic_year = Column(String(50), default="2026-2027", nullable=False)
    principal_id = Column(String(64), nullable=True)
    principal_name = Column(String(255), nullable=True)
    student_count = Column(Integer, default=0, nullable=False)
    teacher_count = Column(Integer, default=0, nullable=False)
    class_count = Column(Integer, default=0, nullable=False)
    pacing_risk = Column(String(50), default="low", nullable=False)  # low, medium, high
    description = Column(Text, nullable=True)
    official_working_days = Column(Integer, default=220, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    memberships = relationship("SchoolMembership", back_populates="school", cascade="all, delete-orphan")


class SchoolMembership(Base):
    __tablename__ = "school_memberships"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="memberships")
    school = relationship("School", back_populates="memberships")


class ClassSection(Base):
    __tablename__ = "classes"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    grade = Column(Integer, nullable=False)
    section = Column(String(10), nullable=False)
    name = Column(String(100), nullable=False)
    class_teacher_id = Column(String(64), nullable=True)
    class_teacher_name = Column(String(255), nullable=True)
    student_count = Column(Integer, default=0, nullable=False)
    subject_ids_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    grade = Column(Integer, default=8, nullable=False)
    icon_name = Column(String(50), default="BookOpen", nullable=False)


class Student(Base):
    __tablename__ = "students"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String(64), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    class_name = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    roll_no = Column(Integer, nullable=False)
    gender = Column(String(20), default="Other", nullable=False)
    attendance_pct = Column(Float, default=90.0, nullable=False)
    
    # Live / Graded Competencies
    lu_score = Column(Integer, default=70, nullable=False)
    cu_score = Column(Integer, default=70, nullable=False)
    au_score = Column(Integer, default=70, nullable=False)
    ct_score = Column(Integer, default=70, nullable=False)
    overall_score = Column(Integer, default=70, nullable=False)

    # Diagnostic Baseline
    baseline_lu = Column(Integer, default=60, nullable=False)
    baseline_cu = Column(Integer, default=60, nullable=False)
    baseline_au = Column(Integer, default=60, nullable=False)
    baseline_ct = Column(Integer, default=60, nullable=False)
    baseline_overall = Column(Integer, default=60, nullable=False)

    learning_modality = Column(String(50), default="Visual", nullable=False)
    parent_id = Column(String(64), nullable=True, index=True)
    homework_completion_rate = Column(Float, default=85.0, nullable=False)
    needs_support = Column(Boolean, default=False, nullable=False)
    support_area = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class StudentOcrHistory(Base):
    __tablename__ = "student_ocr_history"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    extracted_text = Column(Text, nullable=False)
    pages_processed = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ParentStudentLink(Base):
    __tablename__ = "parent_student_links"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    parent_user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class InstructionalDisruption(Base):
    __tablename__ = "instructional_disruptions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(20), nullable=False)
    reason = Column(String(100), nullable=False)
    days_lost = Column(Float, default=1.0, nullable=False)
    recorded_by = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String(64), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    cycle_number = Column(Integer, default=1, nullable=False)
    date = Column(String(20), nullable=False)
    duration_minutes = Column(Integer, default=45, nullable=False)
    total_marks = Column(Integer, default=25, nullable=False)
    status = Column(String(50), default="scheduled", nullable=False)  # draft, scheduled, graded, closed
    competency_focus_json = Column(JSON, default=list, nullable=False)
    questions_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class AssignmentOcrUpload(Base):
    __tablename__ = "assignment_ocr_uploads"

    history_id = Column(String(64), ForeignKey("student_ocr_history.id", ondelete="CASCADE"), primary_key=True)
    assessment_id = Column(String(64), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)


class AssessmentSubmission(Base):
    __tablename__ = "assessment_submissions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    assessment_id = Column(String(64), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    student_name = Column(String(255), nullable=False)
    marks_obtained = Column(Integer, nullable=False)
    total_marks = Column(Integer, nullable=False)
    percentage = Column(Integer, nullable=False)
    lu_score = Column(Integer, default=70, nullable=False)
    cu_score = Column(Integer, default=70, nullable=False)
    au_score = Column(Integer, default=70, nullable=False)
    ct_score = Column(Integer, default=70, nullable=False)
    overall_score = Column(Integer, default=70, nullable=False)
    feedback = Column(Text, nullable=True)
    submission_date = Column(String(20), nullable=False)
    is_scanned = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class StudentCompetencySnapshot(Base):
    __tablename__ = "student_competency_snapshots"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_number = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, default=utc_now, nullable=False)
    lu_score = Column(Integer, nullable=False)
    cu_score = Column(Integer, nullable=False)
    au_score = Column(Integer, nullable=False)
    ct_score = Column(Integer, nullable=False)
    overall_score = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)


class HomeworkRemediation(Base):
    __tablename__ = "homework_remediations"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    student_name = Column(String(255), nullable=False)
    class_id = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    competency_target = Column(String(20), nullable=False)  # LU, CU, AU, CT
    reason = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    due_date = Column(String(20), nullable=False)
    status = Column(String(50), default="assigned", nullable=False)  # assigned, submitted, reviewed
    score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class CurriculumDay(Base):
    __tablename__ = "curriculum_days"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    day_number = Column(Integer, nullable=False, index=True)
    class_id = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False)
    topic = Column(String(255), nullable=False)
    objective = Column(Text, nullable=False)
    teaching_process = Column(Text, nullable=False)
    measurable_outcome = Column(Text, nullable=False)
    estimated_duration_mins = Column(Integer, default=45, nullable=False)
    vark_modality = Column(String(50), default="Visual", nullable=False)
    bloom_level = Column(String(50), default="Apply", nullable=False)
    classification = Column(String(50), default="core", nullable=False)  # core, supplementary
    status = Column(String(50), default="pending", nullable=False)  # completed, in-progress, pending, compressed_to_homework, integrated
    prerequisites_json = Column(JSON, default=list, nullable=False)


class CurriculumProposal(Base):
    __tablename__ = "curriculum_proposals"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), nullable=False, index=True)
    class_id = Column(String(64), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    original_duration_days = Column(Integer, nullable=False)
    revised_duration_days = Column(Integer, nullable=False)
    days_saved = Column(Integer, nullable=False)
    topics_preserved_count = Column(Integer, nullable=False)
    topics_reassigned_count = Column(Integer, nullable=False)
    topics_integrated_count = Column(Integer, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, approved, rejected
    trade_offs_json = Column(JSON, default=list, nullable=False)
    remediation_requirements_json = Column(JSON, default=list, nullable=False)
    reassigned_topic_ids = Column(JSON, default=list, nullable=False)
    integrated_topic_ids = Column(JSON, default=list, nullable=False)
    created_by = Column(String(255), nullable=True)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class CrossCurricularProposal(Base):
    __tablename__ = "cross_curricular_proposals"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    school_id = Column(String(64), default="school-1", nullable=False)
    class_id = Column(String(64), default="class-8a", nullable=False)
    subject_ids_json = Column(JSON, default=list, nullable=False)
    subject_names_json = Column(JSON, default=list, nullable=False)
    target_day_numbers_json = Column(JSON, default=list, nullable=False)
    learning_objectives_json = Column(JSON, default=list, nullable=False)
    activity = Column(Text, nullable=False)
    vark_modality = Column(String(50), default="Visual", nullable=False)
    bloom_level = Column(String(50), default="Apply", nullable=False)
    estimated_duration_hours = Column(Float, default=3.0, nullable=False)
    time_saved_hours = Column(Float, default=2.0, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, accepted, rejected
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), nullable=False, index=True)
    uploader_id = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=True, index=True)
    doc_type = Column(String(50), default="source_material", nullable=True)  # source_material, answer_sheet
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    storage_path = Column(String(512), nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    content_hash = Column(String(128), nullable=True, index=True)
    extracted_text = Column(Text, nullable=True)
    status = Column(String(50), default="uploaded", nullable=False)  # uploaded, processing, ready, failed
    created_at = Column(DateTime, default=utc_now, nullable=False)


class OCRRun(Base):
    __tablename__ = "ocr_runs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), default="simulated", nullable=False)
    model_version = Column(String(100), default="v1.0", nullable=False)
    confidence_score = Column(Float, default=0.98, nullable=False)
    extraction_json = Column(JSON, default=dict, nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    ocr_run_id = Column(String(64), ForeignKey("ocr_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String(64), nullable=False, index=True)
    student_id = Column(String(64), nullable=False)
    assessment_id = Column(String(64), nullable=False)
    verified_marks = Column(Integer, nullable=False)
    total_marks = Column(Integer, nullable=False)
    verified_data_json = Column(JSON, default=dict, nullable=False)
    teacher_notes = Column(Text, nullable=True)
    status = Column(String(50), default="approved", nullable=False)
    reviewed_at = Column(DateTime, default=utc_now, nullable=False)


class DatasetExample(Base):
    __tablename__ = "dataset_examples"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    dataset_version = Column(String(50), default="v1.0", nullable=False, index=True)
    document_id = Column(String(64), nullable=False)
    split_type = Column(String(20), default="train", nullable=False)  # train, val, test
    ground_truth_text = Column(Text, nullable=False)
    verified_by = Column(String(255), nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    model_id = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    cer = Column(Float, nullable=False)  # Character Error Rate
    wer = Column(Float, nullable=False)  # Word Error Rate
    field_accuracy = Column(Float, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    status = Column(String(50), default="passed", nullable=False)
    notes = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=utc_now, nullable=False)


class ModelDeployment(Base):
    __tablename__ = "model_deployments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    model_id = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    deployed_by = Column(String(255), nullable=False)
    deployed_at = Column(DateTime, default=utc_now, nullable=False)
    rollback_reason = Column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info", nullable=False)  # info, warning, success, alert
    is_read = Column(Boolean, default=False, nullable=False)
    link = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), nullable=False, index=True)
    sender_id = Column(String(64), nullable=False)
    sender_name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    target_role = Column(String(50), default="teacher", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    timestamp = Column(String(50), nullable=False)
    user_id = Column(String(64), nullable=False)
    user_name = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # curriculum, assessment, user, system
    ip_address = Column(String(50), default="127.0.0.1", nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class QuestionBankItem(Base):
    __tablename__ = "question_bank_items"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), default="school-1", nullable=False, index=True)
    subject_id = Column(String(64), nullable=False, index=True)
    text = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # mcq, short, descriptive, practical
    options_json = Column(JSON, default=list, nullable=False)
    correct_answer = Column(Text, nullable=True)
    marking_rubric = Column(Text, nullable=True)
    marks = Column(Integer, default=2, nullable=False)
    competency = Column(String(20), default="CU", nullable=False)  # LU, CU, AU, CT
    bloom_level = Column(String(50), default="Understand", nullable=False)
    source_document_ids_json = Column(JSON, default=list, nullable=False)
    source_document_names_json = Column(JSON, default=list, nullable=False)
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class GradingBatch(Base):
    __tablename__ = "grading_batches"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), default="school-1", nullable=False, index=True)
    class_id = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False, index=True)
    assessment_id = Column(String(64), nullable=False, index=True)
    created_by = Column(String(64), nullable=False)
    status = Column(String(50), default="configuring", nullable=False)  # configuring, queued, processing, completed, completed_with_warnings, cancelled, failed
    total_files = Column(Integer, default=0, nullable=False)
    valid_files = Column(Integer, default=0, nullable=False)
    invalid_or_duplicate_files = Column(Integer, default=0, nullable=False)
    completed_files = Column(Integer, default=0, nullable=False)
    review_required_files = Column(Integer, default=0, nullable=False)
    failed_files = Column(Integer, default=0, nullable=False)
    concurrency_limit = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class GradingBatchItem(Base):
    __tablename__ = "grading_batch_items"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    batch_id = Column(String(64), ForeignKey("grading_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(64), nullable=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    page_range = Column(String(50), nullable=True)
    content_hash = Column(String(128), nullable=True, index=True)
    status = Column(String(50), default="uploaded", nullable=False)  # queued, uploading, uploaded, extracting_ocr, identifying_student, evaluating_answers, calculating_marks, completed, requires_review, failed, approved, invalid, duplicate, cancelled
    stage_progress = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    student_id = Column(String(64), nullable=True, index=True)
    student_name = Column(String(255), nullable=True)
    student_confidence = Column(Float, default=0.0, nullable=False)
    ocr_confidence = Column(Float, default=0.0, nullable=False)
    extracted_text = Column(Text, nullable=True)
    question_evaluations_json = Column(JSON, default=list, nullable=False)
    marks_obtained = Column(Integer, default=0, nullable=False)
    max_marks = Column(Integer, default=25, nullable=False)
    percentage = Column(Integer, default=0, nullable=False)
    grade = Column(String(10), default="B", nullable=False)
    competency_scores_json = Column(JSON, default=dict, nullable=False)
    requires_review = Column(Boolean, default=False, nullable=False)
    review_reasons_json = Column(JSON, default=list, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    submission_id = Column(String(64), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PayPalSubscription(Base):
    """One PayPal subscription for a school: kind is 'base' (flat fee) or 'seats' (per teacher)."""
    __tablename__ = "paypal_subscriptions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    school_id = Column(String(64), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    principal_user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(20), nullable=False)  # base, seats
    paypal_subscription_id = Column(String(64), unique=True, nullable=True, index=True)
    plan_id = Column(String(64), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="APPROVAL_PENDING", nullable=False)  # mirrors PayPal status
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


