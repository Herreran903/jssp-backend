from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import SolverConfig, Solution, SolutionEnvelope, Meta
from .validation import validate_solution
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

    app = FastAPI(title="JSSP Backend", version="1.0.0")

    # CORS: allow calls from the frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "Bad Request"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )

    @app.get("/")
    async def root():
        """Health check endpoint."""
        return {"status": "ok", "service": "JSSP Backend"}

    @app.post("/api/solve-once")
    async def solve_once(request: Request):
        """
        POST /api/solve-once
        
        Accepts either:
        1. application/json with:
           - instanceId: string (required)
           - instanceName: string (optional)
           - solverConfig: SolverConfig object (required)
           - fileName: string (optional, informational)
        
        2. multipart/form-data with:
           - file: UploadFile (optional if instanceId provided)
           - instanceId: string (optional if file provided)
           - instanceName: string (optional)
           - solverConfig: string (JSON serialized SolverConfig, required)
        
        Returns: SolutionEnvelope (without meta field)
        """
        try:
            content_type = request.headers.get("content-type", "")
            logger.info("Incoming request Content-Type: %s", content_type)

            # Extract inputs depending on content type
            if "multipart/form-data" in content_type:
                # Handle multipart/form-data
                form = await request.form()
                
                # Parse solverConfig (required)
                solver_config_raw = form.get("solverConfig")
                if not solver_config_raw:
                    raise HTTPException(
                        status_code=400, detail="Field 'solverConfig' is required"
                    )
                
                try:
                    solver_config_obj = json.loads(str(solver_config_raw))
                except Exception:
                    raise HTTPException(
                        status_code=400, 
                        detail="Field 'solverConfig' must be a valid JSON string"
                    )
                
                try:
                    solver_config = SolverConfig.model_validate(solver_config_obj)
                except Exception as e:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid solverConfig: {str(e)}"
                    )

                # Instance source: file or instanceId
                file = form.get("file")
                instance_id = form.get("instanceId")
                instance_name = form.get("instanceName")
                
                data: dict[str, Any]
                if file is not None and hasattr(file, "read"):
                    try:
                        content = await file.read()  # type: ignore[assignment]
                    except Exception:
                        raise HTTPException(
                            status_code=400, detail="Failed to read uploaded file"
                        )
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
                # Handle application/json
                try:
                    body: dict[str, Any] = await request.json()  # type: ignore[assignment]
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid JSON body")

                # Required fields for JSON mode
                instance_id = body.get("instanceId")
                if not instance_id:
                    raise HTTPException(
                        status_code=400, detail="Field 'instanceId' is required"
                    )

                solver_config_obj = body.get("solverConfig")
                if solver_config_obj is None:
                    raise HTTPException(
                        status_code=400, detail="Field 'solverConfig' is required"
                    )

                try:
                    solver_config = SolverConfig.model_validate(solver_config_obj)
                except Exception as e:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid solverConfig: {str(e)}"
                    )

                instance_name = body.get("instanceName")

                # Load stored instance by id
                try:
                    data = load_instance_by_id(str(instance_id))
                except ValueError as ve:
                    raise HTTPException(status_code=400, detail=str(ve))

            # Solve with MiniZinc using the configured solver
            try:
                solution, _stats, elapsed_ms = await solve_jobshop(
                    data=data, solver_config=solver_config
                )
            except ValueError as ve:
                # Input/data validation errors
                raise HTTPException(status_code=400, detail=str(ve))
            except RuntimeError as re:
                # MiniZinc execution errors
                logger.error("MiniZinc execution error: %s", re)
                envelope = SolutionEnvelope(
                    status="ERROR",
                    logs=[f"error: {str(re)}"]
                )
                return JSONResponse(
                    status_code=200,
                    content=envelope.model_dump(exclude_none=True)
                )

            # Validate solution
            try:
                validate_solution(solution)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))

            # Build logs with configuration details
            logs = [
                f"solver:{solver_config.solver}",
                f"problemType:{solver_config.problemType}",
                f"searchHeuristic:{solver_config.searchHeuristic}",
                f"valueChoice:{solver_config.valueChoice}",
            ]
            
            if instance_name:
                logs.append(f"instanceName:{instance_name}")

            # Create meta object with execution metadata
            meta = Meta(
                elapsedMs=elapsed_ms,
                timestamp=datetime.now(timezone.utc).isoformat()
            )

            envelope = SolutionEnvelope(
                status="COMPLETED",
                solution=solution,
                meta=meta,
                logs=logs,
            )
            return JSONResponse(
                status_code=200,
                content=envelope.model_dump(exclude_none=True)
            )

        except HTTPException:
            # Forward explicit HTTP errors as-is
            raise
        except Exception as exc:
            logger.exception("Unexpected error in /api/solve-once: %s", exc)
            # Let global handler format the 500
            raise

    return app


# Create app instance for uvicorn: uvicorn app.main:app --reload
app = create_app()