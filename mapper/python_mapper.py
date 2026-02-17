# mapper/python_mapper.py
# Catapillar v0.2 Python mapper
# Responsibility: AST -> Python source code with proper indentation and control flow

from typing import Dict, List, Tuple


class MapError(Exception):
    pass


class IndentContext:
    """Manages indentation levels for Python code generation."""
    def __init__(self):
        self.level = 0
        self.indent_str = "    "  # 4 spaces
        self.last_was_block_end = False  # True after 终; used so ELIF/ELSE don't dedent twice

    def indent(self):
        """Increase indentation level."""
        self.level += 1

    def dedent(self):
        """Decrease indentation level."""
        if self.level > 0:
            self.level -= 1

    def get_indent(self) -> str:
        """Get current indentation string."""
        return self.indent_str * self.level


def map_program(program: Dict) -> str:
    """
    Map AST Program node to Python source code.
    """
    if program.get("type") != "Program":
        raise MapError("Root node must be Program")

    ctx = IndentContext()
    lines: List[str] = []

    for flow in program.get("flows", []):
        lines.extend(map_flow(flow, ctx))

    return "\n".join(lines)


def map_flow(flow: Dict, ctx: IndentContext) -> List[str]:
    """
    Map Flow node.
    """
    if flow.get("type") != "Flow":
        raise MapError("Expected Flow node")

    lines: List[str] = []

    for segment in flow.get("segments", []):
        lines.extend(map_segment(segment, ctx))

    return lines


def map_segment(segment: Dict, ctx: IndentContext) -> List[str]:
    """
    Map Segment node.
    """
    if segment.get("type") != "Segment":
        raise MapError("Expected Segment node")

    lines: List[str] = []

    for line in segment.get("lines", []):
        result = map_statement(line, ctx)
        if result:
            lines.extend(result)

    return lines


def map_statement(stmt: Dict, ctx: IndentContext) -> List[str]:
    """
    Map a statement (Line, Block, Arrow, or BLOCK_END) to Python code.
    Returns a list of lines (may be multiple for blocks).
    """
    stmt_type = stmt.get("type")

    if stmt_type == "Line":
        result = map_line_with_block_end_tracking(stmt, ctx)
        ctx.last_was_block_end = False
        return result
    elif stmt_type == "Block":
        ctx.last_was_block_end = False
        return map_block(stmt, ctx)
    elif stmt_type == "BLOCK_END":
        ctx.dedent()
        ctx.last_was_block_end = True
        return []
    elif stmt_type == "Arrow":
        return []
    else:
        raise MapError(f"Unknown statement type: {stmt_type}")


def map_block(block: Dict, ctx: IndentContext) -> List[str]:
    """
    Map a Block node (currently just a placeholder in parser).
    """
    # Blocks in current parser are just markers, lines are handled separately
    return []


def map_line_with_block_end_tracking(line: Dict, ctx: IndentContext) -> List[str]:
    """Dispatch to map_line; dedent once before ELIF/ELSE/EXCEPT/FINALLY when no 终 preceded them."""
    action = line.get("action")
    if action in ("ELIF", "ELSE", "EXCEPT", "FINALLY") and not ctx.last_was_block_end:
        ctx.dedent()
    return map_line(line, ctx)


