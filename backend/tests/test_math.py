import sympy as sp
import pytest
import asyncio
import httpx
from app.main import app
from app.parser import parse, variable, InvalidExpression
from app.integrals import parse_integral
from app.solver import solve
from app.models import MathRequest

def calc(expression, operation, **kwargs):
    return solve(MathRequest(expression=expression, operation=operation, **kwargs))

@pytest.mark.parametrize("expression,operation,expected", [
    ("(x+1)^2", "expand", "x**2 + 2*x + 1"),
    ("x^2-1", "factor", "(x - 1)*(x + 1)"),
    ("x^2+2*x+1", "simplify", "x**2 + 2*x + 1"),
    ("x^2", "differentiate", "2*x"),
    ("x^2", "integrate", "x**3/3"),
])
def test_symbolic(expression, operation, expected):
    result = calc(expression, operation)
    assert sp.simplify(sp.sympify(result.result_text) - sp.sympify(expected)) == 0

def test_equation_and_domain():
    result = calc("(x^2-1)/(x-1)=0", "solve")
    assert result.result_text == "{-1}"
    assert result.verification == "result_verified"

def test_limit_and_definite_integral():
    assert calc("sin(x)/x", "limit", point="0").result_text == "1"
    assert calc("x", "definite_integral", lower="0", upper="1").result_text == "1/2"

def test_plot_and_solid():
    graph = calc("1/x", "plot")
    assert len(graph.plot["traces"][0]["x"]) == 401
    assert None in graph.plot["traces"][0]["y"]
    solid = calc("x", "revolution", lower="0", upper="1")
    assert sp.simplify(sp.sympify(solid.result_text)-sp.pi/3) == 0
    washer = calc("x+1", "revolution", lower="0", upper="1", second_expression="1")
    assert washer.solid["secondary_mesh"] is not None
    assert sp.simplify(sp.sympify(washer.result_text)-4*sp.pi/3) == 0
    vertical = calc("x", "revolution", lower="0", upper="1", axis="y")
    assert sp.simplify(sp.sympify(vertical.result_text)-2*sp.pi/3) == 0
    assert vertical.solid["secondary_mesh"] is not None

def test_system_and_steps():
    system = calc("x+y=2", "system", second_expression="x-y=0")
    assert system.result_text == "{(1, 1)}"
    linear = calc("2*x+4=0", "solve")
    assert linear.result_text == "{-2}"
    assert linear.steps[0].verified is True
    integral = calc("x^2", "integrate")
    assert integral.verification == "procedure_verified"
    assert calc("x+y=2", "system", second_expression="2*x+2*y=4").status == "unsupported"
    assert calc("x^2+1=0", "solve").result_text == "EmptySet"

def test_revolution_rejects_crossing():
    with pytest.raises(InvalidExpression): calc("x-1/2", "revolution", lower="0", upper="1")

def test_parser_rejects_code_and_large_power():
    with pytest.raises(InvalidExpression): parse("__import__(x)")
    with pytest.raises(InvalidExpression): parse("x^999999")
    with pytest.raises(InvalidExpression): parse("1/0")
    assert parse("-x^2") == -sp.Symbol("x", real=True)**2

def test_api():
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/health")).json()["status"] == "ok"
            response = await client.post("/api/solve", json={"expression":"x^2", "operation":"differentiate"})
            assert response.status_code == 200
            assert response.json()["result_text"] == "2*x"
            triple = await client.post("/api/solve", json={"expression":r"\int_0^1\int_0^2\int_0^3 xyz\,dz\,dy\,dx", "operation":"simplify"})
            assert triple.status_code == 200
            assert triple.json()["result_text"] == "9/2"
            trig = await client.post("/api/solve", json={
                "expression": "int cos^4(x) sin^3(x) dx",
                "latex": r"\int\cos^{4}\left(x\right)\sin^{3}\left(x\right)\,dx",
                "operation": "integrate",
            })
            assert trig.status_code == 200
            assert trig.json()["result_text"] == "cos(x)**7/7 - cos(x)**5/5 + C"
            invalid = await client.post("/api/solve", json={"expression":r"\int_0^1 x", "operation":"integrate"})
            assert invalid.status_code == 422
    asyncio.run(check())


