"""Provide numerical arithmetic to agents through a native toolset.

Input origin:
    Tool-call arguments selected by a model using the calculator schema.
Output destination:
    Computed numbers returned to the calling agent's message history.
Responsibilities:
    Own arithmetic implementation, usage guidance, and invocation logs.
"""

from collections.abc import Mapping
from time import monotonic
import ast
import operator

from pydantic_ai import FunctionToolset
from logger import get_logger, trace_call


@trace_call("tool", "calculate")
def calculate(expression: str) -> float | int:
    """Evaluate basic numerical arithmetic without executing Python code.

    Args:
        expression: Numeric expression using +, -, *, /, //, %, and parentheses.

    Returns:
        The computed number.
    """
    logger = get_logger("plugins.tools.calculator.local")
    started = monotonic()
    logger.info("kind=script provider=local tool=calculate Tool started.")
    try:
        if len(expression) > 200:
            raise ValueError("Arithmetic expression is too large")
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 100:
            raise ValueError("Arithmetic expression is too large")
        value = _evaluate(tree.body)
    except Exception:
        logger.exception("kind=script provider=local tool=calculate Tool failed: elapsed=%.2fs.",
                         monotonic() - started)
        raise
    logger.info("kind=script provider=local tool=calculate Tool completed: elapsed=%.2fs.",
                monotonic() - started)
    return value


def _evaluate(node: ast.AST) -> float | int:
    """Evaluate only numeric constants and supported arithmetic operators.

    Args:
        node: Expression node produced by the arithmetic parser.

    Returns:
        The numeric result for this subtree.
    """
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
    }
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        value = node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in operations:
        operation = operations[type(node.op)]
        value = operation(_evaluate(node.left), _evaluate(node.right))
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _evaluate(node.operand)
        value = -operand if isinstance(node.op, ast.USub) else operand
    else:
        raise ValueError("Only basic numerical arithmetic is supported")
    return value


def create_toolset(options: Mapping[str, object]) -> FunctionToolset:
    """Build arithmetic tools with their usage guidance.

    Args:
        options: Plugin options; the calculator currently needs no settings.

    Returns:
        A fresh PydanticAI toolset owned by the calling agent.
    """
    toolset = FunctionToolset(tools=[calculate], instructions="Use calculate for numerical arithmetic.")
    return toolset