def map_line(line: Dict, ctx: IndentContext) -> List[str]:
    """
    Map Line node to Python code (may return multiple lines for control structures).
    """
    if line.get("type") != "Line":
        raise MapError("Expected Line node")

    action = line.get("action")
    args = line.get("args", [])
    
    indent = ctx.get_indent()

    # Control flow and blocks
    if action == "DEF":
        return map_def(args, ctx)
    elif action == "IF":
        return map_if(args, ctx)
    elif action == "ELIF":
        return map_elif(args, ctx)
    elif action == "ELSE":
        return map_else(args, ctx)
    elif action == "WHILE":
        return map_while(args, ctx)
    elif action == "FOR":
        return map_for(args, ctx)
    elif action == "TRY":
        return map_try(args, ctx)
    elif action == "EXCEPT":
        return map_except(args, ctx)
    elif action == "FINALLY":
        return map_finally(args, ctx)
    
    # Simple statements
    elif action == "RETURN":
        return [indent + map_return(args)]
    elif action == "BREAK":
        return [indent + "break"]
    elif action == "CONTINUE":
        return [indent + "continue"]
    elif action == "PASS":
        return [indent + "pass"]
    elif action == "PRINT":
        return [indent + map_print(args)]
    elif action == "SET":
        return [indent + map_set(args)]
    elif action == "CALL":
        return [indent + map_call(args)]
    
    # Arithmetic operations
    elif action == "ADD":
        return [indent + map_arithmetic(args, "+")]
    elif action == "SUB":
        return [indent + map_arithmetic(args, "-")]
    elif action == "MUL":
        return [indent + map_arithmetic(args, "*")]
    elif action == "DIV":
        return [indent + map_arithmetic(args, "/")]
    
    raise MapError(f"Unhandled ActionID: {action}")


def map_def(args: List[str], ctx: IndentContext) -> List[str]:
    """Map function definition: 定 函数名 参数...:"""
    if not args:
        raise MapError("DEF expects at least a function name")
    
    indent = ctx.get_indent()
    
    # Extract function name and parameters
    # Function name is first arg, params are rest (may have : at end)
    func_name = args[0].rstrip(":")
    
    if len(args) == 1:
        # Just function name, no params: 定 函数名:
        param_str = ""
    else:
        # Has parameters: 定 函数名 参数1 参数2:
        params = [p.rstrip(":") for p in args[1:]]
        param_str = ", ".join(params)
    
    ctx.indent()
    return [indent + f"def {func_name}({param_str}):"]


def map_if(args: List[str], ctx: IndentContext) -> List[str]:
    """Map if statement: 若 条件...:"""
    if not args:
        raise MapError("IF expects a condition")
    
    indent = ctx.get_indent()
    condition = build_condition(args)
    ctx.indent()
    return [indent + f"if {condition}:"]


def map_elif(args: List[str], ctx: IndentContext) -> List[str]:
    """Map elif statement: 又若 条件...:"""
    if not args:
        raise MapError("ELIF expects a condition")
    
    indent = ctx.get_indent()
    condition = build_condition(args)
    ctx.indent()
    return [indent + f"elif {condition}:"]


def map_else(args: List[str], ctx: IndentContext) -> List[str]:
    """Map else statement: 否则:"""
    indent = ctx.get_indent()
    ctx.indent()
    return [indent + "else:"]


def map_while(args: List[str], ctx: IndentContext) -> List[str]:
    """Map while loop: 当 条件...:"""
    if not args:
        raise MapError("WHILE expects a condition")
    
    indent = ctx.get_indent()
    condition = build_condition(args)
    ctx.indent()
    return [indent + f"while {condition}:"]


def map_for(args: List[str], ctx: IndentContext) -> List[str]:
    """Map for loop: 扭扭 变量 in 序列:"""
    if len(args) < 3:
        raise MapError("FOR expects: variable in iterable")
    
    indent = ctx.get_indent()
    var = args[0]
    # Skip 'in' keyword if present
    if args[1] == "in":
        iterable = " ".join(args[2:]).rstrip(":")
    else:
        iterable = " ".join(args[1:]).rstrip(":")
    
    ctx.indent()
    return [indent + f"for {var} in {iterable}:"]


def map_try(args: List[str], ctx: IndentContext) -> List[str]:
    """Map try block: 试:"""
    indent = ctx.get_indent()
    ctx.indent()
    return [indent + "try:"]


def map_except(args: List[str], ctx: IndentContext) -> List[str]:
    """Map except block: 捕 异常类型:"""
    indent = ctx.get_indent()
    
    if args:
        exception = args[0].rstrip(":")
        # Map Chinese exception names to Python
        exception_map = {
            "零除错误": "ZeroDivisionError",
            "其他错误": "Exception",
        }
        py_exception = exception_map.get(exception, exception)
        ctx.indent()
        return [indent + f"except {py_exception}:"]
    else:
        ctx.indent()
        return [indent + "except:"]


