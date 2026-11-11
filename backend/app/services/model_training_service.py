import difflib
from typing import Dict, List, Any, Tuple


def calculate_cer_wer(reference: str, hypothesis: str) -> Tuple[float, float]:
    """
    Computes Character Error Rate (CER) and Word Error Rate (WER) using Levenshtein distance.
    """
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    
    char_matcher = difflib.SequenceMatcher(None, ref_chars, hyp_chars)
    char_distance = len(ref_chars) + len(hyp_chars) - 2 * sum(match.size for match in char_matcher.get_matching_blocks())
    cer = round(char_distance / max(1, len(ref_chars)), 4)

    ref_words = reference.split()
    hyp_words = hypothesis.split()
    word_matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
    word_distance = len(ref_words) + len(hyp_words) - 2 * sum(match.size for match in word_matcher.get_matching_blocks())
    wer = round(word_distance / max(1, len(ref_words)), 4)

    return min(1.0, cer), min(1.0, wer)


def partition_dataset_by_student(
    examples: List[Dict[str, Any]],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Partitions annotations by student ID to prevent data leakage across splits.
    """
    students = list(set(e["student_id"] for e in examples if "student_id" in e))
    students.sort()
    
    n_total = len(students)
    n_train = max(1, int(n_total * train_ratio))
    n_val = max(1, int(n_total * val_ratio))
    
    train_students = set(students[:n_train])
    val_students = set(students[n_train : n_train + n_val])
    test_students = set(students[n_train + n_val :])

    splits = {"train": [], "val": [], "test": []}
    for ex in examples:
        st_id = ex.get("student_id")
        if st_id in train_students:
            splits["train"].append(ex)
        elif st_id in val_students:
            splits["val"].append(ex)
        else:
            splits["test"].append(ex)
            
    return splits


def check_model_promotion_criteria(cer: float, wer: float, field_accuracy: float) -> Tuple[bool, str]:
    """
    Evaluates whether candidate model satisfies production gates:
    - CER <= 0.05 (<=5% character error)
    - WER <= 0.12 (<=12% word error)
    - Field Accuracy >= 0.90
    """
    if cer > 0.05:
        return False, f"Failed promotion: Character Error Rate ({cer*100:.1f}%) exceeds threshold of 5.0%."
    if wer > 0.12:
        return False, f"Failed promotion: Word Error Rate ({wer*100:.1f}%) exceeds threshold of 12.0%."
    if field_accuracy < 0.90:
        return False, f"Failed promotion: Field accuracy ({field_accuracy*100:.1f}%) below threshold of 90.0%."
    return True, "Model passed all benchmark gates for production deployment."

