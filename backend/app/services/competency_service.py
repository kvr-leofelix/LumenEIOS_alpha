from typing import Dict, List, Any
from backend.app.models.entities import Student, AssessmentSubmission, StudentCompetencySnapshot


def calculate_composite_score(lu: int, cu: int, au: int, ct: int) -> int:
    return round((lu + cu + au + ct) / 4)


def aggregate_student_competencies(students: List[Student]) -> Dict[str, Any]:
    if not students:
        return {
            "LU": 0, "CU": 0, "AU": 0, "CT": 0, "overall": 0
        }
    count = len(students)
    return {
        "LU": round(sum(s.lu_score for s in students) / count),
        "CU": round(sum(s.cu_score for s in students) / count),
        "AU": round(sum(s.au_score for s in students) / count),
        "CT": round(sum(s.ct_score for s in students) / count),
        "overall": round(sum(s.overall_score for s in students) / count),
    }


def generate_differentiated_recommendation(student: Student) -> Dict[str, Any]:
    """
    Deterministic rule-based pedagogical homework generator.
    Identifies the student's weakest foundational dimension and recommends targeted remediation.
    """
    scores = {
        "LU": student.lu_score,
        "CU": student.cu_score,
        "AU": student.au_score,
        "CT": student.ct_score,
    }
    weakest_dim = min(scores, key=scores.get)
    score_val = scores[weakest_dim]

    if weakest_dim == "LU":
        return {
            "competency": "LU",
            "title": "Word Problem Linguistic Scaffolding: Visual Keyword Annotations",
            "reason": f"Student has an LU score of {score_val}%. Struggles with phrase parsing in multi-clause statements.",
            "description": "Worksheet with 6 real-world rate problems featuring color-coded key phrases, bilingual glossaries, and step-by-step clause breakdown."
        }
    elif weakest_dim == "CU":
        return {
            "competency": "CU",
            "title": "Visual Concept Mapping & Number Line Decomposition",
            "reason": f"Student has a CU score of {score_val}%. Needs concrete diagrammatic models before abstract algebra.",
            "description": "Hands-on diagrammatic representation of rational operations and algebraic variables using interactive balance scales."
        }
    elif weakest_dim == "AU":
        return {
            "competency": "AU",
            "title": "Real-World Household Mensuration & Data Collection Lab",
            "reason": f"Student has an AU score of {score_val}%. Theoretical knowledge is sound but unit conversions need practice.",
            "description": "Home activity: Measure dimensions of 3 cylindrical food containers, compute theoretical volume in cm3, and verify with a graduated measuring beaker."
        }
    else:
        return {
            "competency": "CT",
            "title": "Counterexample Investigation & Fallacy Detection",
            "reason": f"Student has a CT score of {score_val}%. Needs practice evaluating conjectures and biased charts.",
            "description": "Analyze 3 commercial news adverts showing truncated bar chart axes. Identify the perceptual distortion and re-plot with honest zero baselines."
        }

