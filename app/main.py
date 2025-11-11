from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    HeuristicType,
    Machine,
    Operation,
    SearchConfig,
    Solution,
    SolutionEnvelope,
)
from .validation import validate_search, validate_solution
from .solver import (
    solve_jobshop,
    parse_instance_payload_from_multipart,
    load_instance_by_id,
)

logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    """
    Build FastAPI application with:
    - CORS enabled
    - Basic logging
    - Global error handlers
    - Endpoint: POST /api/solve-once
    """
    # Basic logging config (uvicorn will integrate with this)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = FastAPI(title="JSSP Backend", version="0.1.0")

    # CORS: allow calls from the frontend; relax by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        # Return the same message (400 etc.)
        detail = exc.detail if isinstance(exc.detail, str) else "Bad Request"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )

    @app.post("/api/solve-once")
    async def solve_once(request: Request):
        """
        Contract:
        - Accepts either application/json or multipart/form-data
        - In multipart, 'search' arrives as a JSON string and must be parsed
        - Executes MiniZinc model (jobshop) per variation and returns SolutionEnvelope (no meta)
        - Errors:
            * 400 on validation problems or unknown modelId/variation
            * 500 on unexpected errors
        """
        try:
            content_type = request.headers.get("content-type", "")
            logger.info("Incoming request Content-Type: %s", content_type)

            # Extract inputs depending on content type
            if "multipart/form-data" in content_type:
                form = await request.form()
                model_id = _require_field(form, "modelId")
                variation = _require_field(form, "variation")
                search_raw = _require_field(form, "search")

                # Parse search from JSON string
                try:
                    search_obj = json.loads(search_raw)  # type: ignore[arg-type]
                except Exception:
                    raise HTTPException(
                        status_code=400, detail="Field 'search' must be a valid JSON string"
                    )
                search = SearchConfig.model_validate(search_obj)

                # Instance source: file or instanceId
                file = form.get("file")
                instance_id = form.get("instanceId")
                data: dict[str, Any]
                if file is not None and hasattr(file, "read"):
                    try:
                        content = await file.read()  # type: ignore[assignment]
                    except Exception:
                        raise HTTPException(status_code=400, detail="Failed to read uploaded file")
                    filename = getattr(file, "filename", None)
                    try:
                        data = parse_instance_payload_from_multipart(
                            content=content, filename=filename
                        )
                    except ValueError as ve:
                        raise HTTPException(status_code=400, detail=str(ve))
                elif instance_id:
                    try:
                        data = load_instance_by_id(str(instance_id))
                    except ValueError as ve:
                        raise HTTPException(status_code=400, detail=str(ve))
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Either 'file' or 'instanceId' is required in multipart/form-data",
                    )

            else:
                # Default to JSON body
                try:
                    body: dict[str, Any] = await request.json()  # type: ignore[assignment]
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid JSON body")

                # Required fields for JSON mode
                model_id = body.get("modelId")
                if not model_id:
                    raise HTTPException(status_code=400, detail="Field 'modelId' is required")

                variation = body.get("variation")
                if not variation:
                    raise HTTPException(status_code=400, detail="Field 'variation' is required")

                instance_id = body.get("instanceId")
                if not instance_id:
                    raise HTTPException(status_code=400, detail="Field 'instanceId' is required")

                search_obj = body.get("search")
                if search_obj is None:
                    raise HTTPException(status_code=400, detail="Field 'search' is required")

                search = SearchConfig.model_validate(search_obj)

                # Load stored instance by id
                try:
                    data = load_instance_by_id(str(instance_id))
                except ValueError as ve:
                    raise HTTPException(status_code=400, detail=str(ve))

            # Validations
            try:
                validate_search(search)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))

            # Model selection validation (400 on unknown)
            if model_id != "jobshop":
                raise HTTPException(status_code=400, detail=f"Unknown modelId '{model_id}'")
            if variation not in {"tardanza", "mantenimiento"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown variation '{variation}' for modelId 'jobshop'",
                )

            # Solve with MiniZinc and normalize
            try:
                solution, _stats = solve_jobshop(
                    model_id=model_id, variation=variation, data=data, search=search
                )
            except ValueError as ve:
                # Input/data validation errors
                raise HTTPException(status_code=400, detail=str(ve))

            # Contract validations on normalized solution
            try:
                validate_solution(solution)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))

            envelope = SolutionEnvelope(
                status="COMPLETED",
                solution=solution,
                logs=[f"model:{model_id}", f"variation:{variation}", f"heuristic:{search.heuristic}"],
            )
            return JSONResponse(status_code=200, content=envelope.model_dump(exclude_none=True))

        except HTTPException:
            # Forward explicit HTTP errors as-is (handled by handler too, but keep logs tidy)
            raise
        except Exception as exc:
            logger.exception("Unexpected error in /api/solve-once: %s", exc)
            # Let global handler format the 500
            raise

    return app


def _require_field(mapping: Any, key: str) -> str:
    """Helper to extract a required str field from a mapping-like object."""
    value = mapping.get(key) if hasattr(mapping, "get") else None
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise HTTPException(status_code=400, detail=f"Field '{key}' is required")
    if not isinstance(value, str):
        # For UploadFile or other types we only call this for string fields
        return str(value)
    return value


def build_mock_solution(model_id: str, heuristic: HeuristicType) -> Solution:
    """
    Produce a coherent mock solution that satisfies the contract:
    - Non-negative times
    - machineId references are valid
    - makespan >= max end
    """
    # Two machines
    machines = [
        Machine(id="M1", name="M1"),
        Machine(id="M2", name="M2"),
    ]

    # A few operations across two jobs, strictly non-negative and consistent
    operations = [
        Operation(jobId="J1", machineId="M1", opId="J1-1", start=0, end=20, duration=20),
        Operation(jobId="J1", machineId="M2", opId="J1-2", start=20, end=60, duration=40),
        Operation(jobId="J2", machineId="M2", opId="J2-1", start=0, end=30, duration=30),
        Operation(jobId="J2", machineId="M1", opId="J2-2", start=30, end=50, duration=20),
    ]

    max_end = max(op.end for op in operations)
    makespan = max_end

    # Minimal stats, values are arbitrary but numeric
    stats = {"util": 0.72, "tardanza": 12.0}

    # 'model_id' and 'heuristic' are already reflected via logs in the envelope per contract
    return Solution(
        makespan=makespan,
        machines=machines,
        operations=operations,
        stats={k: float(v) for k, v in stats.items()},
    )


# Create app instance for uvicorn: uvicorn app.main:app --reload
app = create_app()