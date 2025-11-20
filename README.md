# JSSP Backend

Servicio backend en Python (FastAPI) para resolver variantes del Job Shop Scheduling Problem (JSSP) usando MiniZinc. Expone un endpoint HTTP para ejecutar una resolución única de una instancia y devolver un sobre de solución con operaciones, máquinas, métricas y bitácora de configuración.

Código principal en [app/main.py](app/main.py), modelos de datos en [app/models.py](app/models.py), lógica de resolución y parseo en [app/solver.py](app/solver.py) y validaciones en [app/validation.py](app/validation.py). Aplicación creada en [def create_app()](app/main.py:22) y endpoint principal en [def solve_once()](app/main.py:62).

## Arquitectura general

- Backend: FastAPI sirviendo:
  - GET / → health check.
  - POST /api/solve-once → ejecuta MiniZinc con una instancia dada.
- Motor de resolución: MiniZinc invocado desde Python vía paquete minizinc, modelos en:
  - [app/modelos/JOBSHOP_TARDANZA.MZN](app/modelos/JOBSHOP_TARDANZA.MZN)
  - [app/modelos/JOBSHOP_MANTENIMIENTO.MZN](app/modelos/JOBSHOP_MANTENIMIENTO.MZN)
- Almacenamiento de instancias de ejemplo: [storage/instances/](storage/instances/)
- No hay frontend en este repositorio. CORS está habilitado para orígenes externos en [app/main.py](app/main.py).

## Requisitos previos

Opción A: Local (sin contenedor)
- Python 3.11 (recomendado; el contenedor usa 3.11)
- MiniZinc instalado y disponible en PATH
- pip y venv

Opción B: Docker
- Docker 24+ recomendado

## Instalación y ejecución local

Rápido con scripts:
- macOS/Linux: [start.sh](start.sh)
- Windows: [start.bat](start.bat)

Manual (macOS/Linux):
- Crear y activar entorno
  - python3 -m venv venv
  - source venv/bin/activate
- Instalar dependencias
  - pip install -U pip
  - pip install -r [requirements.txt](requirements.txt)
- Iniciar servidor
  - uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Verificación:
- Abrir http://localhost:8000/ debe responder {"status":"ok","service":"JSSP Backend"}
- Documentación interactiva: http://localhost:8000/docs

## Configuración y variables de entorno

- PORT: puerto al que escucha uvicorn. Por defecto 8000 localmente. En contenedores/Render se puede inyectar; ver [render.yaml](render.yaml) y [Dockerfile](Dockerfile).
- No hay otras variables de entorno obligatorias.

## API

Base URL: http://localhost:8000

Endpoints:
- GET / → health check.
- POST /api/solve-once → recibe una instancia por id o archivo y una configuración de solver, y retorna un [class SolutionEnvelope](app/models.py:56).

Esquemas principales:
- [class SolverConfig](app/models.py:7)
  - problemType: "jssp_maint" | "tardanza_ponderada"
  - solver: "chuffed" | "gecode" | "or-tools"
  - searchHeuristic: "input_order" | "first_fail" | "smallest" | "largest" | "dom_w_deg" | "impact" | "activity"
  - valueChoice: "indomain_min" | "indomain_max" | "indomain_middle" | "indomain_median" | "indomain_random" | "indomain_split"
  - timeLimitSec: número ≥ 0
  - maxSolutions: entero ≥ 1
- [class Solution](app/models.py:48) con makespan, machines, operations y stats.
  - Para `tardanza_ponderada`: stats incluye `w` (tardanza ponderada), `tardanza_total`, `jobs_tardios`, `max_tardanza`
  - Para `jssp_maint`: stats incluye `maint_windows` (ventanas de mantenimiento activas), `maint_time` (tiempo total de mantenimiento)
- Validación de solución en [def validate_solution()](app/validation.py:20).

Modos de envío:

1) JSON application/json
- Cuerpo:
{
  "instanceId": "sample-maint",
  "instanceName": "demo mantenimiento",
  "solverConfig": {
    "problemType": "jssp_maint",
    "solver": "gecode",
    "searchHeuristic": "first_fail",
    "valueChoice": "indomain_min",
    "timeLimitSec": 10,
    "maxSolutions": 1
  }
}