def map_finally(args: List[str], ctx: IndentContext) -> List[str]:
    """Map finally block: 终于:"""
    indent = ctx.get_indent()
    ctx.indent()
    return [indent + "finally:"]


def map_return(args: List[str]) -> str:
    """Map return statement: 回 值"""
    if not args:
        return "return"
    
    value = to_py_value(" ".join(args))
    return f"return {value}"


def map_print(args: List[str]) -> str:
    """Map print statement: 印 值...
    Single identifier -> variable (print(x)). Multiple or non-identifier -> one string literal.
    """
    if not args:
        return "print()"
    if len(args) == 1 and is_valid_identifier(args[0]):
        return f"print({args[0]})"
    # Literal text: join with space and emit as one string
    literal = " ".join(args)
    escaped = literal.replace("\\", "\\\\").replace('"', '\\"')
    return f'print("{escaped}")'


def map_set(args: List[str]) -> str:
    """Map assignment: 置 变量 值 OR 置 变量 表达式"""
    if len(args) < 2:
        raise MapError("SET expects at least 2 arguments: variable value")
    
    name = args[0]
    
    if not is_valid_identifier(name):
        raise MapError(f"Invalid variable name: {name}")
    
    # Handle special function calls (读数, 加, etc.)
    if len(args) == 2:
        # Single value assignment: 置 变量 值
        value_arg = args[1]
        # Check if it's a function call (function name without parens)
        if is_valid_identifier(value_arg) and value_arg in ["读数", "读运算符", "input", "float", "int", "str"]:
            # It's a function call
            value = f"{value_arg}()"
        else:
            value = to_py_value(value_arg)
    elif len(args) == 3:
        # Could be: 置 变量 函数 参数 (like: 置 left_num float left)
        func_or_op = args[1]
        third_arg = args[2]
        
        # Check for arithmetic operations
        if func_or_op in ["加", "add"]:
            raise MapError("ADD in SET expects 4 args: 置 result 加 left right")
        elif func_or_op in ["减", "sub"]:
            raise MapError("SUB in SET expects 4 args: 置 result 减 left right")
        elif func_or_op in ["乘", "mul"]:
            raise MapError("MUL in SET expects 4 args: 置 result 乘 left right")
        elif func_or_op in ["除", "div"]:
            raise MapError("DIV in SET expects 4 args: 置 result 除 left right")
        else:
            # Function call with one argument: 置 变量 函数 参数
            value = f"{func_or_op}({to_py_value(third_arg)})"
    else:
        # Multi-arg: function call like 置 结果 加 左 右
        operation = args[1]
        if operation in ["加", "add"]:
            if len(args) != 4:
                raise MapError("ADD in SET expects: 置 result 加 left right")
            left = to_py_value(args[2])
            right = to_py_value(args[3])
            value = f"{left} + {right}"
        elif operation in ["减", "sub"]:
            if len(args) != 4:
                raise MapError("SUB in SET expects: 置 result 减 left right")
            left = to_py_value(args[2])
            right = to_py_value(args[3])
            value = f"{left} - {right}"
        elif operation in ["乘", "mul"]:
            if len(args) != 4:
                raise MapError("MUL in SET expects: 置 result 乘 left right")
            left = to_py_value(args[2])
            right = to_py_value(args[3])
            value = f"{left} * {right}"
        elif operation in ["除", "div"]:
            if len(args) != 4:
                raise MapError("DIV in SET expects: 置 result 除 left right")
            left = to_py_value(args[2])
            right = to_py_value(args[3])
            value = f"{left} / {right}"
        else:
            # Assume it's a function call: 置 变量 函数 参数...
            func = args[1]
            func_args = [to_py_value(arg) for arg in args[2:]]
            value = f"{func}({', '.join(func_args)})" if func_args else f"{func}()"
    
    return f"{name} = {value}"


def map_call(args: List[str]) -> str:
    """Map function call: 调 函数 参数..."""
    if not args:
        raise MapError("CALL expects at least a function name")
    
    func = args[0]
    call_args = [to_py_value(arg) for arg in args[1:]]
    
    return f"{func}({', '.join(call_args)})"


