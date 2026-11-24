"""Small expression grammar. No Python evaluation or SymPy string parsing."""
from lark import Lark, Transformer
from lark.exceptions import VisitError
import re
import sympy as sp

GRAMMAR = r"""
?start: equation
?equation: sum "=" sum -> equation
         | sum
?sum: sum "+" product -> add
    | sum "-" product -> sub
    | product
?product: product "*" unary -> mul
        | product "/" unary -> div
        | unary
?unary: "-" unary -> neg
      | "+" unary -> pos
      | power
?power: atom "^" unary -> pow
      | atom
?atom: NUMBER -> number
     | NAME "(" sum ")" -> function
     | NAME -> symbol
     | "(" sum ")"
NUMBER: /(?:\d+(?:\.\d*)?|\.\d+)/
NAME: /[a-zA-Z_][a-zA-Z_0-9]*/
%import common.WS
%ignore WS
"""
PARSER = Lark(GRAMMAR, parser="lalr")
SYMBOLS = {name: sp.Symbol(name, real=True) for name in ("x", "y", "z", "t", "u", "v", "a", "b", "c", "n")}
FUNCTIONS = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "asin": sp.asin, "acos": sp.acos,
             "atan": sp.atan, "sinh": sp.sinh, "cosh": sp.cosh, "exp": sp.exp,
             "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs}
CONSTANTS = {"pi": sp.pi, "e": sp.E, "E": sp.E, "oo": sp.oo}


class InvalidExpression(ValueError):
    pass


class Build(Transformer):
    def number(self, args): return sp.Rational(str(args[0]))
    def symbol(self, args):
        name = str(args[0])
        if name in CONSTANTS: return CONSTANTS[name]
        if name not in SYMBOLS: raise InvalidExpression(f"Símbolo no permitido: {name}")
        return SYMBOLS[name]
    def function(self, args):
        name = str(args[0])
        if name not in FUNCTIONS: raise InvalidExpression(f"Función no permitida: {name}")
        return FUNCTIONS[name](args[1], evaluate=False)
    def add(self, a): return sp.Add(a[0], a[1], evaluate=False)
    def sub(self, a): return sp.Add(a[0], -a[1], evaluate=False)
    def mul(self, a): return sp.Mul(a[0], a[1], evaluate=False)
    def div(self, a):
        if a[1] == 0: raise InvalidExpression("No se puede dividir entre cero")
        return sp.Mul(a[0], sp.Pow(a[1], -1, evaluate=False), evaluate=False)
    def pow(self, a):
        if a[1].is_number and (abs(float(a[1])) > 100 or a[1].is_Integer and abs(int(a[1])) > 100):
            raise InvalidExpression("Exponente demasiado grande")
        return sp.Pow(a[0], a[1], evaluate=False)
    def neg(self, a): return -a[0]
    def pos(self, a): return a[0]
    def equation(self, a): return sp.Eq(a[0], a[1], evaluate=False)


def parse(text: str):
    if not text or len(text) > 300: raise InvalidExpression("La expresión debe tener entre 1 y 300 caracteres")
    if sum(c in "()+-*/^=" for c in text) > 120: raise InvalidExpression("Expresión demasiado compleja")
    try:
        text = re.sub(r"(\d|\))(?=[a-zA-Z(])", r"\1*", text)
        text = re.sub(r"([xyztuvabcn])(?=\d)", r"\1*", text)
        text = re.sub(r"\)(?=\d)", ")*", text)
        tree = PARSER.parse(text)
        if len(list(tree.iter_subtrees())) > 200: raise InvalidExpression("Expresión demasiado compleja")
        value = Build().transform(tree)
        if isinstance(value, sp.Basic) and sp.count_ops(value) > 150: raise InvalidExpression("Expresión demasiado compleja")
        return value
    except InvalidExpression: raise
    except VisitError as exc:
        if isinstance(exc.orig_exc, InvalidExpression): raise exc.orig_exc
        raise InvalidExpression("La expresión contiene una operación inválida") from exc
    except Exception as exc: raise InvalidExpression("No se pudo interpretar la expresión. Usa * para multiplicar y paréntesis para agrupar.") from exc


def variable(name: str):
    if name not in SYMBOLS: raise InvalidExpression("Variable no permitida")
    return SYMBOLS[name]
