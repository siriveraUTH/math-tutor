"""Lectura acotada de integrales LaTeX producidas por MathLive.

Solo se reconocen comandos matemáticos explícitamente permitidos. La gramática
algebraica existente construye finalmente los objetos SymPy.
"""
from dataclasses import dataclass

import sympy as sp

from .parser import InvalidExpression, SYMBOLS, parse, variable


@dataclass(frozen=True)
class Integration:
    symbol: sp.Symbol
    lower: sp.Expr | None = None
    upper: sp.Expr | None = None


@dataclass(frozen=True)
class IntegralInput:
    integrand: sp.Expr
    integrations: tuple[Integration, ...]  # De la integral exterior a la interior.
    latex: str

    @property
    def definite(self) -> bool:
        return self.integrations[0].lower is not None

    @property
    def sympy_limits(self):
        return tuple(
            (item.symbol, item.lower, item.upper) if self.definite else item.symbol
            for item in reversed(self.integrations)
        )


SPACING = (r"\,", r"\;", r"\!", r"\:", r"\quad", r"\qquad", r"\ ")
FUNCTIONS = {"sin": "sin", "cos": "cos", "tan": "tan", "arcsin": "asin",
             "arccos": "acos", "arctan": "atan", "ln": "ln", "log": "log",
             "sinh": "sinh", "cosh": "cosh", "exp": "exp"}


def _skip_space(text: str, pos: int) -> int:
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        spacing = next((item for item in SPACING if text.startswith(item, pos)), None)
        if spacing:
            pos += len(spacing)
            continue
        break
    return pos


