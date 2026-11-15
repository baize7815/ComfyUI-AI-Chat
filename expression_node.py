import ast
import math
import random
import operator as op


MAX_EXPRESSION_LENGTH = 4096
MAX_AST_NODES = 128
MAX_POWER_EXPONENT = 2000
MAX_SHIFT_BITS = 100_000
MAX_INTEGER_BITS = 1_000_000


def _validate_numeric_result(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("数字表达式只能产生整数或浮点数。")
    if isinstance(value, int) and value.bit_length() > MAX_INTEGER_BITS:
        raise ValueError(f"整数结果不能超过 {MAX_INTEGER_BITS} 位二进制长度。")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("浮点结果必须是有限数值。")
    return value

# Hack: string type that is always equal in not equal comparisons
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

# Our any instance wants to be a wildcard string
any = AnyType("*")

# 数字运算符
operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.BitXor: op.xor,
    ast.USub: op.neg,
    ast.Mod: op.mod,
    ast.BitAnd: op.and_,
    ast.BitOr: op.or_,
    ast.Invert: op.invert,
    ast.And: lambda a, b: 1 if a and b else 0,
    ast.Or: lambda a, b: 1 if a or b else 0,
    ast.Not: lambda a: 0 if a else 1,
}

# 数字函数
math_functions = {
    "round": {
        "args": (1, 2),
        "call": lambda a, b = None: round(a, b),
        "hint": "number, dp? = 0"
    },
    "ceil": {
        "args": (1, 1),
        "call": lambda a: math.ceil(a),
        "hint": "number"
    },
    "floor": {
        "args": (1, 1),
        "call": lambda a: math.floor(a),
        "hint": "number"
    },
    "min": {
        "args": (2, None),
        "call": lambda *args: min(*args),
        "hint": "...numbers"
    },
    "max": {
        "args": (2, None),
        "call": lambda *args: max(*args),
        "hint": "...numbers"
    },
    "randomint": {
        "args": (2, 2),
        "call": lambda a, b: random.randint(a, b),
        "hint": "min, max"
    },
    "randomchoice": {
        "args": (2, None),
        "call": lambda *args: random.choice(args),
        "hint": "...numbers"
    },
    "sqrt": {
        "args": (1, 1),
        "call": lambda a: math.sqrt(a),
        "hint": "number"
    },
    "int": {
        "args": (1, 1),
        "call": lambda a = None: int(a),
        "hint": "number"
    },
    "iif": {
        "args": (3, 3),
        "call": lambda a, b, c = None: b if a else c,
        "hint": "value, truepart, falsepart"
    },
}

# 字符串函数
string_functions = {
    "upper": {
        "args": (1, 1),
        "call": lambda s: s.upper(),
        "hint": "string"
    },
    "lower": {
        "args": (1, 1),
        "call": lambda s: s.lower(),
        "hint": "string"
    },
    "capitalize": {
        "args": (1, 1),
        "call": lambda s: s.capitalize(),
        "hint": "string"
    },
    "title": {
        "args": (1, 1),
        "call": lambda s: s.title(),
        "hint": "string"
    },
    "strip": {
        "args": (1, 1),
        "call": lambda s: s.strip(),
        "hint": "string"
    },
    "replace": {
        "args": (3, 3),
        "call": lambda s, old, new: s.replace(old, new),
        "hint": "string, old, new"
    },
    "split": {
        "args": (1, 2),
        "call": lambda s, sep=None: s.split(sep),
        "hint": "string, separator?"
    },
    "join": {
        "args": (2, None),
        "call": lambda sep, *args: sep.join(args),
        "hint": "separator, ...strings"
    },
    "len": {
        "args": (1, 1),
        "call": lambda s: len(s),
        "hint": "string"
    },
    "concat": {
        "args": (2, None),
        "call": lambda *args: "".join(args),
        "hint": "...strings"
    },
    "substring": {
        "args": (3, 3),
        "call": lambda s, start, end: s[start:end],
        "hint": "string, start, end"
    },
    "find": {
        "args": (2, 3),
        "call": lambda s, sub, start=0: s.find(sub, start),
        "hint": "string, substring, start?"
    },
    "format": {
        "args": (2, None),
        "call": lambda fmt, *args: fmt.format(*args),
        "hint": "format, ...args"
    },
    "iif": {
        "args": (3, 3),
        "call": lambda a, b, c = None: b if a else c,
        "hint": "value, truepart, falsepart"
    },
}

