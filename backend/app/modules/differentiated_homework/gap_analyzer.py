"""Gap Analyzer: finds a student's relatively weakest competency.

Pure logic with no database access, so it works the same with any data source.

It compares the four scores with each other. It doesn't decide whether a score is
"low enough" to need support: no threshold has been agreed, so none is applied here.
"""
from backend.app.modules.differentiated_homework.schemas import (
    COMPETENCIES,
    CompetencyGap,
    CompetencyProfile,
    GapAnalysis,
)


def analyze_gaps(profile: CompetencyProfile) -> GapAnalysis:
    scores = profile.scores
    lowest = min(scores.values())
    highest = max(scores.values())

    ranked = []
    for competency in sorted(COMPETENCIES, key=lambda c: (scores[c], COMPETENCIES.index(c))):
        score = scores[competency]
        baseline = profile.baseline[competency] if profile.baseline else None
        ranked.append(
            CompetencyGap(
                competency=competency,
                score=score,
                rank=1 + sum(1 for other in scores.values() if other < score),
                baseline=baseline,
                change_from_baseline=None if baseline is None else score - baseline,
            )
        )

    # A competency only counts as weakest if at least one other scores higher.
    weakest = [c for c in COMPETENCIES if scores[c] == lowest] if highest > lowest else []

    notes = []
    if not weakest:
        notes.append("All four competency scores are equal, so no weakest competency can be identified.")
    elif len(weakest) > 1:
        notes.append(f"{len(weakest)} competencies tie for the lowest score: {', '.join(weakest)}.")

    return GapAnalysis(
        student_id=profile.student_id,
        ranked=ranked,
        weakest=weakest,
        has_single_weakest=len(weakest) == 1,
        lowest_score=lowest,
        highest_score=highest,
        spread=highest - lowest,
        source=profile.source,
        notes=notes,
    )
