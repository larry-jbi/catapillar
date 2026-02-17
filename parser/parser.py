# parser/parser.py
# Catapillar Parser
# Converts tokenized lines into AST structure.
# Supports both legacy action lines and new Arrow-based intent lines.

from typing import List, Dict
from parser.errors import ParseError


# ------------------------------------------------------------
# Canonical Action Set (Legacy DSL Support)
# These are only used for non-arrow lines.
# ------------------------------------------------------------

ACTION_IDS = {
    "PRINT": {"print", "印"},
    "SET": {"set", "置"},
    "CALL": {"call", "调"},
    # v0.2 extensions for calculator
    "DEF": {"def", "定"},
    "RETURN": {"return", "回"},
    "IF": {"if", "若"},
    "ELIF": {"elif", "又若"},
    "ELSE": {"else", "否则"},
    "WHILE": {"while", "当"},
    "FOR": {"for", "扭扭"},
    "BREAK": {"break", "断"},
    "CONTINUE": {"continue", "续"},
    "TRY": {"try", "试"},
    "EXCEPT": {"except", "捕"},
    "FINALLY": {"finally", "终于"},
    "PASS": {"pass", "空"},
    # Arithmetic operations
    "ADD": {"add", "加"},
    "SUB": {"sub", "减"},
    "MUL": {"mul", "乘"},
    "DIV": {"div", "除"},
}

STRUCT_IDS = {
    "BLOCK_END": {"end","结束","完了","终"},
}

ACTION_LOOKUP = {
    word: action_id
    for action_id, words in ACTION_IDS.items()
    for word in words
}

STRUCT_LOOKUP = {
    word: struct_id
    for struct_id, words in STRUCT_IDS.items()
    for word in words
}


LINE_STATES = {"~", ">", "<", "!", "?"}


# ============================================================
# Core Parser
# ============================================================

def parse_tokens(tokens: List[Dict]) -> Dict:
    """
    Convert token list into Catapillar AST.

    Supports:
        - Arrow lines (intent flow)
        - Legacy action lines
    """

    program = {
        "type": "Program",
        "flows": [],
    }

    current_flow = {
        "type": "Flow",
        "segments": [],
    }

    current_segment = {
        "type": "Segment",
        "lines": [],
    }

    for token in tokens:

        raw_action = token["raw_action"]
        raw_args = token["raw_args"]
        line_state = token["line_state"]

        # 先检测结构关键字
        if raw_action in STRUCT_LOOKUP:
            struct_id = STRUCT_LOOKUP[raw_action]

            if struct_id == "BLOCK_END":
                # Emit a BLOCK_END node so the mapper can dedent
                line_node = {
                    "type": "BLOCK_END",
                    "line_state": line_state,
                }
                current_segment["lines"].append(line_node)
                continue

        # ----------------------------------------------------
        # 1️⃣ Validate line_state
        # ----------------------------------------------------
        if line_state not in LINE_STATES:
            raise ParseError(f"Invalid line_state: {line_state}")

        # ----------------------------------------------------
        # Detect Arrow Syntax
        # Arrow lines do NOT require ACTION_LOOKUP
        # ----------------------------------------------------
        arrow_type = None

        if "->" in raw_args:
            arrow_type = "->"
        elif "<-" in raw_args:
            arrow_type = "<-"

        # ----------------------------------------------------
        # 2️⃣ Detect Block Definition (e.g. 保存流程:) or control keywords with :
        # ----------------------------------------------------
        if raw_action.endswith(":"):
            block_name = raw_action[:-1]  # 去掉冒号

            # Check if this is a control keyword that should be an action
            # These are: 否则 (else), 试 (try), 终于 (finally)
            if block_name in ["否则", "else"]:
                # This is an ELSE statement
                line_node = {
                    "type": "Line",
                    "action": "ELSE",
                    "args": [],
                    "line_state": line_state,
                }
                current_segment["lines"].append(line_node)
                continue
            elif block_name in ["试", "try"]:
                # This is a TRY statement
                line_node = {
                    "type": "Line",
                    "action": "TRY",
                    "args": [],
                    "line_state": line_state,
                }
                current_segment["lines"].append(line_node)
                continue
            elif block_name in ["终于", "finally"]:
                # This is a FINALLY statement
                line_node = {
                    "type": "Line",
                    "action": "FINALLY",
                    "args": [],
                    "line_state": line_state,
                }
                current_segment["lines"].append(line_node)
                continue
            else:
                # Regular block (like flow names)
                block_node = {
                    "type": "Block",
                    "name": block_name,
                    "lines": [],
                    "line_state": line_state,
                }

                current_segment["lines"].append(block_node)
                continue

        # ----------------------------------------------------
        # 3️⃣ Handle Arrow Lines
        # ----------------------------------------------------
        if arrow_type:

            idx = raw_args.index(arrow_type)

            if idx + 1 >= len(raw_args):
                raise ParseError("Arrow missing target")

            left = raw_action
            right = raw_args[idx + 1]

            if arrow_type == "->":
                from_node = left
                to_node = right
            else:  # "<-"
                from_node = right
                to_node = left

            line_node = {
                "type": "Arrow",
                "from": from_node,
                "to": to_node,
                "direction": arrow_type,
                "line_state": line_state,
            }

            current_segment["lines"].append(line_node)

        # ----------------------------------------------------
        # 4️⃣ Handle Legacy Action Lines
        # ----------------------------------------------------
        else:

            if raw_action not in ACTION_LOOKUP:
                raise ParseError(f"Unknown action: {raw_action}")

            action_id = ACTION_LOOKUP[raw_action]

            line_node = {
                "type": "Line",
                "action": action_id,
                "args": raw_args,
                "line_state": line_state,
            }

            current_segment["lines"].append(line_node)

        # ----------------------------------------------------
        # 5️⃣ Segment Closing Logic
        # ----------------------------------------------------
        if line_state == ">":
            current_flow["segments"].append(current_segment)
            current_segment = {
                "type": "Segment",
                "lines": [],
            }

    # --------------------------------------------------------
    # Flush final segment
    # --------------------------------------------------------
    if current_segment["lines"]:
        current_flow["segments"].append(current_segment)

    # Flush flow
    if current_flow["segments"]:
        program["flows"].append(current_flow)

    return program


# ============================================================
# Convenience Wrapper
# ============================================================

def parse_file(path: str) -> Dict:
    """
    Tokenize + parse in one step.
    """
    from parser.tokenizer import tokenize_file
    tokens = tokenize_file(path)
    return parse_tokens(tokens)
