"""评测题库的结构性回归测试。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


QUESTIONS_FILE = Path(__file__).resolve().parents[2] / "eval" / "questions.json"


class EvalQuestionSetTests(unittest.TestCase):
    def setUp(self) -> None:
        with QUESTIONS_FILE.open(encoding="utf-8") as file:
            self.questions = json.load(file)["questions"]

    def test_is_a_40_question_after_sales_regression_set(self) -> None:
        """作品集题库必须是可解释的 40 条售后回归题，而非凑数。"""
        self.assertEqual(40, len(self.questions))
        self.assertEqual(list(range(1, 41)), [item["id"] for item in self.questions])

    def test_has_five_safe_transfer_cases(self) -> None:
        """未知商品、订单态与非售后请求均应验证安全转人工。"""
        transfer_questions = [
            item for item in self.questions if item["expected_behavior"] == "transfer_human"
        ]
        self.assertEqual(5, len(transfer_questions))

    def test_every_answer_case_has_a_judgment_anchor(self) -> None:
        """应答题要有关键词锚点，避免只有问题数量没有可复核的判定。"""
        for item in self.questions:
            if item["expected_behavior"] == "answer":
                self.assertTrue(item["expected_keywords"], item["id"])


if __name__ == "__main__":
    unittest.main()
