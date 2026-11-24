from uuid import uuid4
import sympy as sp
from sympy.integrals.manualintegrate import integral_steps
from sympy.calculus.util import singularities
from .models import MathRequest, MathResponse, Step
from .parser import parse, variable, InvalidExpression
from .integrals import IntegralInput, parse_integral
from .visuals import plot_data, revolution

def _step(rule, before, after, explanation, verified=None):
    return Step(number=1, rule=rule, before_latex=sp.latex(before), after_latex=sp.latex(after), explanation=explanation, verified=verified)


def _full_integral(req: MathRequest, integral: IntegralInput) -> MathResponse:
    op = "definite_integral" if integral.definite else "integrate"
    if req.operation_explicit and req.operation not in ("integrate", "definite_integral"):
        raise InvalidExpression("La expresión contiene una integral. Selecciona Integrar o Integral definida, o deja la operación automática.")
    if req.operation_explicit and req.operation in ("integrate", "definite_integral") and req.operation != op:
        raise InvalidExpression("La operación seleccionada contradice los límites escritos en la integral.")
    current = integral.integrand
    final_antiderivative = None
    steps: list[Step] = []
    warnings: list[str] = []
    all_verified = True

    def add_step(rule, before, after, explanation, verified):
        nonlocal all_verified
        steps.append(Step(number=len(steps) + 1, rule=rule, before_latex=sp.latex(before),
                          after_latex=sp.latex(after), explanation=explanation, verified=verified))
        all_verified = all_verified and verified is True

    for index, item in enumerate(reversed(integral.integrations)):
        outer = tuple(
            (part.symbol, part.lower, part.upper) if integral.definite else part.symbol
            for part in reversed(integral.integrations[:len(integral.integrations) - index - 1])
        )
        if integral.definite:
            try:
                poles = singularities(current, item.symbol)
                if isinstance(poles, sp.FiniteSet):
                    for pole in poles:
                        if pole.is_real and item.lower.is_number and item.upper.is_number:
                            inside = (pole > sp.Min(item.lower, item.upper)) & (pole < sp.Max(item.lower, item.upper))
                            if inside is sp.true:
                                return MathResponse(request_id=str(uuid4()), expression=integral.latex, operation=op,
                                                    status="unsupported", verification="unsupported",
                                                    warnings=[f"Hay una singularidad interior en {item.symbol}={pole}; esta integral requiere dividir el intervalo."])
                        if pole == item.lower or pole == item.upper:
                            warnings.append(f"Hay una singularidad en un extremo de la integral respecto a {item.symbol}; se evalúa como integral impropia.")
            except (NotImplementedError, ValueError, TypeError):
                pass
            before = sp.Integral(current, (item.symbol, item.lower, item.upper), *outer)
            stage = sp.integrate(current, (item.symbol, item.lower, item.upper))
        else:
            before = sp.Integral(current, item.symbol, *outer)
            stage = sp.integrate(current, item.symbol)
        if stage.has(sp.Integral) or stage.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
            return MathResponse(request_id=str(uuid4()), expression=integral.latex, operation=op,
                                status="unsupported", verification="unsupported",
                                warnings=[f"SymPy no obtuvo un valor finito para la integración respecto a {item.symbol}."])
        antiderivative = sp.integrate(current, item.symbol) if integral.definite else stage
        derivative_ok = None
        substitution = None
        substitution_ok = None
        if not antiderivative.has(sp.Integral):
            try:
                derivative_ok = sp.simplify(sp.diff(antiderivative, item.symbol) - current) == 0
                if integral.definite:
                    def endpoint(bound, side):
                        value = antiderivative.subs(item.symbol, bound)
                        return sp.limit(antiderivative, item.symbol, bound, dir=side) if value.has(sp.nan, sp.zoo) or bound in (sp.oo, -sp.oo) else value
                    upper_value = endpoint(item.upper, "-")
                    lower_value = endpoint(item.lower, "+")
                    substitution = sp.Add(upper_value, -lower_value, evaluate=False)
                    substitution_ok = bool(derivative_ok and sp.simplify(substitution - stage) == 0)
            except (ValueError, TypeError, NotImplementedError, RecursionError):
                pass
        if integral.definite:
            if derivative_ok is not None:
                add_step(f"Antiderivada respecto a {item.symbol}", sp.Integral(current, item.symbol),
                         antiderivative, f"Primero se integra respecto a {item.symbol}, la variable de la integral interna.", derivative_ok)
            if substitution is not None:
                substitution_with_outer = sp.Integral(substitution, *outer) if outer else substitution
                add_step("Sustitución de límites", before, substitution_with_outer,
                         f"Se evalúa la antiderivada en {sp.sstr(item.upper)} y se resta su valor en {sp.sstr(item.lower)}.",
                         substitution_ok)
                if substitution != stage:
                    simplified = sp.Integral(stage, *outer) if outer else stage
                    add_step("Simplificación", substitution_with_outer, simplified,
                             "Se simplifica el resultado antes de continuar con la integral exterior.",
                             sp.simplify(substitution - stage) == 0)
            else:
                after = sp.Integral(stage, *outer) if outer else stage
                add_step("Integración iterada", before, after,
                         f"SymPy evaluó la integral respecto a {item.symbol}; no se dispone de un desglose verificable de este paso.", None)
        else:
            after = sp.Integral(stage, *outer) if outer else stage
            explanation = f"Se obtiene una antiderivada respecto a {item.symbol}; las integraciones exteriores se conservan."
            add_step("Antiderivada iterada", before, after, explanation, derivative_ok)
        current = stage
    if not integral.definite:
        final_antiderivative = current
        with_constant = current + sp.Symbol("C")
        add_step("Constante de integración", current, with_constant,
                 "Se añade una constante porque su derivada es cero.", True)
        current = with_constant
        if len(integral.integrations) > 1:
            warnings.append("En integrales indefinidas múltiples, la constante puede depender de variables externas.")
    if integral.definite and any(item.lower.has(sp.oo) or item.upper.has(sp.oo) for item in integral.integrations):
        warnings.append("Integral impropia: se comprobaron los extremos infinitos cuando fue posible.")
    return MathResponse(request_id=str(uuid4()), expression=integral.latex, operation=op, status="solved",
                        result_latex=f"{sp.latex(final_antiderivative)} + C" if final_antiderivative is not None else sp.latex(current),
                        result_text=f"{final_antiderivative} + C" if final_antiderivative is not None else str(current), steps=steps,
                        verification="procedure_verified" if all_verified else "procedure_partial", warnings=warnings)