Ejemplo curl:
curl -X POST http://localhost:8000/api/solve-once \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "instanceId": "sample-maint",
  "solverConfig": {
    "problemType": "jssp_maint",
    "solver": "gecode",
    "searchHeuristic": "first_fail",
    "valueChoice": "indomain_min",
    "timeLimitSec": 5,
    "maxSolutions": 1
  }
}
JSON

2) multipart/form-data con archivo
- Campos:
  - file: archivo .json o .dzn
  - solverConfig: string JSON del objeto SolverConfig
  - instanceName: opcional
  - instanceId: opcional si se adjunta file

Ejemplo curl:
curl -X POST http://localhost:8000/api/solve-once \
  -F file=@storage/instances/sample-tardanza.json \
  -F solverConfig='{"problemType":"tardanza_ponderada","solver":"gecode","searchHeuristic":"first_fail","valueChoice":"indomain_min","timeLimitSec":5,"maxSolutions":1}' \
  -F instanceName="demo tardanza"

Notas:
- Si se usa instanceId, el backend carga [def load_instance_by_id()](app/solver.py:80) desde [storage/instances](storage/instances/), buscando {id}.json o {id}.dzn.
- Archivos .dzn y .json se aceptan; el parseo de multipart se hace en [def parse_instance_payload_from_multipart()](app/solver.py:46).
- La ejecución MiniZinc se orquesta en [def solve_jobshop()](app/solver.py:18), que delega a variantes según problemType.

## Modelos MiniZinc soportados

- tardanza_ponderada → [app/modelos/JOBSHOP_TARDANZA.MZN](app/modelos/JOBSHOP_TARDANZA.MZN)
  - Datos esperados: jobs, tasks, d, weights, due_dates.
- jssp_maint → [app/modelos/JOBSHOP_MANTENIMIENTO.MZN](app/modelos/JOBSHOP_MANTENIMIENTO.MZN)
  - Datos esperados: JOBS, TASKS, PROC_TIME, MAX_MAINT_WINDOWS, MAINT_START, MAINT_END, MAINT_ACTIVE.

La inyección de estrategia de búsqueda al modelo se realiza en [def _build_modified_model()](app/solver.py:123). La selección del solver se hace en [def _build_instance()](app/solver.py:348).

## Instancias de ejemplo

- [storage/instances/sample-maint.json](storage/instances/sample-maint.json)
- [storage/instances/sample-tardanza.json](storage/instances/sample-tardanza.json)

Use los ids: sample-maint o sample-tardanza como instanceId.

## Ejecutar con Docker

Construir imagen:
docker build -t jssp-backend .

Ejecutar contenedor:
docker run --rm -p 8000:8000 jssp-backend

Variables:
- La imagen expone 8000 y usa PORT por entorno; por defecto 8000. Cambiar puerto:
docker run --rm -e PORT=8080 -p 8080:8080 jssp-backend

Verificación en contenedor:
- GET http://localhost:8000/
- Docs en http://localhost:8000/docs

## Despliegue en Render

Archivo [render.yaml](render.yaml) define un servicio web Docker con PORT=10000 y healthCheckPath "/".

## Pruebas

No se incluyen tests en este repositorio.

## Comandos útiles

- Ver versión de MiniZinc:
  - minizinc --version
- Ejecutar servidor localmente:
  - uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
- Scripts de inicio:
  - bash [start.sh](start.sh)
  - [start.bat](start.bat)

## Estructura del proyecto

.
├── [app/](app/)
│   ├── [__init__.py](app/__init__.py)
│   ├── [main.py](app/main.py)
│   ├── [models.py](app/models.py)
│   ├── [solver.py](app/solver.py)
│   ├── [validation.py](app/validation.py)
│   └── [modelos/](app/modelos/)
│       ├── [JOBSHOP_MANTENIMIENTO.MZN](app/modelos/JOBSHOP_MANTENIMIENTO.MZN)
│       └── [JOBSHOP_TARDANZA.MZN](app/modelos/JOBSHOP_TARDANZA.MZN)
├── [storage/](storage/)
│   └── [instances/](storage/instances/)
│       ├── [sample-maint.json](storage/instances/sample-maint.json)
│       └── [sample-tardanza.json](storage/instances/sample-tardanza.json)
├── [requirements.txt](requirements.txt)
├── [Dockerfile](Dockerfile)
├── [render.yaml](render.yaml)
├── [start.sh](start.sh)
└── [start.bat](start.bat)