# MathTutor

Prototipo universitario local de calculadora matemática conversacional. El frontend usa Next.js, MathLive, KaTeX, Plotly y los componentes oficiales de chat de shadcn/ui Base UI. El backend usa FastAPI, SymPy y NumPy. No requiere cuenta, base de datos ni modelo de IA.

## Ejecutar en Ubuntu

El backend necesita Python 3.12 o superior con `venv` y `pip` disponibles. Desde este directorio:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:3000`. La ruta de Next.js `/api/math` comunica con FastAPI en `http://127.0.0.1:8000`. Se puede cambiar mediante `MATHTUTOR_BACKEND_URL` al iniciar Next.js.

## Uso

Selecciona una operación y escribe la expresión en MathLive. El editor envía ASCIIMath y LaTeX al backend: el parser restringido usa ASCIIMath para las operaciones habituales y lee la estructura LaTeX cuando hay una integral completa. La multiplicación explícita con `*` también se acepta. Para derivadas escribe la función y elige los parámetros en los controles. Para sistemas, introduce la segunda ecuación en el campo adicional. Para volumen, introduce la curva superior y opcionalmente la inferior, el intervalo y el eje.

En la pestaña `f(x)` del teclado hay plantillas de integral indefinida, definida, doble y triple. Completa los límites, el integrando y los diferenciales en el propio editor con la tecla de siguiente campo (`⇥`) o el teclado físico. Por ejemplo, `\int_0^2\int_0^3 xy\,dy\,dx` integra primero respecto a `y` y después respecto a `x`. Una integral completa selecciona automáticamente Integrar o Integral definida; si se eligió explícitamente una operación contradictoria, se solicita corregirla. Las expresiones simples como `x^2` aún pueden integrarse mediante el selector y el control de variable. Los controles externos de límites se ocultan cuando la integral ya los contiene.

Operaciones implementadas: simplificación, desarrollo, factorización, ecuaciones, sistemas de dos ecuaciones en x/y, límites, derivadas, integrales indefinidas, definidas, dobles y triples iteradas, gráficas de funciones y volumen por arandelas o cascarones en intervalos compatibles. Los resultados son simbólicos de SymPy. Las gráficas contienen muestras de NumPy y marcan raíces e intersecciones finitas cuando SymPy las encuentra.

## Pruebas

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx tsc --noEmit && npm run lint
```

## Límites conocidos

- El parser admite números, variables x/y/z/t/u/v/a/b/c/n, constantes pi/e, operadores y funciones sin, cos, tan, asin, acos, atan, sinh, cosh, exp, log, ln, sqrt y abs. No acepta sintaxis Python ni toda la notación de MathLive. Las expresiones difíciles pueden agotar el límite de siete segundos.
- El lector de integrales acepta hasta tres integraciones consecutivas, con un diferencial por integral y límites completos en todas o en ninguna. Conserva el orden escrito y admite límites negativos, fraccionarios, simbólicos, dependientes de variables exteriores e infinitos. No admite integrales mezcladas (unas definidas y otras indefinidas), integrales dentro de sumas ni todos los comandos LaTeX. Si SymPy deja una integral sin evaluar o obtiene un valor no finito, la presenta como no resuelta.
- Los procedimientos detallados existen para transformaciones algebraicas, ecuaciones lineales y algunas reglas simples de derivación e integración. En otros casos se indica que el procedimiento es parcial o no está disponible. La salida simbólica de SymPy no equivale por sí sola a una demostración pedagógica.
- La verificación de una integral iterada comprueba las antiderivadas y la sustitución de límites cuando SymPy puede hacerlo; no constituye una prueba general de convergencia ante singularidades interiores o parámetros simbólicos sin hipótesis de dominio. La equivalencia algebraica se entiende en el dominio común.
- Los sólidos se restringen a regiones continuas, sin cruces interiores de curvas o eje y con límites finitos. Los casos que requieren partición se rechazan. La vista 3D muestra las superficies de las dos curvas cuando corresponde; no dibuja las tapas de los extremos.
- Las gráficas no incluyen todavía tangentes ni sombreado de áreas. Las discontinuidades se separan mediante valores indefinidos y detección de saltos, con las limitaciones de un muestreo finito.
- Las inecuaciones y series todavía no están implementadas. Para problemas no cubiertos, el backend informa la limitación en lugar de inventar un procedimiento.
# math-tutor
