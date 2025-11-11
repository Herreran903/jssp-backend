# JSSP Backend (FastAPI, Python 3.11+)

Single-endpoint backend exposing:
- POST /api/solve-once

Designed to be called by a Next.js frontend that may add meta fields on its side. This backend never returns meta.

## Requirements

- Python 3.11+
- pip
- Optional: Docker

## Setup (venv) and Install

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate
# On Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# Upgrade pip and install deps
pip install -U pip
pip install -r requirements.txt
```

## Run (local)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- CORS: enabled for all origins.
- Logging: basic logging to stdout via uvicorn.

## Endpoint

POST /api/solve-once

Content types:
1) application/json (no file; references an already loaded instance)
   - instanceId: string (required)
   - instanceName: string (optional)
   - modelId: string (required)
   - variation: string (optional)
   - search: object SearchConfig (required)
       - heuristic: "greedy" | "tabu" | "sa"
       - timeLimitSec: number ≥ 0
       - maxSolutions: number ≥ 1
   - fileName: string (optional; informational)

2) multipart/form-data (user uploads an instance file)
   - file: UploadFile (optional if using instanceId)
   - modelId: string (required)
   - variation: string (optional)
   - instanceId: string (optional)
   - instanceName: string (optional)
   - search: string (JSON serialized) required, same SearchConfig schema above

Response (SolutionEnvelope), never includes meta:
- status: "PENDING" | "RUNNING" | "COMPLETED" | "ERROR"
- solution?:
  - makespan: number ≥ 0
  - machines: Array<{ id: string; name: string }>
  - operations: Array<{ jobId: string; machineId: string; opId: string; start: number; end: number; duration: number }>
  - stats: Record<string, number>
- logs?: string[] (e.g., ["solver:basic","heuristic:greedy"])

Validations (400 on failure):
- SearchConfig: heuristic ∈ {"greedy","tabu","sa"}, timeLimitSec ≥ 0, maxSolutions ≥ 1
- Operations:
  - start, end, duration ≥ 0
  - recommended: end == start + duration
  - machineId must exist in machines
  - IDs consistent; no duplicates within scope (jobId, opId)
- makespan ≥ max end over operations
- 500 for unexpected errors.

## Example Requests

Export backend base for convenience:
```bash
export NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"
```

JSON:
```bash
curl -X POST "$NEXT_PUBLIC_BACKEND_URL/api/solve-once" \
  -H "Content-Type: application/json" \
  -d '{ "instanceId":"tai-20-5-10", "modelId":"basic", "search":{"heuristic":"greedy","timeLimitSec":5,"maxSolutions":1} }'
```

multipart:
```bash
curl -X POST "$NEXT_PUBLIC_BACKEND_URL/api/solve-once" \
  -H "Accept: application/json" \
  -F "file=@./instancias/tai-20-5-10.txt" \
  -F "modelId=basic" \
  -F "variation=default" \
  -F "instanceId=tai-20-5-10" \
  -F "instanceName=tai-20-5-10" \
  -F 'search={\"heuristic\":\"tabu\",\"timeLimitSec\":30,\"maxSolutions\":3}'
```

Example successful response (200):
```json
{
  "status": "COMPLETED",
  "solution": {
    "makespan": 100,
    "machines": [
      { "id": "M1", "name": "M1" },
      { "id": "M2", "name": "M2" }
    ],
    "operations": [
      { "jobId": "J1", "machineId": "M1", "opId": "J1-1", "start": 0, "end": 20, "duration": 20 }
    ],
    "stats": { "util": 0.72, "tardanza": 12 }
  },
  "logs": ["solver:basic", "heuristic:greedy"]
}
```

## Project Structure

- app/main.py — FastAPI app, CORS, error handlers, POST /api/solve-once mock solver
- app/models.py — Pydantic v2 models (SearchConfig, Solution, etc.)
- app/validation.py — Validation helpers
- requirements.txt — Python dependencies

Run target for uvicorn uses [main.app](app/main.py:171) exported at module path app.main:app.

## Docker (optional)

A Dockerfile is provided to run with uvicorn. Build and run:

```bash
docker build -t jssp-backend .
docker run --rm -p 8000:8000 jssp-backend
```

## Notes

- The backend may simulate solving and return a coherent COMPLETED solution with logs like ["solver:<modelId>","heuristic:<heuristic>"].
- The frontend is responsible for adding meta before responding to the browser; this backend never returns meta.