def map_arithmetic(args: List[str], operator: str) -> str:
    """Map arithmetic operation: 加/减/乘/除 结果 左 右"""
    if len(args) != 3:
        raise MapError(f"Arithmetic operation expects 3 arguments: result left right")
    
    result, left, right = args
    
    if not is_valid_identifier(result):
        raise MapError(f"Invalid result variable: {result}")
    
    py_left = to_py_value(left)
    py_right = to_py_value(right)
    
    return f"{result} = {py_left} {operator} {py_right}"


def build_condition(args: List[str]) -> str:
    """
    Build a Python condition from args.
    Handles: 变量 是 值, 变量 是 值 或 值2, 函数名 变量 (function call), etc.
    """
    # Remove trailing colon if present
    if args and args[-1].endswith(":"):
        args[-1] = args[-1].rstrip(":")
    
    # Check if this is a function call pattern: function_name arg1 arg2...
    # e.g. "是退出 左" should become "是退出(左)"
    if len(args) >= 2 and is_valid_identifier(args[0]) and "是" not in args and "或" not in args:
        # Looks like a function call
        func = args[0]
        call_args = [to_py_value(arg) for arg in args[1:]]
        return f"{func}({', '.join(call_args)})"
    
    condition_str = " ".join(args)
    
    # Replace Chinese operators with Python equivalents
    condition_str = condition_str.replace(" 是 ", " == ")
    condition_str = condition_str.replace(" 或 ", " or ")
    condition_str = condition_str.replace(" 且 ", " and ")
    condition_str = condition_str.replace(" 不是 ", " != ")
    
    # Convert values (but keep variables as-is)
    parts = condition_str.split()
    result_parts = []
    i = 0
    while i < len(parts):
        part = parts[i]
        if part in ["==", "!=", "or", "and", ">", "<", ">=", "<="]:
            result_parts.append(part)
        else:
            result_parts.append(to_py_value_for_condition(part))
        i += 1
    
    return " ".join(result_parts)


def to_py_value(symbol: str) -> str:
    """
    Convert a Catapillar atom to Python value.
    - Numbers remain as numbers
    - Valid identifiers remain as variables
    - True/False/None as keywords
    - Everything else as strings
    """
    if not symbol:
        return '""'
    
    # Boolean/None keywords
    if symbol in ["True", "真"]:
        return "True"
    if symbol in ["False", "假"]:
        return "False"
    if symbol == "None":
        return "None"
    
    # Numbers
    if is_numeric(symbol):
        return symbol
    
    # Known function names (don't quote these)
    if symbol in ["input", "float", "int", "str"]:
        return symbol
    
    # Variables (valid Python identifiers)
    if is_valid_identifier(symbol):
        return symbol
    
    # Strings - quote everything else
    # Handle punctuation and multi-word phrases
    return f'"{symbol}"'


def to_py_value_for_condition(symbol: str) -> str:
    """
    Convert symbol for use in conditions.
    More aggressive with string conversion for literals.
    """
    if not symbol:
        return '""'
    
    # Boolean/None keywords
    if symbol in ["True", "真"]:
        return "True"
    if symbol in ["False", "假"]:
        return "False"
    if symbol == "None":
        return "None"
    
    # Numbers
    if is_numeric(symbol):
        return symbol
    
    # Known comparison operators
    if symbol in ["==", "!=", ">", "<", ">=", "<=", "or", "and"]:
        return symbol
    
    # Variables (identifiers that don't look like literals)
    if is_valid_identifier(symbol):
        # Check if it's a common literal that should be quoted
        if symbol in ["quit", "exit"]:
            return f'"{symbol}"'
        return symbol
    
    # Everything else as string
    return f'"{symbol}"'


def is_numeric(symbol: str) -> bool:
    """Check if symbol is a number."""
    if not symbol:
        return False
    try:
        float(symbol)
        return True
    except ValueError:
        return False


def is_valid_identifier(name: str) -> bool:
    """Check if name is a valid Python identifier."""
    return name.isidentifier()