@pytest.mark.parametrize("expression,expected", [
    (r"\int x^2\,dx", "x**3/3"),
    (r"\int_0^2 x^2\,dx", "8/3"),
    (r"\int_0^2\int_0^3 xy\,dy\,dx", "9"),
    (r"\int_0^1\int_0^2\int_0^3 xyz\,dz\,dy\,dx", "9/2"),
    (r"\int_0^1\int_0^x (x+y)\,dy\,dx", "1/2"),
    (r"\int_0^2\int_1^3\left(2x+3y\right)\,\mathrm{d}y\,\mathrm{d}x", "32"),
    (r"\int_0^2\int_1^3(2x+3y)\,dy\cdot dx", "32"),
    (r"\int_0^2\int_1^3(2x+3y)\mathrm{dy}\mathrm{dx}", "32"),
    (r"\int_0^2\int_1^3(2x+3y)\operatorname{dy}\operatorname{dx}", "32"),
    (r"\int_0^2\int_1^3(2x+3y)\text{dy}\text{dx}", "32"),
])
def test_complete_integrals(expression, expected):
    result = calc(expression, "simplify")
    assert result.status == "solved"
    assert result.verification == "procedure_verified"
    assert all(step.verified is True for step in result.steps)
    assert sp.simplify(sp.sympify(result.result_text).subs("C", 0) - sp.sympify(expected)) == 0
    assert len(result.steps) >= len(parse_integral(expression).integrations)


def test_integral_structure_and_order():
    assert calc(r"\int x^2\,dx", "integrate").result_text == "x**3/3 + C"
    integral = parse_integral(r"\int_0^1\int_0^x (x+y)\,dy\,dx")
    assert [str(item.symbol) for item in integral.integrations] == ["x", "y"]
    assert [str(limit[0]) for limit in integral.sympy_limits] == ["y", "x"]
    assert integral.integrations[1].upper == parse("x")


@pytest.mark.parametrize("expression", [
    r"\int\cos^{4}\left(x\right)\sin^{3}\left(x\right)\,dx",
    r"\int\cos^4(x)\sin(x)^3\,dx",
    r"\int\cos^4 x\sin^3 x\,dx",
])
def test_trigonometric_powers_in_complete_integrals(expression):
    integral = parse_integral(expression)
    x = variable("x")
    assert sp.simplify(integral.integrand - sp.cos(x)**4 * sp.sin(x)**3) == 0
    result = calc(expression, "integrate")
    assert result.status == "solved"
    assert result.verification == "procedure_verified"
    antiderivative = sp.cos(x)**7 / 7 - sp.cos(x)**5 / 5
    assert sp.simplify(sp.diff(antiderivative, x) - integral.integrand) == 0
    assert result.result_text == f"{antiderivative} + C"


def test_inverse_trig_power_requires_explicit_inverse_function():
    with pytest.raises(InvalidExpression, match="inversa"):
        parse_integral(r"\int\sin^{-1}(x)\,dx")


def test_improper_and_symbolic_integrals():
    assert calc(r"\int_0^{\infty}\frac{1}{1+x^2}\,dx", "integrate").result_text == "pi/2"
    assert calc(r"\int_{-\frac{1}{2}}^{\frac{1}{2}} x^2\,dx", "integrate").result_text == "1/12"
    symbolic = calc(r"\int_0^a x\,dx", "integrate")
    assert sp.simplify(sp.sympify(symbolic.result_text) - sp.Symbol("a")**2 / 2) == 0
    divergent = calc(r"\int_{-1}^{1}\frac{1}{x^2}\,dx", "integrate")
    assert divergent.status == "unsupported"
    assert divergent.result_text is None
    assert "singularidad interior" in divergent.warnings[0]


@pytest.mark.parametrize("expression", [
    r"\int_0^1 x",  # Falta diferencial.
    r"\int_0 x\,dx",  # Falta un límite.
    r"\int_0^1\int_0^1 xy\,dx",  # Faltan diferenciales.
    r"\int_0^1\int_0^1 xy\,dx\,dx",  # Variable repetida.
    r"\int_0^x\int_0^1 xy\,dy\,dx",  # Límite exterior dependiente de sí mismo.
    r"\int_0^1\unknown{x}\,dx",  # Comando no permitido.
])
def test_integral_input_errors(expression):
    with pytest.raises(InvalidExpression):
        calc(expression, "integrate")


def test_integral_operation_conflict():
    with pytest.raises(InvalidExpression, match="integral"):
        solve(MathRequest(expression=r"\int_0^2 x^2\,dx", operation="differentiate", operation_explicit=True))


def test_integral_depth_limit():
    nested = "{" * 30 + "x" + "}" * 30
    with pytest.raises(InvalidExpression, match="niveles"):
        calc(r"\int_0^1 " + nested + r"\,dx", "integrate")


def test_latex_request_takes_precedence_over_ascii_integral():
    result = solve(MathRequest(expression="int _0^2x^2 d x", latex=r"\int_0^2 x^2\,dx", operation="simplify"))
    assert result.result_text == "8/3"