def solve(req: MathRequest) -> MathResponse:
    integral = parse_integral(req.latex if req.latex and r"\int" in req.latex else req.expression)
    if integral is not None:
        return _full_integral(req, integral)
    expr = parse(req.expression)
    x = variable(req.variable)
    op = req.operation
    steps = []
    warnings = []
    plot = solid = None
    verification = "unverified"
    result = None
    if op in ("simplify", "expand", "factor"):
        if isinstance(expr, sp.Equality): raise InvalidExpression("Esta operación requiere una expresión, no una ecuación")
        result = {"simplify": sp.simplify, "expand": sp.expand, "factor": sp.factor}[op](expr)
        difference = sp.simplify(sp.together(expr-result))
        verified = difference == 0
        rule = {"simplify":"Simplificación algebraica", "expand":"Propiedad distributiva", "factor":"Factorización"}[op]
        steps = [_step(rule, expr, result, "SymPy transforma la expresión conservando su valor donde ambas expresiones están definidas.", verified)] if expr != result else []
        if sp.denom(sp.together(expr)) != 1 or sp.denom(sp.together(result)) != 1:
            warnings.append("La equivalencia se interpreta en el dominio común; revisa denominadores y puntos excluidos.")
        verification = "procedure_verified" if verified and steps else "result_verified" if verified else "unverified"
    elif op == "solve":
        eq = expr if isinstance(expr, sp.Equality) else sp.Eq(expr, 0)
        candidates = sp.solve(eq, x)
        valid = []
        for candidate in candidates:
            try:
                lhs, rhs = eq.lhs.subs(x, candidate), eq.rhs.subs(x, candidate)
                if candidate.is_real and sp.simplify(lhs-rhs) == 0 and lhs.is_finite and rhs.is_finite: valid.append(candidate)
            except Exception: pass
        result = sp.FiniteSet(*valid)
        verification = "result_verified" if valid and len(valid) == len(candidates) else "unverified"
        if not valid:
            try:
                if sp.solveset(eq, x, domain=sp.S.Reals) == sp.S.EmptySet: verification = "result_verified"
            except Exception: pass
        try:
            polynomial = sp.Poly(eq.lhs-eq.rhs, x)
            if polynomial.degree() == 1 and valid:
                a, b = polynomial.all_coeffs()
                transformed = sp.Eq(x, -b/a, evaluate=False)
                steps = [_step("Despeje de ecuación lineal", eq, transformed,
                               "Se agrupan los términos y se divide entre el coeficiente no nulo de la variable.",
                               sp.simplify(eq.lhs.subs(x, -b/a)-eq.rhs.subs(x, -b/a)) == 0)]
                if steps[0].verified: verification = "procedure_verified"
        except sp.PolynomialError: pass
        if len(valid) != len(candidates): warnings.append("Algunas soluciones candidatas no pudieron verificarse o están fuera del dominio.")
        if not valid: warnings.append("No se encontraron soluciones verificadas para la variable indicada.")
    elif op == "system":
        equations = [expr, parse(req.second_expression or "")]
        equations = [e if isinstance(e, sp.Equality) else sp.Eq(e, 0) for e in equations]
        solutions = sp.solve(equations, (variable("x"), variable("y")), dict=True)
        if any(variable("x") not in s or variable("y") not in s for s in solutions):
            return MathResponse(request_id=str(uuid4()), expression=req.expression, operation=op, status="unsupported",
                                verification="unsupported", warnings=["El sistema tiene soluciones paramétricas; esta vista requiere una solución aislada en x e y."])
        result = sp.FiniteSet(*[sp.Tuple(s.get(variable("x")), s.get(variable("y"))) for s in solutions])
        verification = "result_verified" if solutions and all(all(sp.simplify(eq.lhs.subs(s)-eq.rhs.subs(s)) == 0 for eq in equations) for s in solutions) else "unverified"
    elif op == "limit":
        if req.point is None: raise InvalidExpression("Indica el punto del límite")
        result = sp.limit(expr, x, parse(req.point), dir=req.direction)
        verification = "procedure_unavailable"
    elif op == "differentiate":
        result = sp.diff(expr, x, req.order)
        verified = sp.simplify(result - sp.Derivative(expr, (x, req.order)).doit()) == 0
        if expr.is_Pow and expr.base == x and expr.exp.is_number and req.order == 1:
            steps = [_step("Regla de la potencia", sp.Derivative(expr, x), result,
                           "Para x elevado a n, la derivada es n por x elevado a n menos uno.", verified)]
            verification = "procedure_verified" if verified else "unverified"
        else:
            steps = [_step("Derivación simbólica", sp.Derivative(expr, (x, req.order)), result,
                           "La derivada obtenida se calcula con SymPy; no se dispone del desglose de reglas para esta expresión.", verified)]
            verification = "procedure_partial" if verified else "unverified"
    elif op in ("integrate", "definite_integral"):
        if op == "integrate":
            result = sp.integrate(expr, x)
            if isinstance(result, sp.Integral): return MathResponse(request_id=str(uuid4()), expression=req.expression, operation=op, status="unsupported", verification="unsupported", warnings=["SymPy no obtuvo una antiderivada cerrada."])
            verified = sp.simplify(sp.diff(result, x)-expr) == 0
            rule = integral_steps(expr, x)
            known = {"PowerRule": ("Regla de la potencia", "Se aumenta el exponente en uno y se divide entre el nuevo exponente."),
                     "SinRule": ("Integral del seno", "La antiderivada de seno es menos coseno."),
                     "CosRule": ("Integral del coseno", "La antiderivada de coseno es seno."),
                     "ExpRule": ("Integral exponencial", "La antiderivada de la exponencial natural es ella misma."),
                     "ReciprocalRule": ("Integral logarítmica", "La antiderivada de uno sobre x es logaritmo del valor absoluto de x.")}
            name = type(rule).__name__
            label, explanation = known.get(name, ("Antiderivada", "La derivada del resultado reproduce el integrando; el método detallado no está disponible."))
            steps = [_step(label, sp.Integral(expr, x), result, explanation, verified)]
            verification = "procedure_verified" if verified and name in known else "procedure_partial" if verified else "unverified"
            if name not in known: warnings.append("Se muestra la comprobación de la antiderivada, sin desglose completo del método.")
        else:
            if req.lower is None or req.upper is None: raise InvalidExpression("Indica los dos límites de integración")
            lo, hi = parse(req.lower), parse(req.upper)
            result = sp.integrate(expr, (x, lo, hi))
            if result.has(sp.Integral): return MathResponse(request_id=str(uuid4()), expression=req.expression, operation=op, status="unsupported", verification="unsupported", warnings=["No se pudo evaluar la integral definida."])
            verification = "procedure_unavailable"
            warnings.append("El valor fue calculado por SymPy; no se verificó automáticamente la convergencia en todos los puntos singulares.")
    elif op == "plot":
        second = parse(req.second_expression) if req.second_expression else None
        plot = plot_data([e for e in (expr, second) if e is not None], x)
        result = expr
        verification = "procedure_unavailable"
    elif op == "revolution":
        if req.lower is None or req.upper is None: raise InvalidExpression("Indica el intervalo")
        second = parse(req.second_expression or "0")
        solid = revolution(expr, second, x, parse(req.lower), parse(req.upper), req.axis, parse(req.axis_value))
        verification = "result_verified"
    else: raise InvalidExpression("Operación no soportada")
    return MathResponse(request_id=str(uuid4()), expression=req.expression, operation=op, status="solved",
                        result_latex=solid["volume_latex"] if solid else sp.latex(result),
                        result_text=solid["volume_text"] if solid else str(result), steps=steps,
                        verification=verification, warnings=warnings, plot=plot, solid=solid)
