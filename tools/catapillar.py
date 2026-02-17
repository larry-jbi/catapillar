# tools/catapillar.py
# Catapillar CLI entry point
# 执行 .cat 文件 → 解析 → (Legacy DSL → Python) OR (Flow → Runtime)

import sys
import os
import warnings

# ------------------------------------------------------------
# 1️⃣ Ensure project root is on sys.path
# ------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ------------------------------------------------------------
# 2️⃣ Configure Catapillar warning behavior
# ------------------------------------------------------------
from parser.errors import CatapillarWarning, CatapillarError

def _show_catapillar_warning(message, category, filename, lineno, file=None, line=None):
    print(f"[Catapillar Warning] {message}")

warnings.showwarning = _show_catapillar_warning
warnings.simplefilter("always", CatapillarWarning)

# ------------------------------------------------------------
# 3️⃣ Import core components
# ------------------------------------------------------------
from parser.parser import parse_file

# Flow pipeline
from mapper.flow_mapper import map_program_to_flow
from runtime.engine import run_flow
from runtime.lexicon_loader import load_lexicon

# Legacy pipeline (python codegen)
try:
    from mapper.python_mapper import map_program as map_program_to_python
except Exception:
    map_program_to_python = None  # 允许你先不装 legacy mapper 也不崩

# 注册节点：API / robot
import runtime.api_nodes
import runtime.robot_nodes


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _iter_lines_from_ast(ast: dict):
    """
    Yield all statement nodes that could be Line/Block inside:
    Program -> flows[] -> segments[] -> lines[]
    """
    if not isinstance(ast, dict):
        return
    for flow in ast.get("flows", []) or []:
        for seg in flow.get("segments", []) or []:
            for stmt in seg.get("lines", []) or []:
                yield stmt

def _ast_contains_legacy_lines(ast: dict) -> bool:
    """
    Legacy DSL is represented by 'Line' (and sometimes 'Block' with inner 'lines').
    If we detect any Line (top-level or inside Block), we consider it legacy-capable.
    """
    for stmt in _iter_lines_from_ast(ast):
        t = stmt.get("type")
        if t == "Line":
            return True
        if t == "Block":
            for inner in stmt.get("lines", []) or []:
                if isinstance(inner, dict) and inner.get("type") == "Line":
                    return True
    return False

def _ast_contains_arrows(ast: dict) -> bool:
    """
    Flow syntax often manifests as 'Arrow' statements.
    """
    for stmt in _iter_lines_from_ast(ast):
        if stmt.get("type") == "Arrow":
            return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/catapillar.py <file.cat> [--mode auto|flow|python] [--exec]")
        sys.exit(1)

    # --- args
    path = sys.argv[1]
    mode = "auto"
    do_exec = False

    for arg in sys.argv[2:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1].strip().lower()
        elif arg == "--exec":
            do_exec = True

    # ✅ Load lexicons (keep your current behavior)
    load_lexicon("lexicon/default.yaml")
    load_lexicon("lexicon/agent.yaml")
    load_lexicon("lexicon/project_api.yaml")

    # Step 1: Parse .cat file into AST
    ast = parse_file(path)

    # Decide mode
    has_legacy = _ast_contains_legacy_lines(ast)
    has_arrows = _ast_contains_arrows(ast)

    # Auto strategy:
    # - If legacy lines exist: prefer python output (this restores your "old DSL" visibility)
    # - Else if arrows exist: run flow
    # - Else: try flow mapping anyway (may be empty), but still print AST so you can debug
    if mode not in ("auto", "flow", "python"):
        print(f"[Catapillar Error] Unknown mode: {mode}. Use --mode=auto|flow|python")
        sys.exit(1)

    chosen = mode
    if mode == "auto":
        if has_arrows:
            chosen = "flow"
        elif has_legacy:
            chosen = "python"
        else:
            chosen = "flow"

    # Step 2: Run selected pipeline
    if chosen == "python":
        if map_program_to_python is None:
            print("[Catapillar Error] python_mapper not available, cannot generate python.")
            print("\n=== AST ===")
            print(ast)
            return

        py_code = map_program_to_python(ast)

        print("=== PYTHON ===")
        print(py_code)

        if do_exec:
            print("\n=== EXEC ===")
            # Single namespace so top-level defs (e.g. 小计算器, main) are visible when main() runs
            glb = {"__name__": "__catapillar_exec__"}
            exec(py_code, glb)

        print("\n=== AST ===")
        print(ast)
        return

    # chosen == "flow"
    flow = map_program_to_flow(ast)

    print("=== FLOW ===")
    print(flow)

    if not flow:
        print("No executable flow generated.")
        print("\n=== AST ===")
        print(ast)
        return

    # Step 3: Execute runtime
    ctx = {}
    run_flow(flow, ctx)

    print("\n=== AST ===")
    print(ast)


if __name__ == "__main__":
    try:
        main()
    except CatapillarError as e:
        print(f"[Catapillar Error] {e}")
        sys.exit(1)
