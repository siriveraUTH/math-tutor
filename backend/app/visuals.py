import math
import numpy as np
import sympy as sp
from sympy.calculus.util import continuous_domain
from .parser import InvalidExpression

def plot_data(expressions, var, lower=-10.0, upper=10.0):
    if not lower < upper or upper - lower > 1000: raise InvalidExpression("Intervalo de gráfica inválido")
    xs = np.linspace(lower, upper, 401)
    traces = []
    for index, expr in enumerate(expressions):
        if expr.free_symbols - {var}: raise InvalidExpression("La gráfica requiere una función de una sola variable")
        fn = sp.lambdify(var, expr, modules=["numpy"])
        with np.errstate(all="ignore"):
            raw = fn(xs)
            vals = np.broadcast_to(np.asarray(raw, dtype=float), xs.shape).copy()
        finite = np.isfinite(vals) & (np.abs(vals) < 1e6)
        # Break likely asymptotes and domain gaps instead of joining branches.
        jumps = np.abs(np.diff(vals)) > max(10.0, np.nanmedian(np.abs(vals[finite])) * 20 if finite.any() else 10.0)
        finite[1:][jumps] = False
        y = [float(v) if ok else None for v, ok in zip(vals, finite)]
        traces.append({"name": f"f{index + 1}", "x": xs.tolist(), "y": y, "type": "scatter", "mode": "lines"})
    markers = []
    for index, expr in enumerate(expressions):
        try:
            roots = sp.solveset(expr, var, sp.Interval(lower, upper))
            if isinstance(roots, sp.FiniteSet):
                for root in roots:
                    if root.is_real and root.is_finite:
                        markers.append({"x": float(root), "y": 0.0, "label": f"Raíz de f{index+1}"})
        except Exception: pass
    if len(expressions) == 2:
        try:
            roots = sp.solveset(expressions[0]-expressions[1], var, sp.Interval(lower, upper))
            if isinstance(roots, sp.FiniteSet):
                for root in roots:
                    value = expressions[0].subs(var, root)
                    if root.is_real and root.is_finite and value.is_real and value.is_finite:
                        markers.append({"x": float(root), "y": float(value), "label": "Intersección"})
        except Exception: pass
    return {"traces": traces, "markers": markers, "x_label": str(var)}