def _group(text: str, pos: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    if pos >= len(text) or text[pos] != opening:
        raise InvalidExpression("Falta un grupo matemático entre llaves.")
    depth = 0
    for end in range(pos, len(text)):
        if text[end] == opening:
            depth += 1
        elif text[end] == closing:
            depth -= 1
            if depth == 0:
                return text[pos + 1:end], end + 1
    raise InvalidExpression("Hay un límite o integrando incompleto: falta cerrar una llave.")


def _bound(text: str, pos: int) -> tuple[str, int]:
    pos = _skip_space(text, pos)
    if pos >= len(text):
        raise InvalidExpression("Falta un límite de integración.")
    if text[pos] == "{":
        return _group(text, pos)
    start = pos
    if text[pos] in "+-":
        pos += 1
    if text.startswith(r"\frac", pos):
        pos += 5
        _, pos = _group(text, pos)
        _, pos = _group(text, pos)
        return text[start:pos], pos
    if text[pos:pos + 1] == "\\":
        pos += 1
        while pos < len(text) and text[pos].isalpha():
            pos += 1
        return text[start:pos], pos
    if pos < len(text) and text[pos].isdigit():
        while pos < len(text) and (text[pos].isdigit() or text[pos] == "."):
            pos += 1
        return text[start:pos], pos
    if pos < len(text) and text[pos].isalpha():
        return text[start:pos + 1], pos + 1
    raise InvalidExpression("No se pudo leer un límite de integración.")


def _to_ascii(text: str, level: int = 0) -> str:
    """Convierte un subconjunto controlado de LaTeX a la gramática algebraica."""
    if level > 24:
        raise InvalidExpression("La integral tiene demasiados niveles de agrupación.")
    parts: list[str] = []
    previous = ""

    def emit(value: str, kind: str = "factor"):
        nonlocal previous
        if previous == "factor" and kind == "factor":
            parts.append("*")
        parts.append(value)
        previous = kind

    pos = 0
    while pos < len(text):
        pos = _skip_space(text, pos)
        if pos >= len(text):
            break
        char = text[pos]
        if char == "{":
            content, pos = _group(text, pos)
            emit(f"({_to_ascii(content, level + 1)})")
            continue
        if char == "\\":
            start = pos + 1
            pos = start
            while pos < len(text) and text[pos].isalpha():
                pos += 1
            command = text[start:pos]
            if not command:
                raise InvalidExpression("Comando LaTeX incompleto.")
            if command in ("left", "right", "limits", "nolimits", "displaystyle"):
                continue
            if command in ("cdot", "times"):
                emit("*", "operator")
                continue
            if command == "frac":
                numerator, pos = _group(text, _skip_space(text, pos))
                denominator, pos = _group(text, _skip_space(text, pos))
                emit(f"(({_to_ascii(numerator, level + 1)})/({_to_ascii(denominator, level + 1)}))")
                continue
            if command == "sqrt":
                pos = _skip_space(text, pos)
                index = None
                if pos < len(text) and text[pos] == "[":
                    index, pos = _group(text, pos, "[", "]")
                radicand, pos = _group(text, _skip_space(text, pos))
                value = f"sqrt({_to_ascii(radicand, level + 1)})" if index is None else f"(({_to_ascii(radicand, level + 1)})^(1/({_to_ascii(index, level + 1)})))"
                emit(value)
                continue
            if command in ("mathrm", "operatorname"):
                content, pos = _group(text, _skip_space(text, pos))
                if content == "e":
                    emit("e")
                    continue
                raise InvalidExpression(f"Notación LaTeX no admitida: {content}")
            if command in ("infty", "infinity"):
                emit("oo")
                continue
            if command == "pi":
                emit("pi")
                continue
            if command in FUNCTIONS:
                name = FUNCTIONS[command]
                next_pos = _skip_space(text, pos)
                exponent = None
                if next_pos < len(text) and text[next_pos] == "^":
                    power, next_pos = _bound(text, next_pos + 1)
                    exponent = _to_ascii(power, level + 1)
                    if exponent in ("-1", "(-1)") and command in ("sin", "cos", "tan"):
                        raise InvalidExpression(f"Para la función trigonométrica inversa usa \\arc{command}(x), no \\{command}^{{-1}}(x).")
                    next_pos = _skip_space(text, next_pos)
                if text.startswith(r"\left", next_pos):
                    next_pos += 5
                if next_pos < len(text) and text[next_pos] == "(":
                    argument, pos = _group(text, next_pos, "(", ")")
                    argument = _to_ascii(argument, level + 1)
                elif next_pos < len(text) and text[next_pos] == "{":
                    argument, pos = _group(text, next_pos)
                    argument = _to_ascii(argument, level + 1)
                elif next_pos < len(text) and text[next_pos] in SYMBOLS:
                    argument = text[next_pos]
                    pos = next_pos + 1
                else:
                    raise InvalidExpression(f"Falta el argumento de {command}.")
                function = f"{name}({argument})"
                emit(f"({function})^({exponent})" if exponent is not None else function)
                continue
            raise InvalidExpression(f"Comando LaTeX no admitido: \\{command}")
        if char in "()":
            if char == "(":
                emit("(", "open")
            else:
                parts.append(")")
                previous = "factor"
            pos += 1
            continue
        if char in "+-*/^":
            emit(char, "operator")
            pos += 1
            continue
        if char.isdigit() or char == ".":
            start = pos
            while pos < len(text) and (text[pos].isdigit() or text[pos] == "."):
                pos += 1
            emit(text[start:pos])
            continue
        if char in SYMBOLS or char == "e":
            emit(char)
            pos += 1
            continue
        raise InvalidExpression(f"Símbolo no admitido en la integral: {char}")
    result = "".join(parts)
    if not result or "placeholder" in text:
        raise InvalidExpression("Completa todos los campos de la integral antes de resolver.")
    return result


def _differentials(text: str) -> tuple[str, list[str]]:
    positions: list[tuple[int, int, str]] = []
    depth = 0
    pos = 0
    while pos < len(text):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth < 0:
                raise InvalidExpression("Hay una llave sobrante en la integral.")
        if depth == 0:
            start = pos
            # MathLive también puede agrupar las dos letras del diferencial
            # en un único comando de estilo: \mathrm{dy}, por ejemplo.
            packed = False
            for command in (r"\mathrm", r"\operatorname", r"\text"):
                if text.startswith(command + "{", pos):
                    content, end = _group(text, pos + len(command))
                    if len(content) == 2 and content[0] == "d" and content[1] in SYMBOLS:
                        positions.append((start, end, content[1]))
                        pos = end
                        packed = True
                    break
            if packed:
                continue
            if text.startswith(r"\mathrm{d}", pos):
                pos += len(r"\mathrm{d}")
            elif text.startswith(r"\operatorname{d}", pos):
                pos += len(r"\operatorname{d}")
            elif text[pos] == "d":
                pos += 1
            else:
                pos += 1
                continue
            pos = _skip_space(text, pos)
            if pos < len(text) and text[pos] in SYMBOLS and (pos + 1 == len(text) or not text[pos + 1].isalpha()):
                positions.append((start, pos + 1, text[pos]))
                pos += 1
                continue
            pos = start + 1
            continue
        pos += 1
    if depth:
        raise InvalidExpression("Hay un grupo matemático sin cerrar en la integral.")
    if not positions:
        raise InvalidExpression("Falta el diferencial, por ejemplo dx o dy.")
    # MathLive puede conservar una multiplicación explícita entre los diferenciales.
    # Solo se admite en el sufijo de integración; el resto sigue pasando por el parser seguro.
    def skip_separator(pos: int) -> int:
        pos = _skip_space(text, pos)
        while text.startswith(r"\cdot", pos):
            pos = _skip_space(text, pos + len(r"\cdot"))
        return pos

    # Leer el sufijo desde el final evita confundir un producto como «dx + ...»
    # dentro del integrando con el primer diferencial de la integral.
    last = next((index for index in range(len(positions) - 1, -1, -1)
                 if _skip_space(text, positions[index][1]) == len(text)), None)
    if last is None:
        raise InvalidExpression("Los diferenciales deben aparecer al final de la integral.")
    first = last
    while first > 0 and skip_separator(positions[first - 1][1]) == positions[first][0]:
        first -= 1
    return text[:positions[first][0]], [item[2] for item in positions[first:last + 1]]


def parse_integral(text: str) -> IntegralInput | None:
    """Devuelve None si no comienza con una integral completa."""
    if len(text) > 600:
        raise InvalidExpression("La integral es demasiado larga.")
    pos = _skip_space(text, 0)
    if not text.startswith(r"\int", pos):
        if r"\int" in text:
            raise InvalidExpression("Escribe la integral completa al inicio de la expresión.")
        return None
    raw_bounds: list[tuple[str | None, str | None]] = []
    while text.startswith(r"\int", pos):
        pos += 4
        pos = _skip_space(text, pos)
        if text.startswith(r"\limits", pos):
            pos = _skip_space(text, pos + 7)
        bounds: dict[str, str] = {}
        while pos < len(text) and text[pos] in "_^":
            marker = text[pos]
            if marker in bounds:
                raise InvalidExpression("La integral repite un límite.")
            bounds[marker], pos = _bound(text, pos + 1)
            pos = _skip_space(text, pos)
        if bool(bounds.get("_")) != bool(bounds.get("^")):
            raise InvalidExpression("Una integral definida necesita límite inferior y superior.")
        raw_bounds.append((bounds.get("_"), bounds.get("^")))
        if len(raw_bounds) > 3:
            raise InvalidExpression("Se admiten como máximo tres integraciones iteradas.")
    integrand_text, differential_names = _differentials(text[pos:])
    if len(differential_names) != len(raw_bounds):
        raise InvalidExpression("Cada integral necesita exactamente un diferencial, en orden de adentro hacia afuera.")
    if len(set(differential_names)) != len(differential_names):
        raise InvalidExpression("No repitas una variable de integración en la misma integral iterada.")
    if any((lo is None) != (raw_bounds[0][0] is None) for lo, _ in raw_bounds):
        raise InvalidExpression("No se admiten integrales iteradas que mezclen límites definidos e indefinidos.")
    integrand = parse(_to_ascii(integrand_text))
    if isinstance(integrand, sp.Equality):
        raise InvalidExpression("El integrando debe ser una expresión, no una ecuación.")
    items = []
    for (lower, upper), name in zip(raw_bounds, reversed(differential_names)):
        items.append(Integration(variable(name), parse(_to_ascii(lower)) if lower is not None else None,
                                 parse(_to_ascii(upper)) if upper is not None else None))
    for index, item in enumerate(items):
        for bound in (item.lower, item.upper):
            if bound is not None and bound.free_symbols.intersection({other.symbol for other in items[index:]}):
                raise InvalidExpression("Un límite no puede depender de su propia variable ni de una variable más interna.")
    return IntegralInput(integrand, tuple(items), text)
