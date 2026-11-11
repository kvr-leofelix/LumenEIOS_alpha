import json

import pytest

from backend.app.services.llm_service import (
    build_studio_prompt,
    parse_studio_questions,
    stamp_competency,
)


def test_studio_parser_keeps_requested_types_and_rejects_bad_counts():
    raw = """```json
    {"mcqs":[
      {"type":"mcq","text":"Which is correct?","options":["A","B","C","D"],"correct_answer":"A","marking_rubric":"Choose A","competency":"CU"}
    ],"theory":[
      {"type":"descriptive","text":"Explain the idea.","correct_answer":"Because...","marking_rubric":"Reasoning","competency":"CT"}
    ]}
    ```"""
    questions = parse_studio_questions(raw, mcq_count=1, theory_count=1)

    assert [question["type"] for question in questions] == ["mcq", "descriptive"]
    assert [question["marks"] for question in questions] == [2, 5]
    with pytest.raises(ValueError, match="unexpected number"):
        parse_studio_questions(raw, mcq_count=2, theory_count=1)
    with pytest.raises(ValueError, match="invalid theory"):
        parse_studio_questions(raw.replace('"descriptive"', '"mcq"'), mcq_count=1, theory_count=1)


def test_studio_prompt_assigns_each_competency_and_the_recommended_answer():
    prompt = build_studio_prompt("Science", 2, 2, "Analyze", "friction", "chapter context")
    for phrase in (
        "LU: Language Understanding",
        "CU: Conceptual Understanding",
        "AU: Application",
        "CT: Critical Thinking",
        "recommended answer",
    ):
        assert phrase in prompt
    assert prompt.index("MCQ 1 must test LU") < prompt.index("MCQ 2 must test CU")
    assert "Theory 1 must test AU" in prompt
    assert "Theory 2 must test CT" in prompt


def test_stamp_keeps_the_mcq_option_and_labels_the_theory_answer():
    mcq = {"type": "mcq", "competency": "LU", "correct_answer": "A", "marking_rubric": "Choose A"}
    stamp_competency(mcq)
    assert mcq["correct_answer"] == "A"
    assert mcq["marking_rubric"].startswith("LU: Language Understanding")

    theory = {"type": "descriptive", "competency": "CT", "correct_answer": "Because", "marking_rubric": "Reason"}
    stamp_competency(theory)
    assert "Recommended answer focus — CT" in theory["correct_answer"]
    assert theory["marking_rubric"].startswith("CT: Critical Thinking")


@pytest.mark.asyncio
async def test_studio_progress_stream_reports_completion():
    from backend.app.services.progress import report_progress, stream_job

    async def work():
        report_progress("write", "Wrote question 1 of 1", 1, 1)
        return {"generated_count": 1}

    response = stream_job(work)
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    streamed = [
        json.loads(line[6:])
        for line in "".join(chunks).split("\n")
        if line.startswith("data: ")
    ]
    assert streamed[0]["kind"] == "progress"
    assert streamed[0]["done"] == 1 and streamed[0]["total"] == 1
    assert streamed[1] == {"kind": "complete", "result": {"generated_count": 1}}