def revolution(expr, other, var, lower, upper, axis, axis_value):
    if var != sp.Symbol("x", real=True): raise InvalidExpression("La revolución requiere la variable x")
    if not (lower.is_real and upper.is_real and lower.is_finite and upper.is_finite):
        raise InvalidExpression("Los límites deben ser reales y finitos")
    a, b = float(lower), float(upper)
    if not (a < b and b-a <= 100): raise InvalidExpression("Intervalo inválido")
    if any(e.free_symbols - {var} for e in (expr, other)):
        raise InvalidExpression("Las curvas deben depender solo de x")
    interval = sp.Interval(lower, upper)
    for curve in (expr, other):
        try:
            if not interval.is_subset(continuous_domain(curve, var, sp.S.Reals)):
                raise InvalidExpression("La región contiene una discontinuidad")
        except NotImplementedError:
            raise InvalidExpression("No se pudo verificar la continuidad de la región")
    offset = float(axis_value)
    if not math.isfinite(offset): raise InvalidExpression("Eje inválido")
    f = sp.lambdify(var, expr, "numpy")
    g = sp.lambdify(var, other, "numpy")
    xs = np.linspace(a, b, 101)
    with np.errstate(all="ignore"):
        fv = np.broadcast_to(np.asarray(f(xs), dtype=float), xs.shape)
        gv = np.broadcast_to(np.asarray(g(xs), dtype=float), xs.shape)
    if not np.all(np.isfinite(fv)) or not np.all(np.isfinite(gv)):
        raise InvalidExpression("La región contiene valores indefinidos")
    # Reject crossings or contact with the axis unless symbolic analysis proves a safe interval.
    checks = [expr-other]
    if axis == "x": checks += [expr-axis_value, other-axis_value]
    for check in checks:
        if sp.simplify(check) == 0: continue
        roots = sp.solveset(check, var, interval)
        if roots == sp.S.EmptySet: continue
        if not isinstance(roots, sp.FiniteSet):
            raise InvalidExpression("No se pudo verificar que las curvas conserven su orden en todo el intervalo")
        if any(root.is_real and lower < root < upper for root in roots):
            raise InvalidExpression("Las curvas se cruzan o tocan el eje dentro del intervalo; divide la región")
    if axis == "x":
        relative_f, relative_g = expr-axis_value, other-axis_value
        if any(float(sp.N(e.subs(var, x))) * float(sp.N(e.subs(var, y))) < 0
               for e in (relative_f, relative_g, expr-other)
               for x, y in zip(xs[:-1], xs[1:])):
            raise InvalidExpression("La región cambia de orden o cruza el eje; divide el intervalo")
        if np.any((fv-offset)*(gv-offset) < -1e-9):
            raise InvalidExpression("La región cruza el eje; divide el intervalo")
        outer = sp.Max(sp.Abs(relative_f), sp.Abs(relative_g))
        inner = sp.Min(sp.Abs(relative_f), sp.Abs(relative_g))
        integrand = sp.pi * (outer**2-inner**2)
        method = "arandelas"
        radius_outer = np.maximum(np.abs(fv-offset), np.abs(gv-offset))
        radius_inner = np.minimum(np.abs(fv-offset), np.abs(gv-offset))
    else:
        if a < offset < b: raise InvalidExpression("El eje vertical atraviesa el intervalo; divide la región")
        integrand = 2*sp.pi*sp.Abs(var-axis_value)*sp.Abs(expr-other)
        method = "cascarones cilíndricos"
        radius_outer = np.abs(xs-offset)
        radius_inner = np.zeros_like(xs)
    volume = sp.integrate(integrand, (var, lower, upper))
    if volume.has(sp.Integral) or not volume.is_finite: raise InvalidExpression("No se pudo evaluar el volumen con seguridad")
    # Plotly renders WebGL surfaces in the browser; a compact mesh keeps the chat responsive.
    mesh_indices = np.linspace(0, len(xs)-1, 41, dtype=int)
    mesh_xs = xs[mesh_indices]
    mesh_fv = fv[mesh_indices]
    mesh_gv = gv[mesh_indices]
    mesh_outer = radius_outer[mesh_indices]
    mesh_inner = radius_inner[mesh_indices]
    theta = np.linspace(0, 2*np.pi, 25)
    X = np.tile(mesh_xs[:, None], (1, len(theta)))
    R = mesh_outer[:, None] * np.ones_like(theta)[None, :]
    if axis == "x":
        mesh = {"x": X.tolist(), "y": (offset + R*np.cos(theta)).tolist(), "z": (R*np.sin(theta)).tolist()}
        inner = mesh_inner[:, None] * np.ones_like(theta)[None, :]
        secondary_mesh = ({"x": X.tolist(), "y": (offset + inner*np.cos(theta)).tolist(),
                           "z": (inner*np.sin(theta)).tolist()}
                          if np.any(radius_inner > 1e-9) else None)
    else:
        radial = (mesh_xs-offset)[:, None]
        rotated_x = offset + radial*np.cos(theta)
        rotated_z = radial*np.sin(theta)
        mesh = {"x": rotated_x.tolist(), "y": np.tile(mesh_fv[:, None], (1, len(theta))).tolist(), "z": rotated_z.tolist()}
        secondary_mesh = {"x": rotated_x.tolist(), "y": np.tile(mesh_gv[:, None], (1, len(theta))).tolist(), "z": rotated_z.tolist()}
    return {"method": method, "integral_latex": sp.latex(sp.Integral(integrand, (var, lower, upper))),
            "volume_latex": sp.latex(volume), "mesh": mesh, "secondary_mesh": secondary_mesh,
            "volume_text": str(volume)}
