"""The docs site must document every public member of the main classes, and build without errors."""
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs" / "src"


def test_reference_covers_every_public_member():
    sys.path.insert(0, str(DOCS))
    try:
        import build

        assert build.check_reference() == []
    finally:
        sys.path.remove(str(DOCS))


def test_every_public_function_has_an_example():
    import ast

    root = Path(__file__).resolve().parent.parent / "src" / "nicebot"
    missing = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def walk(node, prefix=""):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = prefix + child.name
                    doc = ast.get_docstring(child) or ""
                    if not child.name.startswith("_") and child.name != "Meta" and "Example" not in doc:
                        missing.append(f"{path.name}:{name}")
                    if isinstance(child, ast.ClassDef) and not child.name.startswith("_"):
                        walk(child, name + ".")

        walk(tree)
    assert missing == []
