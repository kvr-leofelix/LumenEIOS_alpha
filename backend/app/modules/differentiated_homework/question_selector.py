"""Question Selector: picks question bank items that target a student's weaker competencies.

Pure logic with no database access. Same inputs always give the same output, whatever
order the candidates arrive in.

Steps:
1. Sort candidates on all their fields, so even entries sharing an ID have a fixed order.
   Each excluded question is counted under the first rule it breaks: duplicate ID (any later
   copy of an ID already seen), wrong school, wrong subject, unsupported competency, invalid
   marks, AI-generated (when not requested), duplicate text (among questions already accepted).
2. Group the four competencies by their gap-analysis rank, weakest first. Competencies
   with the same score share a group.
3. Fill the requested number of questions from the weakest group first. Within a group,
   competencies take turns, so a tie doesn't favour one of them. Within a competency,
   questions are taken in question-ID order.
4. If a marks limit is set, a question that would exceed it is skipped, and selection
   continues with the next one.

PROVISIONAL POLICY, not agreed by the team: weakest-first priority, turn-taking within
ties, question-ID order, and skipping over-budget questions. No topic, difficulty or
Bloom-level balancing is applied, because the data or an agreed policy doesn't exist.
"""
from collections import Counter
from typing import Dict, List, Optional

from backend.app.modules.differentiated_homework.schemas import (
    COMPETENCIES,
    CandidateQuestion,
    GapAnalysis,
    SelectedQuestion,
    SelectionRequest,
    SelectionResult,
)


def normalize_competency(value: str) -> Optional[str]:
    """Return LU, CU, AU or CT, ignoring surrounding spaces and letter case; otherwise None.

    Other spellings, such as "Language Understanding", aren't guessed at.
    """
    cleaned = value.strip().upper() if isinstance(value, str) else ""
    return cleaned if cleaned in COMPETENCIES else None


def _text_key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _priority_groups(analysis: GapAnalysis) -> List[List[str]]:
    competencies = [gap.competency for gap in analysis.ranked]
    if len(competencies) != len(COMPETENCIES) or set(competencies) != set(COMPETENCIES):
        raise ValueError("Gap analysis must rank each of LU, CU, AU and CT exactly once")

    ranks = {gap.competency: gap.rank for gap in analysis.ranked}
    groups: List[List[str]] = []
    for rank in sorted(set(ranks.values())):
        groups.append([c for c in COMPETENCIES if ranks[c] == rank])
    return groups


def select_questions(
    analysis: GapAnalysis,
    candidates: List[CandidateQuestion],
    request: SelectionRequest,
) -> SelectionResult:
    groups = _priority_groups(analysis)
    rank_of = {gap.competency: gap.rank for gap in analysis.ranked}

    excluded: Counter = Counter()
    pools: Dict[str, List[CandidateQuestion]] = {c: [] for c in COMPETENCIES}
    seen_ids, seen_texts = set(), set()

    def order_key(q: CandidateQuestion):
        return (q.id, q.school_id, q.subject_id, q.competency, q.marks, q.text, q.type, q.bloom_level, q.is_ai_generated)

    for question in sorted(candidates, key=order_key):
        competency = normalize_competency(question.competency)
        if question.id in seen_ids:
            excluded["duplicate_id"] += 1
            continue
        seen_ids.add(question.id)

        if question.school_id != request.school_id:
            excluded["wrong_school"] += 1
        elif question.subject_id != request.subject_id:
            excluded["wrong_subject"] += 1
        elif competency is None:
            excluded["unsupported_competency"] += 1
        elif question.marks < 1:
            excluded["invalid_marks"] += 1
        elif question.is_ai_generated and not request.include_ai_generated:
            excluded["ai_generated_not_requested"] += 1
        elif _text_key(question.text) in seen_texts:
            excluded["duplicate_text"] += 1
        else:
            seen_texts.add(_text_key(question.text))
            pools[competency].append(question)

    eligible_by_competency = {c: len(pools[c]) for c in COMPETENCIES}

    selected: List[SelectedQuestion] = []
    total_marks = 0
    skipped_for_marks = 0

    def room_left() -> bool:
        return len(selected) < request.max_questions

    def fits(question: CandidateQuestion) -> bool:
        return request.max_total_marks is None or total_marks + question.marks <= request.max_total_marks

    for group in groups:
        queues = {c: list(pools[c]) for c in group}
        while room_left() and any(queues.values()):
            for competency in group:
                if not room_left():
                    break
                queue = queues[competency]
                while queue:
                    question = queue.pop(0)
                    if fits(question):
                        selected.append(
                            SelectedQuestion(
                                question_id=question.id,
                                competency=competency,
                                competency_rank=rank_of[competency],
                                marks=question.marks,
                                type=question.type,
                                bloom_level=question.bloom_level,
                                is_ai_generated=question.is_ai_generated,
                                text=question.text,
                            )
                        )
                        total_marks += question.marks
                        break
                    skipped_for_marks += 1
        if not room_left():
            break

    shortfall = request.max_questions - len(selected)
    notes: List[str] = []
    if not analysis.weakest:
        notes.append("All competency scores are equal, so every competency had the same priority.")
    missing = [c for c in groups[0] if eligible_by_competency[c] == 0]
    if missing:
        notes.append(f"No eligible questions for the weakest competency group: {', '.join(missing)}.")
    if skipped_for_marks:
        notes.append(f"{skipped_for_marks} eligible question(s) skipped because they would exceed the marks limit.")
    if shortfall:
        notes.append(f"Selected {len(selected)} of {request.max_questions} requested questions.")

    return SelectionResult(
        student_id=analysis.student_id,
        selected=selected,
        total_marks=total_marks,
        requested_questions=request.max_questions,
        max_total_marks=request.max_total_marks,
        shortfall=shortfall,
        priority=groups,
        eligible_by_competency=eligible_by_competency,
        excluded=dict(excluded),
        notes=notes,
    )
