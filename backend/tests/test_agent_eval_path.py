import tempfile
import unittest
from pathlib import Path

from app.services import agent_eval_runner


class AgentEvalPathTests(unittest.TestCase):
    def test_container_eval_directory_wins_when_it_exists(self):
        resolver = getattr(agent_eval_runner, "_resolve_eval_dir", None)
        self.assertIsNotNone(resolver, "需要一个可测试的评测目录解析函数")

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            container_eval = root / "app" / "eval"
            project_eval = root / "project" / "eval"
            container_eval.mkdir(parents=True)
            project_eval.mkdir(parents=True)

            self.assertEqual(
                resolver(project_eval.parent, container_eval),
                container_eval,
            )


if __name__ == "__main__":
    unittest.main()
