"""Legacy sample dataset (Sunrise Public School etc.) used only by the test suite.

The app seeds the real roster from backend/app/seed/seed_data.py. Tests keep this richer
fixture because they exercise assessments, curriculum and the question bank.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import get_password_hash
from backend.app.models.entities import (
    School,
    User,
    SchoolMembership,
    ClassSection,
    Subject,
    Student,
    ParentStudentLink,
    InstructionalDisruption,
    Assessment,
    AssessmentSubmission,
    StudentCompetencySnapshot,
    CurriculumDay,
    CrossCurricularProposal,
    HomeworkRemediation,
    Document,
    QuestionBankItem,
    ModelEvaluation,
    ModelDeployment,
    Notification,
    AuditEvent,
)
from backend.app.modules.differentiated_homework.models import StudentAccountLink

logger = logging.getLogger(__name__)


async def seed_database_if_empty(session: AsyncSession) -> None:
    # Check if schools already exist
    result = await session.execute(select(School))
    existing_school = result.scalars().first()
    if existing_school:
        await ensure_source_documents_and_question_bank(session)
        await link_demo_student(session)
        logger.info("Database already seeded. Verified source documents and question bank.")
        return

    logger.info("Empty database detected. Seeding comprehensive LumenEIOS reference dataset...")

    # 1. Schools
    schools = [
        School(
            id="school-1",
            name="Sunrise Public School",
            location="Indiranagar, Bengaluru",
            state="Karnataka",
            infrastructure_tier="high-tech",
            academic_year="2026-2027",
            principal_id="user-principal-1",
            principal_name="Dr. Sunita Deshmukh",
            student_count=850,
            teacher_count=42,
            class_count=18,
            pacing_risk="medium",
            description="Premier smart-school with interactive digital boards, 1:1 student tablets, and high-speed fiber connectivity.",
            official_working_days=220,
        ),
        School(
            id="school-2",
            name="Green Valley Academy",
            location="Kothrud, Pune",
            state="Maharashtra",
            infrastructure_tier="standard",
            academic_year="2026-2027",
            principal_id="user-principal-2",
            principal_name="Prof. Arvind Kulkarni",
            student_count=640,
            teacher_count=32,
            class_count=14,
            pacing_risk="low",
            description="CBSE affiliated school with shared computer laboratories, projector-equipped classrooms, and blended learning models.",
            official_working_days=220,
        ),
        School(
            id="school-3",
            name="Pragati Government Senior Secondary School",
            location="Sanganer, Jaipur",
            state="Rajasthan",
            infrastructure_tier="low-tech",
            academic_year="2026-2027",
            principal_id="user-principal-3",
            principal_name="Shri Ramswaroop Sharma",
            student_count=520,
            teacher_count=24,
            class_count=12,
            pacing_risk="high",
            description="State government school utilizing offline printed student workbooks, periodic mobile scans, and community solar lanterns.",
            official_working_days=220,
        ),
        School(
            id="school-4",
            name="Vidya Niketan School",
            location="Gomti Nagar, Lucknow",
            state="Uttar Pradesh",
            infrastructure_tier="standard",
            academic_year="2026-2027",
            principal_id="user-principal-4",
            principal_name="Mrs. Rekha Srivastava",
            student_count=710,
            teacher_count=35,
            class_count=15,
            pacing_risk="low",
            description="Progressive institution with hybrid smart classrooms, science tinkering labs, and structured peer-led study groups.",
            official_working_days=220,
        ),
        School(
            id="school-5",
            name="Udaan Learning Government School",
            location="Namkum, Ranchi",
            state="Jharkhand",
            infrastructure_tier="low-tech",
            academic_year="2026-2027",
            principal_id="user-principal-5",
            principal_name="Shri Birsa Munda",
            student_count=430,
            teacher_count=18,
            class_count=10,
            pacing_risk="high",
            description="Tribal welfare initiative school focusing on foundational literacy and numeracy with physical worksheets and vernacular audio aides.",
            official_working_days=220,
        ),
    ]
    for s in schools:
        session.add(s)

    # 2. Users & Memberships
    default_hash = get_password_hash("demo123")
    users = [
        User(
            id="user-admin",
            email="admin@lumeneios.demo",
            name="Dr. Rajesh Sharma",
            hashed_password=default_hash,
            role="admin",
            school_id="school-1",
            designation="Director of Academic Innovation & State Lead",
            avatar="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        ),
        User(
            id="user-principal-1",
            email="principal@lumeneios.demo",
            name="Dr. Sunita Deshmukh",
            hashed_password=default_hash,
            role="principal",
            school_id="school-1",
            designation="Principal, Sunrise Public School",
            avatar="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
        ),
        User(
            id="user-teacher-1",
            email="teacher@lumeneios.demo",
            name="Vikram Sengupta",
            hashed_password=default_hash,
            role="teacher",
            school_id="school-1",
            designation="TGT Mathematics & Science (Grade 8 & 9 Lead)",
            avatar="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        ),
        User(
            id="user-student-1",
            email="student@lumeneios.demo",
            name="Aarav Patel",
            hashed_password=default_hash,
            role="student",
            school_id="school-1",
            designation="Student, Grade 8 Section A",
            avatar="https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80",
        ),
        User(
            id="user-parent-1",
            email="parent@lumeneios.demo",
            name="Meera Patel",
            hashed_password=default_hash,
            role="parent",
            school_id="school-1",
            designation="Parent / Guardian",
            avatar="https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80",
        ),
        User(
            id="user-teacher-2",
            email="anjali.roy@lumeneios.demo",
            name="Anjali Roy",
            hashed_password=default_hash,
            role="teacher",
            school_id="school-1",
            designation="TGT English & Social Science",
            avatar="https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80",
        ),
        User(
            id="user-teacher-3",
            email="kavita.meena@lumeneios.demo",
            name="Kavita Meena",
            hashed_password=default_hash,
            role="teacher",
            school_id="school-3",
            designation="Senior Teacher (Mathematics)",
            avatar="https://images.unsplash.com/photo-1548142813-c348350df52b?w=150&auto=format&fit=crop&q=80",
        ),
    ]
    for u in users:
        session.add(u)

    # Memberships
    memberships = [
        SchoolMembership(id="mem-admin-1", user_id="user-admin", school_id="school-1", role="admin"),
        SchoolMembership(id="mem-admin-2", user_id="user-admin", school_id="school-2", role="admin"),
        SchoolMembership(id="mem-admin-3", user_id="user-admin", school_id="school-3", role="admin"),
        SchoolMembership(id="mem-admin-4", user_id="user-admin", school_id="school-4", role="admin"),
        SchoolMembership(id="mem-admin-5", user_id="user-admin", school_id="school-5", role="admin"),
        SchoolMembership(id="mem-prin-1", user_id="user-principal-1", school_id="school-1", role="principal"),
        SchoolMembership(id="mem-teach-1", user_id="user-teacher-1", school_id="school-1", role="teacher"),
        SchoolMembership(id="mem-stud-1", user_id="user-student-1", school_id="school-1", role="student"),
        SchoolMembership(id="mem-par-1", user_id="user-parent-1", school_id="school-1", role="parent"),
        SchoolMembership(id="mem-teach-2", user_id="user-teacher-2", school_id="school-1", role="teacher"),
        SchoolMembership(id="mem-teach-3", user_id="user-teacher-3", school_id="school-3", role="teacher"),
    ]
    for m in memberships:
        session.add(m)

    # 3. Classes
    classes = [
        ClassSection(
            id="class-8a",
            school_id="school-1",
            grade=8,
            section="A",
            name="Class 8-A",
            class_teacher_id="user-teacher-1",
            class_teacher_name="Vikram Sengupta",
            student_count=32,
            subject_ids_json=["sub-math", "sub-sci", "sub-eng", "sub-sst"],
        ),
        ClassSection(
            id="class-8b",
            school_id="school-1",
            grade=8,
            section="B",
            name="Class 8-B",
            class_teacher_id="user-teacher-2",
            class_teacher_name="Anjali Roy",
            student_count=30,
            subject_ids_json=["sub-math", "sub-sci", "sub-eng", "sub-sst"],
        ),
        ClassSection(
            id="class-9b",
            school_id="school-1",
            grade=9,
            section="B",
            name="Class 9-B",
            class_teacher_id="user-teacher-1",
            class_teacher_name="Vikram Sengupta",
            student_count=28,
            subject_ids_json=["sub-math", "sub-sci"],
        ),
        ClassSection(
            id="class-7a",
            school_id="school-1",
            grade=7,
            section="A",
            name="Class 7-A",
            class_teacher_id="user-teacher-2",
            class_teacher_name="Anjali Roy",
            student_count=31,
            subject_ids_json=["sub-math", "sub-sci", "sub-eng"],
        ),
        ClassSection(
            id="class-pragati-8",
            school_id="school-3",
            grade=8,
            section="A",
            name="Class 8-Gov",
            class_teacher_id="user-teacher-3",
            class_teacher_name="Kavita Meena",
            student_count=29,
            subject_ids_json=["sub-math", "sub-sci"],
        ),
        ClassSection(
            id="class-greenvalley-8",
            school_id="school-2",
            grade=8,
            section="A",
            name="Class 8-GVA",
            class_teacher_id="user-teacher-1",
            class_teacher_name="Sanjay Deshmukh",
            student_count=34,
            subject_ids_json=["sub-math", "sub-sci"],
        ),
    ]
    for c in classes:
        session.add(c)

    # 4. Subjects
    subjects = [
        Subject(id="sub-math", name="Mathematics", code="MATH-8", grade=8, icon_name="Calculator"),
        Subject(id="sub-sci", name="Science & Discovery", code="SCI-8", grade=8, icon_name="FlaskConical"),
        Subject(id="sub-eng", name="English Communication", code="ENG-8", grade=8, icon_name="BookOpen"),
        Subject(id="sub-sst", name="Social Studies & Civics", code="SST-8", grade=8, icon_name="Globe"),
    ]
    for sub in subjects:
        session.add(sub)

    # 5. Students
    student_records = [
        Student(
            id="user-student-1",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Aarav Patel",
            roll_no=14,
            gender="M",
            attendance_pct=94.0,
            lu_score=78,
            cu_score=82,
            au_score=70,
            ct_score=65,
            overall_score=74,
            baseline_lu=68,
            baseline_cu=72,
            baseline_au=60,
            baseline_ct=54,
            baseline_overall=64,
            learning_modality="Visual",
            parent_id="user-parent-1",
            homework_completion_rate=92.0,
            needs_support=False,
        ),
        Student(
            id="student-ananya",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Ananya Patel",
            roll_no=15,
            gender="F",
            attendance_pct=96.0,
            lu_score=88,
            cu_score=84,
            au_score=79,
            ct_score=82,
            overall_score=83,
            baseline_lu=80,
            baseline_cu=76,
            baseline_au=70,
            baseline_ct=72,
            baseline_overall=75,
            learning_modality="Reading/Writing",
            parent_id="user-parent-1",
            homework_completion_rate=98.0,
            needs_support=False,
        ),
        Student(
            id="student-3",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Rohan Gupta",
            roll_no=27,
            gender="M",
            attendance_pct=86.0,
            lu_score=52,
            cu_score=76,
            au_score=66,
            ct_score=55,
            overall_score=62,
            baseline_lu=46,
            baseline_cu=70,
            baseline_au=58,
            baseline_ct=50,
            baseline_overall=56,
            learning_modality="Kinesthetic",
            parent_id="parent-3",
            homework_completion_rate=70.0,
            needs_support=True,
            support_area="Language Understanding in multi-step Word Problems",
        ),
        Student(
            id="student-4",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Priya Nair",
            roll_no=22,
            gender="F",
            attendance_pct=91.0,
            lu_score=85,
            cu_score=62,
            au_score=54,
            ct_score=60,
            overall_score=65,
            baseline_lu=80,
            baseline_cu=55,
            baseline_au=48,
            baseline_ct=52,
            baseline_overall=59,
            learning_modality="Auditory",
            parent_id="parent-4",
            homework_completion_rate=85.0,
            needs_support=True,
            support_area="Application Understanding in geometric proofs & units",
        ),
        Student(
            id="student-5",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Devansh Kulkarni",
            roll_no=8,
            gender="M",
            attendance_pct=98.0,
            lu_score=92,
            cu_score=94,
            au_score=91,
            ct_score=88,
            overall_score=91,
            baseline_lu=85,
            baseline_cu=88,
            baseline_au=82,
            baseline_ct=80,
            baseline_overall=84,
            learning_modality="Visual",
            parent_id="parent-5",
            homework_completion_rate=100.0,
            needs_support=False,
        ),
        Student(
            id="student-6",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Kavya Raman",
            roll_no=18,
            gender="F",
            attendance_pct=89.0,
            lu_score=74,
            cu_score=70,
            au_score=68,
            ct_score=62,
            overall_score=69,
            baseline_lu=68,
            baseline_cu=62,
            baseline_au=60,
            baseline_ct=55,
            baseline_overall=61,
            learning_modality="Reading/Writing",
            parent_id="parent-6",
            homework_completion_rate=88.0,
            needs_support=False,
        ),
        Student(
            id="student-7",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Mohammad Farhan",
            roll_no=20,
            gender="M",
            attendance_pct=82.0,
            lu_score=58,
            cu_score=65,
            au_score=52,
            ct_score=49,
            overall_score=56,
            baseline_lu=52,
            baseline_cu=58,
            baseline_au=45,
            baseline_ct=42,
            baseline_overall=49,
            learning_modality="Kinesthetic",
            parent_id="parent-7",
            homework_completion_rate=65.0,
            needs_support=True,
            support_area="Application & Critical Thinking in Data Handling",
        ),
        Student(
            id="student-8",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Tanvi Iyer",
            roll_no=31,
            gender="F",
            attendance_pct=95.0,
            lu_score=86,
            cu_score=85,
            au_score=80,
            ct_score=83,
            overall_score=84,
            baseline_lu=78,
            baseline_cu=77,
            baseline_au=72,
            baseline_ct=75,
            baseline_overall=76,
            learning_modality="Visual",
            parent_id="parent-8",
            homework_completion_rate=96.0,
            needs_support=False,
        ),
        Student(
            id="student-9",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Siddharth Mehra",
            roll_no=29,
            gender="M",
            attendance_pct=90.0,
            lu_score=71,
            cu_score=75,
            au_score=69,
            ct_score=67,
            overall_score=71,
            baseline_lu=65,
            baseline_cu=68,
            baseline_au=62,
            baseline_ct=60,
            baseline_overall=64,
            learning_modality="Auditory",
            parent_id="parent-9",
            homework_completion_rate=85.0,
            needs_support=False,
        ),
        Student(
            id="student-10",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Ishita Banerjee",
            roll_no=16,
            gender="F",
            attendance_pct=97.0,
            lu_score=94,
            cu_score=90,
            au_score=86,
            ct_score=85,
            overall_score=89,
            baseline_lu=88,
            baseline_cu=84,
            baseline_au=79,
            baseline_ct=78,
            baseline_overall=82,
            learning_modality="Reading/Writing",
            parent_id="parent-10",
            homework_completion_rate=100.0,
            needs_support=False,
        ),
        Student(
            id="student-11",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Aditya Chauhan",
            roll_no=3,
            gender="M",
            attendance_pct=88.0,
            lu_score=65,
            cu_score=68,
            au_score=60,
            ct_score=58,
            overall_score=63,
            baseline_lu=60,
            baseline_cu=62,
            baseline_au=55,
            baseline_ct=51,
            baseline_overall=57,
            learning_modality="Kinesthetic",
            parent_id="parent-11",
            homework_completion_rate=75.0,
            needs_support=True,
            support_area="Concept Understanding in Rational Numbers",
        ),
        Student(
            id="student-12",
            school_id="school-1",
            class_id="class-8a",
            class_name="Class 8-A",
            name="Diya Nambiar",
            roll_no=9,
            gender="F",
            attendance_pct=93.0,
            lu_score=82,
            cu_score=79,
            au_score=76,
            ct_score=74,
            overall_score=78,
            baseline_lu=75,
            baseline_cu=71,
            baseline_au=68,
            baseline_ct=66,
            baseline_overall=70,
            learning_modality="Visual",
            parent_id="parent-12",
            homework_completion_rate=91.0,
            needs_support=False,
        ),
        Student(
            id="student-16",
            school_id="school-1",
            class_id="class-9b",
            class_name="Class 9-B",
            name="Arjun Das",
            roll_no=4,
            gender="M",
            attendance_pct=91.0,
            lu_score=76,
            cu_score=80,
            au_score=74,
            ct_score=71,
            overall_score=75,
            baseline_lu=70,
            baseline_cu=72,
            baseline_au=66,
            baseline_ct=63,
            baseline_overall=68,
            learning_modality="Visual",
            parent_id="parent-16",
            homework_completion_rate=88.0,
            needs_support=False,
        ),
        Student(
            id="student-17",
            school_id="school-1",
            class_id="class-9b",
            class_name="Class 9-B",
            name="Bhavna Joshi",
            roll_no=7,
            gender="F",
            attendance_pct=94.0,
            lu_score=83,
            cu_score=85,
            au_score=78,
            ct_score=76,
            overall_score=81,
            baseline_lu=77,
            baseline_cu=78,
            baseline_au=70,
            baseline_ct=68,
            baseline_overall=73,
            learning_modality="Reading/Writing",
            parent_id="parent-17",
            homework_completion_rate=92.0,
            needs_support=False,
        ),
        Student(
            id="student-18",
            school_id="school-3",
            class_id="class-pragati-8",
            class_name="Class 8-Gov",
            name="Mukesh Gurjar",
            roll_no=12,
            gender="M",
            attendance_pct=79.0,
            lu_score=48,
            cu_score=58,
            au_score=49,
            ct_score=42,
            overall_score=49,
            baseline_lu=42,
            baseline_cu=51,
            baseline_au=41,
            baseline_ct=36,
            baseline_overall=43,
            learning_modality="Kinesthetic",
            parent_id="parent-18",
            homework_completion_rate=60.0,
            needs_support=True,
            support_area="Foundational Language & Vernacular-to-English Maths Terms",
        ),
        Student(
            id="student-19",
            school_id="school-3",
            class_id="class-pragati-8",
            class_name="Class 8-Gov",
            name="Geeta Kumari",
            roll_no=10,
            gender="F",
            attendance_pct=83.0,
            lu_score=55,
            cu_score=64,
            au_score=56,
            ct_score=50,
            overall_score=56,
            baseline_lu=49,
            baseline_cu=57,
            baseline_au=48,
            baseline_ct=43,
            baseline_overall=49,
            learning_modality="Visual",
            parent_id="parent-19",
            homework_completion_rate=72.0,
            needs_support=True,
            support_area="Application in real life measurements",
        ),
        Student(
            id="student-20",
            school_id="school-2",
            class_id="class-greenvalley-8",
            class_name="Class 8-GVA",
            name="Kabir Thapar",
            roll_no=17,
            gender="M",
            attendance_pct=93.0,
            lu_score=84,
            cu_score=81,
            au_score=77,
            ct_score=79,
            overall_score=80,
            baseline_lu=78,
            baseline_cu=74,
            baseline_au=69,
            baseline_ct=71,
            baseline_overall=73,
            learning_modality="Auditory",
            parent_id="parent-20",
            homework_completion_rate=94.0,
            needs_support=False,
        ),
    ]
    for s in student_records:
        session.add(s)

    # 6. Parent-Student Link
    session.add(ParentStudentLink(id="psl-1", parent_user_id="user-parent-1", student_id="user-student-1"))
    session.add(ParentStudentLink(id="psl-2", parent_user_id="user-parent-1", student_id="student-ananya"))

    # 7. Instructional Disruptions (16 Lost Days)
    disruptions = [
        InstructionalDisruption(
            id="ltd-1",
            school_id="school-1",
            date="2026-08-14",
            reason="Election Duties",
            days_lost=5.0,
            recorded_by="Dr. Sunita Deshmukh",
            notes="State legislative assembly constituency polling booth setup and mandatory teacher presiding officer training.",
        ),
        InstructionalDisruption(
            id="ltd-2",
            school_id="school-1",
            date="2026-09-04",
            reason="Census Duties",
            days_lost=3.0,
            recorded_by="Vikram Sengupta",
            notes="District statistical household census verification drive assigned to secondary faculty.",
        ),
        InstructionalDisruption(
            id="ltd-3",
            school_id="school-1",
            date="2026-09-16",
            reason="Extreme Weather",
            days_lost=4.0,
            recorded_by="Dr. Sunita Deshmukh",
            notes="District collector safety directive due to urban flash flooding and heavy monsoon red alert.",
        ),
        InstructionalDisruption(
            id="ltd-4",
            school_id="school-1",
            date="2026-10-02",
            reason="Teacher Training",
            days_lost=2.0,
            recorded_by="Vikram Sengupta",
            notes="NEP 2020 Competency-Based Assessment pedagogy workshop mandated by the state education board.",
        ),
        InstructionalDisruption(
            id="ltd-5",
            school_id="school-1",
            date="2026-10-09",
            reason="Health Drive",
            days_lost=2.0,
            recorded_by="Dr. Sunita Deshmukh",
            notes="National deworming and adolescent nutritional screening conducted on campus by state health workers.",
        ),
    ]
    for d in disruptions:
        session.add(d)

    # 8. Questions and Assessments
    sample_questions = [
        {
            "id": "q-1",
            "text": "A water tank is in the shape of a cuboid with length 4m, breadth 3m, and depth 2m. If water is poured at the rate of 60 liters per minute, how many hours will it take to fill the tank completely? (1 m³ = 1000 liters)",
            "type": "practical",
            "marks": 4,
            "competency": "AU",
            "bloomLevel": "Apply",
            "correctAnswer": "Volume = 4 * 3 * 2 = 24 m³ = 24,000 L. Time = 24,000 / 60 = 400 minutes = 6 hours and 40 minutes.",
        },
        {
            "id": "q-2",
            "text": "Identify the multiplicative inverse of -13/19 and explain why the product of a rational number and its inverse is always 1.",
            "type": "short",
            "marks": 2,
            "competency": "CU",
            "bloomLevel": "Understand",
            "correctAnswer": "-19/13. By definition, a/b * (b/a) = (a*b)/(b*a) = 1.",
        },
        {
            "id": "q-3",
            "text": "Read the following statement carefully: 'If all squares are rectangles, then all rectangular properties apply to squares, but all rectangles cannot be squares.' State whether this is valid and justify the linguistic condition using geometric definitions.",
            "type": "descriptive",
            "marks": 3,
            "competency": "LU",
            "bloomLevel": "Analyze",
            "correctAnswer": "Statement is mathematically valid. Square has 4 equal sides and 90° angles; rectangle requires only opposite sides equal and 90° angles.",
        },
        {
            "id": "q-4",
            "text": "A farmer claims that doubling the perimeter of a rectangular crop field will always double its grazing area. Evaluate whether this claim is true or false using at least two mathematical examples.",
            "type": "descriptive",
            "marks": 5,
            "competency": "CT",
            "bloomLevel": "Evaluate",
            "correctAnswer": "False. Uniform 2x scaling doubles perimeter but quadruples area (4A). Non-uniform changes result in variable areas.",
        },
        {
            "id": "q-5",
            "text": "Which of the following numbers is a perfect square? A) 1057  B) 23453  C) 7928  D) 1089",
            "type": "mcq",
            "options": ["1057", "23453", "7928", "1089"],
            "marks": 1,
            "competency": "CU",
            "bloomLevel": "Remember",
            "correctAnswer": "1089 (33 * 33 = 1089. Perfect squares cannot end in 2, 3, 7, 8).",
        },
    ]

    assessments = [
        Assessment(
            id="asm-1",
            school_id="school-1",
            class_id="class-8a",
            subject_id="sub-math",
            title="Cycle 1 Baseline: Number Systems & Rational Algebraic Operations",
            cycle_number=1,
            date="2026-07-28",
            duration_minutes=45,
            total_marks=25,
            questions_json=sample_questions[:5],
            status="graded",
            competency_focus_json=["LU", "CU", "AU", "CT"],
        ),
        Assessment(
            id="asm-2",
            school_id="school-1",
            class_id="class-8a",
            subject_id="sub-math",
            title="Cycle 2 Mid-Term: Linear Equations, Quadrilaterals & Data Handling",
            cycle_number=2,
            date="2026-09-18",
            duration_minutes=50,
            total_marks=30,
            questions_json=sample_questions[:5],
            status="graded",
            competency_focus_json=["CU", "AU", "CT"],
        ),
        Assessment(
            id="asm-3",
            school_id="school-1",
            class_id="class-8a",
            subject_id="sub-math",
            title="Cycle 3 Pacing Check: Mensuration & Applied Geometric Reasoning",
            cycle_number=3,
            date="2026-10-24",
            duration_minutes=45,
            total_marks=25,
            questions_json=sample_questions[:4],
            status="scheduled",
            competency_focus_json=["AU", "CT", "LU"],
        ),
        Assessment(
            id="asm-4",
            school_id="school-1",
            class_id="class-8a",
            subject_id="sub-sci",
            title="Cycle 2 Diagnostic: Pressure, Atmospheric Density & Friction Dynamics",
            cycle_number=2,
            date="2026-09-22",
            duration_minutes=40,
            total_marks=20,
            questions_json=sample_questions[:4],
            status="graded",
            competency_focus_json=["LU", "AU", "CT"],
        ),
    ]
    for a in assessments:
        session.add(a)

    # 9. Submissions
    submissions = [
        AssessmentSubmission(
            id="res-aarav-1",
            assessment_id="asm-2",
            student_id="user-student-1",
            student_name="Aarav Patel",
            marks_obtained=24,
            total_marks=30,
            percentage=80,
            lu_score=78,
            cu_score=82,
            au_score=72,
            ct_score=66,
            overall_score=75,
            feedback="Commendable algebraic accuracy. In Question 4 on field geometry, focus on explaining unit quadratics step-by-step.",
            submission_date="2026-09-18",
            is_scanned=True,
        ),
        AssessmentSubmission(
            id="res-ananya-1",
            assessment_id="asm-2",
            student_id="student-ananya",
            student_name="Ananya Patel",
            marks_obtained=27,
            total_marks=30,
            percentage=90,
            lu_score=89,
            cu_score=85,
            au_score=80,
            ct_score=84,
            overall_score=85,
            feedback="Exceptional structural analysis and clear linguistic justification for geometric proofs.",
            submission_date="2026-09-18",
            is_scanned=True,
        ),
        AssessmentSubmission(
            id="res-rohan-1",
            assessment_id="asm-2",
            student_id="student-3",
            student_name="Rohan Gupta",
            marks_obtained=17,
            total_marks=30,
            percentage=57,
            lu_score=48,
            cu_score=74,
            au_score=62,
            ct_score=50,
            overall_score=58,
            feedback="High conceptual grasp, but misread the wording in compound rate problems. Assigned reading-annotated scaffolding.",
            submission_date="2026-09-18",
            is_scanned=True,
        ),
        AssessmentSubmission(
            id="res-priya-1",
            assessment_id="asm-2",
            student_id="student-4",
            student_name="Priya Nair",
            marks_obtained=19,
            total_marks=30,
            percentage=63,
            lu_score=84,
            cu_score=60,
            au_score=52,
            ct_score=58,
            overall_score=64,
            feedback="Fluent written answers, but slipped on unit conversion and practical spatial calculations.",
            submission_date="2026-09-18",
            is_scanned=True,
        ),
        AssessmentSubmission(
            id="res-devansh-1",
            assessment_id="asm-2",
            student_id="student-5",
            student_name="Devansh Kulkarni",
            marks_obtained=29,
            total_marks=30,
            percentage=97,
            lu_score=95,
            cu_score=96,
            au_score=92,
            ct_score=90,
            overall_score=93,
            feedback="Mastery across all four dimensions. Ready for advanced olympiad problem sets.",
            submission_date="2026-09-18",
            is_scanned=True,
        ),
    ]
    for sub in submissions:
        session.add(sub)

    # 10. Student Competency Snapshots (Historical Cycles)
    snapshots = [
        StudentCompetencySnapshot(
            id="snap-aarav-c1",
            student_id="user-student-1",
            cycle_number=1,
            recorded_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
            lu_score=68,
            cu_score=72,
            au_score=60,
            ct_score=54,
            overall_score=64,
            notes="Cycle 1 Diagnostic Baseline",
        ),
        StudentCompetencySnapshot(
            id="snap-aarav-c2",
            student_id="user-student-1",
            cycle_number=2,
            recorded_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            lu_score=78,
            cu_score=82,
            au_score=72,
            ct_score=66,
            overall_score=75,
            notes="Cycle 2 Mid-Term Assessment",
        ),
        StudentCompetencySnapshot(
            id="snap-ananya-c1",
            student_id="student-ananya",
            cycle_number=1,
            recorded_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
            lu_score=80,
            cu_score=76,
            au_score=70,
            ct_score=72,
            overall_score=75,
            notes="Cycle 1 Diagnostic Baseline",
        ),
        StudentCompetencySnapshot(
            id="snap-ananya-c2",
            student_id="student-ananya",
            cycle_number=2,
            recorded_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
            lu_score=88,
            cu_score=84,
            au_score=79,
            ct_score=82,
            overall_score=83,
            notes="Cycle 2 Mid-Term Assessment",
        ),
    ]
    for snap in snapshots:
        session.add(snap)

    # 11. 180-Day Micro-Curriculum
    chapters = [
        {"name": "Rational Numbers & Operations", "core": 14, "supp": 6},
        {"name": "Linear Equations in One Variable", "core": 16, "supp": 8},
        {"name": "Understanding Quadrilaterals & Polygons", "core": 15, "supp": 7},
        {"name": "Data Handling & Probability", "core": 14, "supp": 6},
        {"name": "Squares, Square Roots & Cubes", "core": 12, "supp": 6},
        {"name": "Comparing Quantities & Percentage Models", "core": 15, "supp": 7},
        {"name": "Algebraic Expressions & Identities", "core": 18, "supp": 8},
        {"name": "Mensuration: Surface Areas & Volumes", "core": 16, "supp": 8},
        {"name": "Exponents, Powers & Scientific Notation", "core": 10, "supp": 4},
        {"name": "Direct & Inverse Proportions", "core": 12, "supp": 5},
    ]
    modalities = ["Visual", "Auditory", "Reading/Writing", "Kinesthetic"]
    blooms = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]

    current_day = 1
    current_instructional_day = 104

    for ch_idx, ch in enumerate(chapters):
        total_in_ch = ch["core"] + ch["supp"]
        for i in range(1, total_in_ch + 1):
            if current_day > 180:
                break
            is_core = i <= ch["core"]
            if current_day < current_instructional_day:
                status = "completed"
            elif current_day == current_instructional_day:
                status = "in-progress"
            else:
                status = "pending"

            mod = modalities[(current_day + ch_idx) % len(modalities)]
            bloom = blooms[(i + ch_idx) % len(blooms)]

            c_day = CurriculumDay(
                id=f"cur-day-{current_day}",
                day_number=current_day,
                class_id="class-8a",
                subject_id="sub-math",
                topic=f"{ch['name']} — Part {i}: {'Core Concept & Application' if is_core else 'Extension & Supplementary Inquiries'}",
                objective=(
                    f"Master fundamental mastery in {ch['name']} through direct structured modeling."
                    if is_core
                    else f"Synthesize exploratory case studies in {ch['name']}."
                ),
                teaching_process=f"Interactive lecture with {mod.lower()} activities, peer review, and exit check.",
                measurable_outcome="Student can solve 3 target benchmark problems with >80% accuracy within 12 minutes.",
                estimated_duration_mins=45,
                vark_modality=mod,
                bloom_level=bloom,
                classification="core" if is_core else "supplementary",
                status=status,
                prerequisites_json=[f"Day {current_day - 1}"] if i > 1 else [],
            )
            session.add(c_day)
            current_day += 1

    # 12. Cross-Curricular Proposals
    ccps = [
        CrossCurricularProposal(
            id="ccp-1",
            title="Climate Rainfall Data Modeling & Civic Water Footprint",
            school_id="school-1",
            class_id="class-8a",
            subject_ids_json=["sub-math", "sub-sci", "sub-eng"],
            subject_names_json=["Mathematics", "Science", "English"],
            target_day_numbers_json=[112, 113, 114],
            learning_objectives_json=[
                "Draw and interpret frequency polygons & double bar charts (Maths)",
                "Analyze hydrological precipitation cycles and groundwater depletion (Science)",
                "Compose an evidence-based persuasive community letter on rainwater harvesting (English)",
            ],
            activity="Students collect 10-year local monsoon precipitation data, calculate mean variances, and draft a civic water audit memorandum.",
            vark_modality="Visual",
            bloom_level="Evaluate",
            estimated_duration_hours=4.0,
            time_saved_hours=3.5,
            status="pending",
        ),
        CrossCurricularProposal(
            id="ccp-2",
            title="Heritage Monument Geometry & Architectural Mensuration",
            school_id="school-1",
            class_id="class-8a",
            subject_ids_json=["sub-math", "sub-sst"],
            subject_names_json=["Mathematics", "Social Studies"],
            target_day_numbers_json=[126, 127],
            learning_objectives_json=[
                "Calculate surface area and volume of composite cylindrical and hemispherical domes (Maths)",
                "Evaluate Mughal & Dravidian architectural acoustic engineering principles (Social Studies)",
            ],
            activity="Scale blueprint modeling of historical domed structures using recycled card and calculating structural load distributions.",
            vark_modality="Kinesthetic",
            bloom_level="Create",
            estimated_duration_hours=3.0,
            time_saved_hours=2.0,
            status="accepted",
        ),
        CrossCurricularProposal(
            id="ccp-3",
            title="Scientific Exponents in Astronomical & Microscopic Dimensions",
            school_id="school-1",
            class_id="class-8a",
            subject_ids_json=["sub-math", "sub-sci"],
            subject_names_json=["Mathematics", "Science"],
            target_day_numbers_json=[142, 143],
            learning_objectives_json=[
                "Express numbers in standard scientific notation with negative exponents (Maths)",
                "Compare cellular organelle dimensions with planetary orbits (Science)",
            ],
            activity="Interactive zoom-scale logarithmic scroll comparing viral diameter to the Milky Way galaxy.",
            vark_modality="Visual",
            bloom_level="Analyze",
            estimated_duration_hours=2.5,
            time_saved_hours=2.0,
            status="pending",
        ),
    ]
    for ccp in ccps:
        session.add(ccp)

    # 13. Homework Remediations
    hwrs = [
        HomeworkRemediation(
            id="hwr-1",
            student_id="student-3",
            student_name="Rohan Gupta",
            class_id="class-8a",
            subject_id="sub-math",
            title="Word Problem Linguistic Scaffolding: Visual Highlighting of Keywords",
            competency_target="LU",
            reason="Scored 48/100 in Language Understanding on Cycle 2 assessment. Struggles with phrase parsing ('per unit time', 'diminished by').",
            description="Worksheet with 6 real-world rate problems featuring color-coded key phrases, bilingual glossaries, and step-by-step clause breakdown.",
            due_date="2026-10-16",
            status="assigned",
        ),
        HomeworkRemediation(
            id="hwr-2",
            student_id="student-4",
            student_name="Priya Nair",
            class_id="class-8a",
            subject_id="sub-math",
            title="Concrete-to-Abstract Mensuration: Kitchen Container Volume Lab",
            competency_target="AU",
            reason="Scored 52/100 in Application Understanding. Theoretical grasp is high, but commits dimensional conversion errors (m³ vs Liters).",
            description="Home activity: Measure dimensions of 3 cylindrical food containers, compute theoretical volume in cm³, and verify with a graduated measuring beaker.",
            due_date="2026-10-18",
            status="assigned",
        ),
        HomeworkRemediation(
            id="hwr-3",
            student_id="user-student-1",
            student_name="Aarav Patel",
            class_id="class-8a",
            subject_id="sub-math",
            title="Critical Evaluation of Misleading Advertising Data Graphs",
            competency_target="CT",
            reason="Scored 66/100 in Critical Thinking. Needs targeted practice in identifying truncated axes and perceptual distortion.",
            description="Analyze 3 commercial news adverts showing truncated bar chart axes. Identify perceptual distortion and re-plot with honest zero baselines.",
            due_date="2026-10-17",
            status="assigned",
        ),
    ]
    for hwr in hwrs:
        session.add(hwr)

    # 13.5 Seed Document for OCR processing
    session.add(
        Document(
            id="doc-demo-1",
            school_id="school-1",
            uploader_id="user-teacher-1",
            file_name="grade8_math_midterm_aarav_patel.jpg",
            file_size=245000,
            mime_type="image/jpeg",
            storage_path="./storage_uploads/grade8_math_midterm_aarav_patel.jpg",
            page_count=1,
            status="ready",
        )
    )

    # 14. OCR Model Evaluation and Active Deployment
    session.add(
        ModelEvaluation(
            id="eval-trocr-v1.0",
            model_id="trocr-handwritten-indic",
            model_version="v1.0",
            cer=0.042,
            wer=0.078,
            field_accuracy=0.965,
            latency_ms=180,
            status="passed",
            notes="Passed baseline gating: CER < 0.05 and Field Accuracy > 0.95 across Indian school handwriting test set.",
        )
    )
    session.add(
        ModelDeployment(
            id="deploy-trocr-v1.0",
            model_id="trocr-handwritten-indic",
            model_version="v1.0",
            provider="simulated",
            is_active=True,
            deployed_by="Dr. Rajesh Sharma",
        )
    )

    # 15. Notifications
    notifications = [
        Notification(
            id="notif-1",
            user_id="user-teacher-1",
            title="Pacing Risk Alert: Class 8-A Mathematics",
            message="16 lost instructional days have reduced buffer to -4 days. Syllabus compression is recommended.",
            type="alert",
            is_read=False,
            link="/teacher/dashboard",
        ),
        Notification(
            id="notif-2",
            user_id="user-teacher-1",
            title="Cross-Curricular Proposal Ready for Review",
            message="Syllabus Engine detected 3.5 hrs recoverable time between Maths (Data Handling) and Science.",
            type="info",
            is_read=False,
            link="/teacher/dashboard",
        ),
        Notification(
            id="notif-3",
            user_id="user-principal-1",
            title="Class 8-A Pacing Warning",
            message="Vikram Sengupta has recorded 16 cumulative lost teaching days. Review proposed compression.",
            type="warning",
            is_read=False,
            link="/principal/dashboard",
        ),
        Notification(
            id="notif-4",
            user_id="user-student-1",
            title="New Adaptive Homework Assigned",
            message="Mr. Sengupta assigned 'Critical Evaluation of Misleading Data Graphs' due on Oct 17.",
            type="info",
            is_read=False,
            link="/student/dashboard",
        ),
        Notification(
            id="notif-5",
            user_id="user-parent-1",
            title="Aarav Completed Cycle 2 Assessment",
            message="Aarav scored 80% (LU: 78, CU: 82, AU: 72, CT: 66). Click to review teacher feedback.",
            type="success",
            is_read=False,
            link="/parent/dashboard",
        ),
    ]
    for n in notifications:
        session.add(n)

    # 16. Audit Events
    audit_events = [
        AuditEvent(
            id="log-1",
            timestamp="2026-10-12 14:32",
            user_id="user-admin",
            user_name="Dr. Rajesh Sharma",
            action="Platform Baseline Recalibration",
            details="Initiated statewide Q2 competency aggregation across 5 affiliated schools.",
            category="system",
        ),
        AuditEvent(
            id="log-2",
            timestamp="2026-10-12 11:15",
            user_id="user-principal-1",
            user_name="Dr. Sunita Deshmukh",
            action="Recorded Lost Instructional Days",
            details="Added 2 lost instructional days due to District Adolescent Health Drive.",
            category="curriculum",
        ),
        AuditEvent(
            id="log-3",
            timestamp="2026-10-11 16:40",
            user_id="user-teacher-1",
            user_name="Vikram Sengupta",
            action="Approved Cross-Curricular Integration",
            details="Merged Monument Geometry (Maths + Social Studies) saving 2 instructional periods.",
            category="curriculum",
        ),
        AuditEvent(
            id="log-4",
            timestamp="2026-10-10 09:20",
            user_id="user-teacher-1",
            user_name="Vikram Sengupta",
            action="Graded Offline Optical Scan Sheets",
            details="Verified AI OCR transcription for Class 8-A Cycle 2 Mathematics sheets.",
            category="assessment",
        ),
    ]
    for ae in audit_events:
        session.add(ae)

    await session.commit()
    await ensure_source_documents_and_question_bank(session)
    await link_demo_student(session)


async def link_demo_student(session: AsyncSession) -> None:
    # Seed this known demo identity once. Never infer links for other accounts.
    seed_event_id = "seed-demo-student-account-link-v1"
    if await session.get(AuditEvent, seed_event_id):
        return
    user = await session.get(User, "user-student-1")
    student = await session.get(Student, "user-student-1")
    if not user or not student or (
        user.email != "student@lumeneios.demo" or user.role != "student"
        or user.school_id != "school-1" or student.school_id != "school-1"
    ):
        return
    if await session.scalar(select(StudentAccountLink.id).where(or_(
        StudentAccountLink.user_id == user.id, StudentAccountLink.student_id == student.id,
    ))):
        return
    session.add_all([
        StudentAccountLink(user_id=user.id, student_id=student.id, created_by="user-admin"),
        AuditEvent(
            id=seed_event_id, timestamp=datetime.now(timezone.utc).isoformat(),
            user_id="user-admin", user_name="System", category="user",
            action="Linked demo student", details="Linked the seeded student login and roster record.",
        ),
    ])
    await session.commit()
    logger.info("Database seeding successfully completed!")


async def ensure_source_documents_and_question_bank(session: AsyncSession) -> None:
    """Idempotently seeds reference curriculum source documents and initial question bank items."""
    doc_check = await session.execute(select(Document).filter(Document.id == "doc-src-math-1"))
    if not doc_check.scalars().first():
        source_docs = [
            Document(
                id="doc-src-math-1",
                school_id="school-1",
                uploader_id="user-teacher-1",
                subject_id="sub-math",
                doc_type="source_material",
                file_name="NCERT_Grade8_Maths_Ch11_Mensuration_&_Volumes.pdf",
                file_size=1420500,
                mime_type="application/pdf",
                storage_path="./storage_uploads/NCERT_Grade8_Maths_Ch11_Mensuration.pdf",
                page_count=18,
                content_hash="sha256-mensuration-ch11-v1",
                extracted_text=(
                    "Chapter 11: Mensuration & Three-Dimensional Volumes. "
                    "Surface area of cuboid = 2(lb + bh + hl). Volume of cuboid = l * b * h. "
                    "Volume of cylinder = pi * r^2 * h. 1 cubic meter (m3) = 1000 Liters. "
                    "Doubling linear dimensions scales perimeter by factor 2, surface area by factor 4, and volume by factor 8."
                ),
                status="ready",
            ),
            Document(
                id="doc-src-math-2",
                school_id="school-1",
                uploader_id="user-teacher-1",
                subject_id="sub-math",
                doc_type="source_material",
                file_name="CBSE_Competency_Handbook_Rational_Numbers_&_Polygons.pdf",
                file_size=980200,
                mime_type="application/pdf",
                storage_path="./storage_uploads/CBSE_Rational_Numbers_Polygons.pdf",
                page_count=14,
                content_hash="sha256-rational-polygons-v1",
                extracted_text=(
                    "Rational Numbers & Geometric Classification. "
                    "Multiplicative inverse (reciprocal) of a/b is b/a such that (a/b)*(b/a) = 1. "
                    "Zero has no multiplicative inverse. Every square satisfies all properties of a rectangle "
                    "(four 90-degree interior angles and equal opposite sides), making squares a subset of rectangles."
                ),
                status="ready",
            ),
            Document(
                id="doc-src-sci-1",
                school_id="school-1",
                uploader_id="user-teacher-1",
                subject_id="sub-sci",
                doc_type="source_material",
                file_name="NCERT_Grade8_Science_Force_Pressure_&_Friction.pdf",
                file_size=1850000,
                mime_type="application/pdf",
                storage_path="./storage_uploads/NCERT_Science_Force_Friction.pdf",
                page_count=22,
                content_hash="sha256-science-friction-v1",
                extracted_text=(
                    "Force, Pressure, and Friction Dynamics. "
                    "Friction is a contact force opposing relative motion between surfaces in contact. "
                    "Gravitation is a non-contact attractive force. Fluid pressure increases with depth. "
                    "Buoyant force acts upward opposing weight; wet roadways cause hydroplaning by reducing tire friction."
                ),
                status="ready",
            ),
            Document(
                id="doc-src-eng-1",
                school_id="school-1",
                uploader_id="user-teacher-2",
                subject_id="sub-eng",
                doc_type="source_material",
                file_name="NEP2020_Reading_Comprehension_&_Analytical_Syntax.pdf",
                file_size=760400,
                mime_type="application/pdf",
                storage_path="./storage_uploads/NEP2020_Reading_Syntax.pdf",
                page_count=12,
                content_hash="sha256-english-syntax-v1",
                extracted_text=(
                    "Analytical Reading & Clause Identification. "
                    "In complex scientific sentences, identifying the grammatical subject and active verb clarifies cause and effect. "
                    "Persuasive civic writing requires empirical evidence, structured counterarguments, and clear synthesis."
                ),
                status="ready",
            ),
        ]
        for sd in source_docs:
            session.add(sd)

    qb_check = await session.execute(select(QuestionBankItem))
    if not qb_check.scalars().first():
        initial_qb = [
            QuestionBankItem(
                id="qb-1",
                school_id="school-1",
                subject_id="sub-math",
                text="A water tank is in the shape of a cuboid with length 4m, breadth 3m, and depth 2m. If water is poured at the rate of 60 liters per minute, how many hours will it take to fill the tank completely? (1 m³ = 1000 liters)",
                type="practical",
                options_json=[],
                correct_answer="Volume = 4 * 3 * 2 = 24 m³ = 24,000 L. Time = 24,000 / 60 = 400 minutes = 6 hours and 40 minutes.",
                marking_rubric="1m for cuboid volume formula (24 m³); 1m for m³ to Liter conversion (24,000 L); 1m for rate division (400 mins); 1m for hours/mins conversion (6h 40m).",
                marks=4,
                competency="AU",
                bloom_level="Apply",
                source_document_ids_json=["doc-src-math-1"],
                source_document_names_json=["NCERT_Grade8_Maths_Ch11_Mensuration_&_Volumes.pdf"],
                is_ai_generated=False,
                created_by="user-teacher-1",
            ),
            QuestionBankItem(
                id="qb-2",
                school_id="school-1",
                subject_id="sub-math",
                text="Identify the multiplicative inverse of -13/19 and explain why the product of a rational number and its inverse is always 1.",
                type="short",
                options_json=[],
                correct_answer="-19/13. By definition, a/b * (b/a) = (a*b)/(b*a) = 1.",
                marking_rubric="1m for stating -19/13; 1m for algebraic cancellation explanation.",
                marks=2,
                competency="CU",
                bloom_level="Understand",
                source_document_ids_json=["doc-src-math-2"],
                source_document_names_json=["CBSE_Competency_Handbook_Rational_Numbers_&_Polygons.pdf"],
                is_ai_generated=False,
                created_by="user-teacher-1",
            ),
            QuestionBankItem(
                id="qb-3",
                school_id="school-1",
                subject_id="sub-math",
                text="Which of the following numbers is a perfect square? A) 1057  B) 23453  C) 7928  D) 1089",
                type="mcq",
                options_json=["1057", "23453", "7928", "1089"],
                correct_answer="1089",
                marking_rubric="1m for selecting 1089 (33 * 33 = 1089; integers ending in 2, 3, 7, 8 cannot be perfect squares).",
                marks=1,
                competency="CU",
                bloom_level="Remember",
                source_document_ids_json=["doc-src-math-2"],
                source_document_names_json=["CBSE_Competency_Handbook_Rational_Numbers_&_Polygons.pdf"],
                is_ai_generated=False,
                created_by="user-teacher-1",
            ),
            QuestionBankItem(
                id="qb-4",
                school_id="school-1",
                subject_id="sub-sci",
                text="Compare and contrast the forces of Friction and Gravitation. In what practical scenario would reducing friction result in a dangerous loss of mechanical control?",
                type="descriptive",
                options_json=[],
                correct_answer="Friction is a contact force opposing relative motion; gravity is a non-contact field attraction. On wet roadways, hydroplaning eliminates tire-road friction, leading to steering failure.",
                marking_rubric="2m for distinguishing contact vs non-contact forces; 2m for valid real-world loss-of-control example (hydroplaning/braking).",
                marks=4,
                competency="CT",
                bloom_level="Analyze",
                source_document_ids_json=["doc-src-sci-1"],
                source_document_names_json=["NCERT_Grade8_Science_Force_Pressure_&_Friction.pdf"],
                is_ai_generated=False,
                created_by="user-teacher-1",
            ),
        ]
        for item in initial_qb:
            session.add(item)

    await session.commit()

