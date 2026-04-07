"""
Strips verbose/AI-style docstrings from Python source files.
Keeps only essential comments (TODO, FIXME, type: ignore, noqa, etc.)
and the LLM prompt template strings (RAG_SYSTEM_PROMPT etc.)
"""
import ast
import os
import sys
from pathlib import Path

# Files/dirs to skip
SKIP_DIRS = {'.venv', '__pycache__', '.pytest_cache', 'node_modules', '.git'}

# Template variable names to KEEP (these are functional, not comments)
KEEP_DOCSTRING_VARS = {
    'RAG_SYSTEM_PROMPT', 'RAG_CONTEXT_TEMPLATE', 'CONTEXT_CHUNK_TEMPLATE',
    'NO_CONTEXT_PROMPT', 'VERIFICATION_PROMPT'
}


def should_process(filepath: Path) -> bool:
    parts = filepath.parts
    return not any(skip in parts for skip in SKIP_DIRS)


def strip_docstrings(source: str, filepath: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        print(f"  SKIP (syntax error): {filepath}")
        return source

    lines = source.splitlines(keepends=True)
    removals = []  # list of (start_line, end_line) 1-indexed

    for node in ast.walk(tree):
        # Only strip docstrings from functions, methods, classes, and modules
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                doc_node = node.body[0]
                # Get the string value
                val = doc_node.value.value if isinstance(doc_node.value, ast.Constant) else doc_node.value.s

                # Skip if it's very short/useful (single-line, like "# noqa" equivalent)
                if isinstance(val, str) and len(val.strip()) < 15:
                    continue

                removals.append((doc_node.lineno, doc_node.end_lineno))

    if not removals:
        return source

    # Sort removals in reverse order so line numbers stay valid
    removals.sort(key=lambda x: x[0], reverse=True)

    for start, end in removals:
        # Remove the docstring lines (1-indexed to 0-indexed)
        del lines[start - 1:end]

    result = ''.join(lines)
    print(f"  Cleaned {len(removals)} docstring(s) from {filepath}")
    return result


def process_directory(root_dir: str):
    root = Path(root_dir)
    count = 0

    for py_file in sorted(root.rglob('*.py')):
        if not should_process(py_file):
            continue

        original = py_file.read_text(encoding='utf-8', errors='replace')
        cleaned = strip_docstrings(original, str(py_file.relative_to(root)))

        if cleaned != original:
            py_file.write_text(cleaned, encoding='utf-8')
            count += 1

    print(f"\nDone. Modified {count} files.")


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f"Stripping docstrings from: {target}")
    process_directory(target)
