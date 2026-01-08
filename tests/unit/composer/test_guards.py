import ast
import unittest
from pathlib import Path


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


class TestComposerGuards(unittest.TestCase):
    def test_no_forbidden_imports(self) -> None:
        composer_root = Path(__file__).resolve().parents[3] / "src" / "composer"
        python_files = list(composer_root.rglob("*.py"))
        forbidden = {
            "orchestrator",
            "consumers",
            "regime_engine",
            "random",
            "secrets",
            "time",
            "datetime",
        }
        for path in python_files:
            with self.subTest(path=str(path)):
                imports = _imported_modules(path)
                self.assertTrue(forbidden.isdisjoint(imports))


if __name__ == "__main__":
    unittest.main()
