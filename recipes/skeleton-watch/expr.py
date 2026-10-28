#!/usr/bin/env python3
"""expr — evaluate the arithmetic a RemoteCompose document carries, safely.

The checkers in this folder read documents rather than trusting the code that wrote them,
which means they have to evaluate the expressions those documents contain. This is that
evaluator: a whitelist of node types and a whitelist of functions, so a document cannot
smuggle anything executable past a checker that reads it.

It understands the subset these documents use — arithmetic, the named functions below,
`t` as the clock, and any variables handed to it. `a[0]`, the sweep parameter of a
pathExpression, is substituted textually by the caller before it gets here.
"""

import ast
import math

class Fail(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise Fail(msg)


# ── document access ──────────────────────────────────────────────────────────

def canvas(doc):
    for child in doc["root"][0]["box"]["children"]:
        if child.get("type") == "canvas":
            return child
    raise Fail("no canvas in the document")


def variables(doc):
    """Named values, including touch inputs resolved to their resting defaults.

    A touch value is a variable like any other to an expression that reads it; with no
    finger on the screen it sits at its defaultValue, which is the state a static check
    should reason about.
    """
    out = {}
    for c in canvas(doc)["commands"]:
        if "variable" in c:
            out[c["variable"]["name"]] = str(c["variable"]["value"])
        elif "touchExpression" in c:
            te = c["touchExpression"]
            out[te["name"]] = str(te.get("defaultValue", 0.0))
    return out


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Call)

# The only callables a document expression may use here. A whitelist, not a sandbox
# escape hatch: anything not named is a hard failure, so a document cannot get arbitrary
# code past a checker that reads it.
_FUNCS = {
    "cos": math.cos, "sin": math.sin, "tan": math.tan, "sqrt": math.sqrt,
    "abs": abs, "floor": math.floor, "exp": math.exp, "log": math.log,
    "min": min, "max": max,
    "fract": lambda v: v - math.floor(v),
}


def evaluate(expr, vars_, t, depth=0):
    """Evaluate one of the simple arithmetic expressions these documents emit.

    Deliberately not `eval` on the raw string: the node types are whitelisted, so a
    document cannot smuggle anything executable past a checker that reads it.
    """
    check(depth < 12, "variable reference nests too deeply: %r" % expr)
    if isinstance(expr, (int, float)):
        return float(expr)
    e = str(expr).strip().replace("@", "")
    tree = ast.parse(e, mode="eval")
    for node in ast.walk(tree):
        check(isinstance(node, _ALLOWED),
              "expression %r contains %s, which this checker will not evaluate"
              % (e, type(node).__name__))

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id == "t":
                return t
            check(node.id in vars_, "unknown variable %r" % node.id)
            return evaluate(vars_[node.id], vars_, t, depth + 1)
        if isinstance(node, ast.Call):
            check(isinstance(node.func, ast.Name) and node.func.id in _FUNCS,
                  "expression calls %r, which is not on the permitted list"
                  % getattr(node.func, "id", node.func))
            return float(_FUNCS[node.func.id](*[ev(a) for a in node.args]))
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        a, b = ev(node.left), ev(node.right)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        return a / b

    return ev(tree)