# 数字函数自动完成
math_autocomplete = list({
    "text": x,
    "value": f"{x}()",
    "showValue": False,
    "hint": f"{math_functions[x]['hint']}",
    "caretOffset": -1
} for x in math_functions.keys())

# 字符串函数自动完成
string_autocomplete = list({
    "text": x,
    "value": f"{x}()",
    "showValue": False,
    "hint": f"{string_functions[x]['hint']}",
    "caretOffset": -1
} for x in string_functions.keys())

class ExpressionNode:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "表达式类型": (["数字表达式", "字符串表达式"], {"default": "数字表达式"}),
                "表达式": ("STRING", {"multiline": True, "dynamicPrompts": False, "pysssss.autocomplete": {
                    "words": math_autocomplete,
                    "separator": ""
                }}),
            },
            "optional": {
                "a": (any, ),
                "b": (any,),
                "c": (any, ),
            },
            "hidden": {"extra_pnginfo": "EXTRA_PNGINFO",
                       "prompt": "PROMPT"},
        }

    RETURN_TYPES = ("INT", "FLOAT", "STRING", )
    RETURN_NAMES = ("整数", "浮点数", "字符串", )
    FUNCTION = "evaluate"
    CATEGORY = "🫧 AI Chat"
    OUTPUT_NODE = False
    DESCRIPTION = "安全计算白名单数字或字符串表达式，并支持引用上游输入。"

    @classmethod
    def IS_CHANGED(s, 表达式类型, 表达式, **kwargs):
        if "random" in 表达式:
            return float("nan")
        return 表达式

    def get_widget_value(self, extra_pnginfo, prompt, node_name, widget_name):
        workflow = extra_pnginfo["workflow"] if "workflow" in extra_pnginfo else { "nodes": [] }
        node_id = None
        for node in workflow["nodes"]:
            name = node["type"]
            if "properties" in node:
                if "Node name for S&R" in node["properties"]:
                    name = node["properties"]["Node name for S&R"]
            if name == node_name:
                node_id = node["id"]
                break
            if "title" in node:
                name = node["title"]
            if name == node_name:
                node_id = node["id"]
                break
        if node_id is not None:
            values = prompt[str(node_id)]
            if "inputs" in values:
                if widget_name in values["inputs"]:
                    value = values["inputs"][widget_name]
                    if isinstance(value, list):
                        raise ValueError("Converted widgets are not supported via named reference, use the inputs instead.")
                    return value
            raise NameError(f"Widget not found: {node_name}.{widget_name}")
        raise NameError(f"Node not found: {node_name}.{widget_name}")

    def get_size(self, target, property):
        if isinstance(target, dict) and "samples" in target:
            # Latent
            if property == "width":
                return target["samples"].shape[3] * 8
            return target["samples"].shape[2] * 8
        else:
            # Image
            if property == "width":
                return target.shape[2]
            return target.shape[1]

    @staticmethod
    def validate_ast(node):
        nodes = list(ast.walk(node))
        if len(nodes) > MAX_AST_NODES:
            raise ValueError(f"表达式结构过于复杂，最多允许 {MAX_AST_NODES} 个语法节点。")

    @staticmethod
    def apply_compare(operator_node, left, right):
        comparisons = {
            ast.Eq: op.eq,
            ast.NotEq: op.ne,
            ast.Gt: op.gt,
            ast.GtE: op.ge,
            ast.Lt: op.lt,
            ast.LtE: op.le,
        }
        compare = comparisons.get(type(operator_node))
        if compare is None:
            raise NotImplementedError(
                "Operator " + operator_node.__class__.__name__ + " not supported."
            )
        return compare(left, right)

    @staticmethod
    def apply_binary(operator_node, left, right):
        if isinstance(operator_node, ast.Pow):
            if abs(right) > MAX_POWER_EXPONENT:
                raise ValueError(f"指数绝对值不能超过 {MAX_POWER_EXPONENT}。")
            if isinstance(left, int) and isinstance(right, int) and right >= 0:
                estimated_bits = max(1, abs(left).bit_length()) * right
                if estimated_bits > MAX_INTEGER_BITS:
                    raise ValueError(f"幂运算结果预计超过 {MAX_INTEGER_BITS} 位限制。")
            return _validate_numeric_result(op.pow(left, right))
        if isinstance(operator_node, (ast.LShift, ast.RShift)):
            if not isinstance(right, int) or right < 0 or right > MAX_SHIFT_BITS:
                raise ValueError(f"位移量必须是 0 到 {MAX_SHIFT_BITS} 之间的整数。")
            if not isinstance(left, int):
                raise TypeError("位移运算只支持整数。")
            if isinstance(operator_node, ast.LShift) and left.bit_length() + right > MAX_INTEGER_BITS:
                raise ValueError(f"位移结果不能超过 {MAX_INTEGER_BITS} 位限制。")
            result = op.lshift(left, right) if isinstance(operator_node, ast.LShift) else op.rshift(left, right)
            return _validate_numeric_result(result)
        if isinstance(operator_node, ast.Mult) and isinstance(left, int) and isinstance(right, int):
            if left.bit_length() + right.bit_length() > MAX_INTEGER_BITS + 1:
                raise ValueError(f"乘法结果预计超过 {MAX_INTEGER_BITS} 位限制。")
        function = operators.get(type(operator_node))
        if function is None:
            raise NotImplementedError(
                "Operator " + operator_node.__class__.__name__ + " not supported."
            )
        return _validate_numeric_result(function(left, right))

    def eval_math_expr(self, node, lookup, extra_pnginfo, prompt):
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise TypeError("数字表达式只允许数字常量。")
            return _validate_numeric_result(node.value)
        elif isinstance(node, ast.BinOp):
            l = self.eval_math_expr(node.left, lookup, extra_pnginfo, prompt)
            r = self.eval_math_expr(node.right, lookup, extra_pnginfo, prompt)
            l = l if isinstance(l, int) else float(l)
            r = r if isinstance(r, int) else float(r)
            return self.apply_binary(node.op, l, r)
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value_node in node.values:
                    value = self.eval_math_expr(value_node, lookup, extra_pnginfo, prompt)
                    if not value:
                        return 0
                return 1
            if isinstance(node.op, ast.Or):
                for value_node in node.values:
                    value = self.eval_math_expr(value_node, lookup, extra_pnginfo, prompt)
                    if value:
                        return 1
                return 0
            raise NotImplementedError(f"Operator {type(node.op).__name__} not supported.")
        elif isinstance(node, ast.UnaryOp):
            function = operators.get(type(node.op))
            if function is None:
                raise NotImplementedError(f"Operator {type(node.op).__name__} not supported.")
            return _validate_numeric_result(
                function(self.eval_math_expr(node.operand, lookup, extra_pnginfo, prompt))
            )
        elif isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name):
                raise TypeError("只支持 node.widget 或 image.width/height 形式的属性引用。")
            if node.value.id in lookup:
                if node.attr == "width" or node.attr == "height":
                    return self.get_size(lookup[node.value.id], node.attr)
            return self.get_widget_value(extra_pnginfo, prompt, node.value.id, node.attr)
        elif isinstance(node, ast.Name):
            if node.id in lookup:
                val = lookup[node.id]
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    return _validate_numeric_result(val)
                else:
                    raise TypeError(
                        f"Complex types (LATENT/IMAGE) need to reference their width/height, e.g. {node.id}.width")
            raise NameError(f"Name not found: {node.id}")
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise NameError("只允许调用内置白名单函数。")
            if node.func.id in math_functions:
                fn = math_functions[node.func.id]
                l = len(node.args)
                if l < fn["args"][0] or (fn["args"][1] is not None and l > fn["args"][1]):
                    if fn["args"][1] is None:
                        toErr = " or more"
                    else:
                        toErr = f" to {fn['args'][1]}"
                    raise SyntaxError(
                        f"Invalid function call: {node.func.id} requires {fn['args'][0]}{toErr} arguments")
                args = []
                for arg in node.args:
                    args.append(self.eval_math_expr(arg, lookup, extra_pnginfo, prompt))
                return _validate_numeric_result(fn["call"](*args))
            raise NameError(f"Invalid function call: {node.func.id}")
        elif isinstance(node, ast.Compare):
            left = self.eval_math_expr(node.left, lookup, extra_pnginfo, prompt)
            for operator_node, comparator_node in zip(node.ops, node.comparators):
                right = self.eval_math_expr(comparator_node, lookup, extra_pnginfo, prompt)
                if not self.apply_compare(operator_node, left, right):
                    return 0
                left = right
            return 1
        else:
            raise TypeError(node)

    def eval_string_expr(self, node, lookup, extra_pnginfo, prompt):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # 字符串连接
            left = self.eval_string_expr(node.left, lookup, extra_pnginfo, prompt)
            right = self.eval_string_expr(node.right, lookup, extra_pnginfo, prompt)
            return str(left) + str(right)
        elif isinstance(node, ast.Name):
            if node.id in lookup:
                val = lookup[node.id]
                if isinstance(val, str):
                    return val
                else:
                    # 尝试将其他类型转换为字符串
                    return str(val)
            raise NameError(f"Name not found: {node.id}")
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise NameError("只允许调用内置白名单函数。")
            if node.func.id in string_functions:
                fn = string_functions[node.func.id]
                l = len(node.args)
                if l < fn["args"][0] or (fn["args"][1] is not None and l > fn["args"][1]):
                    if fn["args"][1] is None:
                        toErr = " or more"
                    else:
                        toErr = f" to {fn['args'][1]}"
                    raise SyntaxError(
                        f"Invalid function call: {node.func.id} requires {fn['args'][0]}{toErr} arguments")
                args = []
                for arg in node.args:
                    # 尝试将参数转换为字符串
                    try:
                        arg_value = self.eval_string_expr(arg, lookup, extra_pnginfo, prompt)
                    except (TypeError, ValueError, NameError):
                        try:
                            arg_value = self.eval_math_expr(arg, lookup, extra_pnginfo, prompt)
                        except (TypeError, ValueError, NameError):
                            arg_value = str(arg)
                    args.append(arg_value)
                return fn["call"](*args)
            raise NameError(f"Invalid function call: {node.func.id}")
        elif isinstance(node, ast.Compare):
            left = self.eval_string_expr(node.left, lookup, extra_pnginfo, prompt)
            for operator_node, comparator_node in zip(node.ops, node.comparators):
                right = self.eval_string_expr(comparator_node, lookup, extra_pnginfo, prompt)
                if not self.apply_compare(operator_node, left, right):
                    return 0
                left = right
            return 1
        else:
            # 尝试将其他类型转换为字符串
            try:
                return str(self.eval_math_expr(node, lookup, extra_pnginfo, prompt))
            except (TypeError, ValueError, NameError):
                raise TypeError(f"Unsupported node type in string expression: {type(node).__name__}")

    def evaluate(self, 表达式类型, 表达式, prompt, extra_pnginfo=None, a=None, b=None, c=None):
        if extra_pnginfo is None:
            extra_pnginfo = {}
        if len(表达式) > MAX_EXPRESSION_LENGTH:
            error_msg = f"表达式计算错误: 表达式不能超过 {MAX_EXPRESSION_LENGTH} 个字符"
            return {"ui": {"value": [error_msg]}, "result": (0, 0.0, error_msg,)}
        表达式 = 表达式.replace('\n', ' ').replace('\r', '')
        lookup = {"a": a, "b": b, "c": c}

        try:
            node = ast.parse(表达式, mode='eval').body
            self.validate_ast(node)

            if 表达式类型 == "数字表达式":
                r = self.eval_math_expr(node, lookup, extra_pnginfo, prompt)
                return {"ui": {"value": [r]}, "result": (int(r), float(r), str(r),)}
            else:  # 字符串表达式
                r = self.eval_string_expr(node, lookup, extra_pnginfo, prompt)
                # 尝试将结果转换为数字
                try:
                    int_r = int(r)
                except (TypeError, ValueError):
                    int_r = 0
                try:
                    float_r = float(r)
                except (TypeError, ValueError):
                    float_r = 0.0
                return {"ui": {"value": [r]}, "result": (int_r, float_r, str(r),)}
        except Exception as e:
            error_msg = f"表达式计算错误: {str(e)}"
            return {"ui": {"value": [error_msg]}, "result": (0, 0.0, error_msg,)}


NODE_CLASS_MAPPINGS = {
    "ExpressionNode": ExpressionNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ExpressionNode": "表达式计算器",
}
