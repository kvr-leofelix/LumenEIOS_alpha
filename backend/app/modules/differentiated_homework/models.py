"""Database tables owned by the Differentiated Homework module.

How these tables are created: there's no migration tool set up. On startup, init_db() calls
Base.metadata.create_all, which creates missing tables and never alters or drops existing
ones. These are new tables only, so adding them is non-destructive. This module is imported
through the API router before init_db runs, so the tables are registered in time.

Snapshots: each item stores a full copy of the question at save time, so later edits or
deletions in the question bank don't change a saved draft. The answer key and rubric are
stored for future grading, but no API response returns them.
"""
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
)
from sqlalchemy.orm import relationship

from backend.app.db.session import Base
from backend.app.models.entities import generate_uuid, utc_now

DRAFT_STATUSES = ("draft", "approved", "rejected", "assigned")


class HomeworkDraftRecord(Base):
    __tablename__ = "homework_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'assigned')", name="ck_homework_drafts_status"
        ),
    )

    id = Column(String(64), primary_key=True, default=generate_uuid)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False)
    created_by = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), default="draft", nullable=False, index=True)

    requested_questions = Column(Integer, nullable=False)
    max_total_marks = Column(Integer, nullable=True)
    include_ai_generated = Column(Boolean, nullable=False)
    question_count = Column(Integer, nullable=False)
    total_marks = Column(Integer, nullable=False)
    shortfall = Column(Integer, nullable=False)
    rationale_json = Column(JSON, nullable=False)
    notes_json = Column(JSON, default=list, nullable=False)

    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Optimistic-concurrency version counter, managed by SQLAlchemy: every UPDATE requires the
    # number this request read and adds 1. If another request changed the row in between, the
    # UPDATE matches nothing and SQLAlchemy raises StaleDataError (returned as 409).
    # An integer, not a timestamp: on Windows most consecutive clock readings are identical, so
    # a timestamp version could stay the same across two updates and miss a conflict.
    version = Column(Integer, nullable=False)

    __mapper_args__ = {"version_id_col": version}

    items = relationship(
        "HomeworkDraftItemRecord",
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="HomeworkDraftItemRecord.position",
        lazy="selectin",
    )


class HomeworkDraftItemRecord(Base):
    __tablename__ = "homework_draft_items"
    __table_args__ = (
        UniqueConstraint("draft_id", "position", name="uq_homework_draft_items_position"),
        UniqueConstraint("draft_id", "source_question_id", name="uq_homework_draft_items_question"),
    )

    id = Column(String(64), primary_key=True, default=generate_uuid)
    draft_id = Column(String(64), ForeignKey("homework_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    # Not a foreign key on purpose: the snapshot must survive if the bank question is deleted.
    source_question_id = Column(String(64), nullable=False)

    text = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)
    options_json = Column(JSON, default=list, nullable=False)
    marks = Column(Integer, nullable=False)
    competency = Column(String(20), nullable=False)
    competency_rank = Column(Integer, nullable=False)
    bloom_level = Column(String(50), nullable=False)
    is_ai_generated = Column(Boolean, nullable=False)
    # Stored for future grading. Never returned by any API response.
    correct_answer = Column(Text, nullable=True)
    marking_rubric = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    draft = relationship("HomeworkDraftRecord", back_populates="items")


class HomeworkAssignmentRecord(Base):
    """An approved draft issued to its student.

    Questions aren't copied: the assignment shows the draft's snapshot items, which can no
    longer change once the draft's status is 'assigned'. A draft can be assigned only once,
    enforced by the unique draft_id.

    status: only 'assigned' exists for now, validated by the application. There's deliberately
    no CHECK constraint, because SQLite can't change one without rebuilding the table, and
    later statuses (for submission) would need that.
    """

    __tablename__ = "homework_assignments"
    __table_args__ = (UniqueConstraint("draft_id", name="uq_homework_assignments_draft"),)

    id = Column(String(64), primary_key=True, default=generate_uuid)
    draft_id = Column(String(64), ForeignKey("homework_drafts.id"), nullable=False)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(64), nullable=False, index=True)
    assigned_by = Column(String(64), ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=utc_now, nullable=False)
    due_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="assigned", nullable=False, index=True)

    draft = relationship("HomeworkDraftRecord", lazy="selectin")


