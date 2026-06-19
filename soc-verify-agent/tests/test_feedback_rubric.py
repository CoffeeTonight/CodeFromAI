from __future__ import annotations

from pathlib import Path

from soc_verify.feedback_rubric import score_all_questions, write_user_feedback


def test_question_sharpness_auto_not_user_score():
    qs = [
        {
            "id": "Q1",
            "type": "stalemate",
            "context": "sim/g",
            "question": "Same failure repeated; please review logs and provide guidance?",
            "blocking": "yes",
        }
    ]
    result = score_all_questions(qs)
    assert result["mean_sharpness"] >= 3.0
    assert result["questions"][0]["scorer"] == "platform_heuristic"


def test_user_feedback_optional(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    p = write_user_feedback(run_dir, overall_score=4, comment="helpful")
    assert p.is_file()