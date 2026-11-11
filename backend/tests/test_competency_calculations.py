import pytest
from backend.app.models.entities import Student
from backend.app.services.competency_service import (
    calculate_composite_score,
    aggregate_student_competencies,
    generate_differentiated_recommendation,
)


def test_calculate_composite_score():
    assert calculate_composite_score(80, 80, 80, 80) == 80
    assert calculate_composite_score(70, 75, 80, 85) == 78  # 310 / 4 = 77.5 -> 78
    assert calculate_composite_score(100, 90, 80, 70) == 85


def test_aggregate_student_competencies():
    students = [
        Student(lu_score=60, cu_score=70, au_score=80, ct_score=90, overall_score=75),
        Student(lu_score=80, cu_score=80, au_score=80, ct_score=80, overall_score=80),
    ]
    agg = aggregate_student_competencies(students)
    assert agg["LU"] == 70
    assert agg["CU"] == 75
    assert agg["AU"] == 80
    assert agg["CT"] == 85
    assert agg["overall"] == 78


def test_differentiated_recommendation_weakest_lu():
    student = Student(
        name="Rohan Gupta",
        lu_score=48,  # weakest
        cu_score=74,
        au_score=62,
        ct_score=50,
        overall_score=58,
    )
    rec = generate_differentiated_recommendation(student)
    assert rec["competency"] == "LU"
    assert "Linguistic Scaffolding" in rec["title"]
    assert "LU score of 48%" in rec["reason"]


def test_differentiated_recommendation_weakest_au():
    student = Student(
        name="Priya Nair",
        lu_score=84,
        cu_score=60,
        au_score=52,  # weakest
        ct_score=58,
        overall_score=64,
    )
    rec = generate_differentiated_recommendation(student)
    assert rec["competency"] == "AU"
    assert "Mensuration" in rec["title"]
    assert "AU score of 52%" in rec["reason"]