class StudentAccountLink(Base):
    """Explicit one-to-one link between a student login (User) and a Student record.

    Why this table exists: User and Student had no relationship. Student has no email, and
    matching IDs (User.id == Student.id) is a coincidence of the seed data, not a rule.
    Links are created by an admin or when a teacher provisions a new student account.

    Why a new table instead of a Student.user_id column: create_all() doesn't add columns to
    existing tables and no migration tool is set up, so a new column would need an unsafe
    manual change. A new table is created by create_all without touching existing data. It
    follows the existing ParentStudentLink pattern. Both columns are unique: one account per
    student and one student per account.

    Identity is platform-wide, so this may later move to shared code (team decision).
    """

    __tablename__ = "student_account_links"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_student_account_links_user"),
        UniqueConstraint("student_id", name="uq_student_account_links_student"),
    )

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(String(64), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class AssignedDraftDeletionError(Exception):
    """Raised when something tries to delete a draft that has been assigned."""


@event.listens_for(HomeworkDraftRecord, "before_delete")
def _refuse_deleting_assigned_drafts(mapper, connection, target):
    """Deleting a draft cascades to its question snapshots, which an assignment depends on.

    No endpoint deletes drafts, but scripts or admin code using the ORM could. SQLite foreign
    keys are off in this app, so the database wouldn't stop it. Checked against the
    assignments table, not just the status, so it holds even if the status were changed.
    """
    assigned = connection.execute(
        select(HomeworkAssignmentRecord.id).where(HomeworkAssignmentRecord.draft_id == target.id).limit(1)
    ).first()
    if assigned is not None or target.status == "assigned":
        raise AssignedDraftDeletionError(f"Draft {target.id} has been assigned and can't be deleted.")


# --- Student answer submissions -------------------------------------------------------------

SUBMISSION_STATUSES = ("in_progress", "submitted")


class HomeworkSubmissionRecord(Base):
    """A student's answers to one assignment. One per assignment (unique assignment_id).

    in_progress: answers can be saved and changed. submitted: locked for good.
    No marks, scores, grades or feedback are stored here; grading is a later milestone.

    Database rules, written to work on both SQLite and PostgreSQL:
    - status is one of SUBMISSION_STATUSES;
    - submitted_at is set exactly when status is "submitted";
    - is_late can only be true on a submitted submission.

    version: optimistic locking, as on drafts. Every change to the answers also updates this
    row (updated_at), so the version goes up and a concurrent change is detected.
    """

    __tablename__ = "homework_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_homework_submissions_assignment"),
        CheckConstraint(
            "status IN ('" + "', '".join(SUBMISSION_STATUSES) + "')",
            name="ck_homework_submissions_status",
        ),
        CheckConstraint(
            "(status = 'submitted') = (submitted_at IS NOT NULL)",
            name="ck_homework_submissions_submitted_at",
        ),
        CheckConstraint("NOT is_late OR status = 'submitted'", name="ck_homework_submissions_late"),
    )

    id = Column(String(64), primary_key=True, default=generate_uuid)
    assignment_id = Column(String(64), ForeignKey("homework_assignments.id"), nullable=False)
    # Copied from the assignment, never from the client.
    student_id = Column(String(64), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(String(64), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="in_progress", index=True)
    is_late = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False)

    __mapper_args__ = {"version_id_col": version}

    answers = relationship(
        "HomeworkSubmissionAnswerRecord",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class HomeworkSubmissionAnswerRecord(Base):
    """One answer to one frozen question. A row exists only while the question is answered;
    clearing an answer deletes the row.

    Exactly one of answer_text (short, descriptive, practical) and selected_option_index
    (mcq, 0-based into the frozen options) is set. That rule is a database CHECK, written as
    "(a IS NULL) <> (b IS NULL)" because it works on both SQLite and PostgreSQL.

    The item must belong to the same assignment's draft. The database can't express that
    across tables; submission_service checks it.
    """

    __tablename__ = "homework_submission_answers"
    __table_args__ = (
        UniqueConstraint("submission_id", "draft_item_id", name="uq_homework_submission_answers_item"),
        CheckConstraint(
            "(answer_text IS NULL) <> (selected_option_index IS NULL)",
            name="ck_homework_submission_answers_one_form",
        ),
        CheckConstraint(
            "selected_option_index IS NULL OR selected_option_index >= 0",
            name="ck_homework_submission_answers_index",
        ),
    )

    id = Column(String(64), primary_key=True, default=generate_uuid)
    submission_id = Column(
        String(64), ForeignKey("homework_submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_item_id = Column(String(64), ForeignKey("homework_draft_items.id"), nullable=False)
    answer_text = Column(Text, nullable=True)
    selected_option_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, nullable=False)

    submission = relationship("HomeworkSubmissionRecord", back_populates="answers")
