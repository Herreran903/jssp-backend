from __future__ import annotations

import datetime as _dt
import json
import os
import re
from typing import Any, Dict, List, Tuple

from minizinc import Instance, Model, Result, Solver  # type: ignore

from .models import HeuristicType, Machine, Operation, SearchConfig, Solution


# Public API ------------------------------------------------------------------


def solve_jobshop(
    *,
    model_id: str,
    variation: str,
    data: Dict[str, Any],
    search: SearchConfig,
) -> Tuple[Solution, Dict[str, float]]:
    """
    Execute the specified jobshop variation using MiniZinc and normalize the solution.

    Returns:
        (solution, stats)
    Raises:
        ValueError on validation / unsupported model/variation or data problems.
        RuntimeError on MiniZinc execution errors or no feasible solution.
    """
    model_path = _select_jobshop_model_path(model_id=model_id, variation=variation)

    if variation == "tardanza":
        return _run_jobshop_tardanza(model_path=model_path, data=data, search=search)
    elif variation == "mantenimiento":
        return _run_jobshop_mantenimiento(model_path=model_path, data=data, search=search)
    else:
        raise ValueError(f"Unsupported variation '{variation}' for modelId '{model_id}'")


def parse_instance_payload_from_multipart(
    *,
    content: bytes,
    filename: str | None,
) -> Dict[str, Any]:
    """
    Parse instance file (multipart upload) into a MiniZinc data dictionary.
    - Supports JSON (.json) and DZN-like (.dzn or default) textual formats.
    """
    name = (filename or "").lower()
    text = content.decode("utf-8", errors="replace")

    # Prefer JSON if extension or if the content parses as JSON.
    if name.endswith(".json"):
        try:
            obj = json.loads(text)
            if not isinstance(obj, dict):
                raise ValueError("JSON instance must be an object")
            return obj
        except Exception as exc:  # fallthrough to DZN parser with clear message
            raise ValueError(f"Invalid JSON instance file: {exc}") from exc

    # If not explicitly .json, try JSON first anyway (helpful for misnamed files)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Parse as DZN
    return _parse_dzn(text)


def load_instance_by_id(instance_id: str) -> Dict[str, Any]:
    """
    Load stored instance data by id from ./storage/instances/{instanceId}.{json|dzn}
    Preference: .json first, then .dzn
    """
    base_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", "instances"))
    json_path = os.path.join(base_dir, f"{instance_id}.json")
    dzn_path = os.path.join(base_dir, f"{instance_id}.dzn")

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
            if not isinstance(obj, dict):
                raise ValueError(f"Stored instance JSON is not an object: {json_path}")
            return obj

    if os.path.exists(dzn_path):
        with open(dzn_path, "r", encoding="utf-8") as fh:
            return _parse_dzn(fh.read())

    raise ValueError(f"Instance not found: {instance_id}")


# Internal helpers -------------------------------------------------------------


def _select_jobshop_model_path(*, model_id: str, variation: str) -> str:
    if model_id != "jobshop":
        raise ValueError(f"Unsupported modelId '{model_id}'")

    root = os.path.dirname(__file__)
    models_dir = os.path.join(root, "modelos")
    if variation == "tardanza":
        path = os.path.join(models_dir, "JOBSHOP_TARDANZA.MZN")
    elif variation == "mantenimiento":
        path = os.path.join(models_dir, "JOBSHOP_MANTENIMIENTO.MZN")
    else:
        raise ValueError(f"Unsupported variation '{variation}' for modelId '{model_id}'")

    if not os.path.exists(path):
        raise RuntimeError(f"Model file not found: {path}")
    return path


def _run_jobshop_tardanza(
    *,
    model_path: str,
    data: Dict[str, Any],
    search: SearchConfig,
) -> Tuple[Solution, Dict[str, float]]:
    """
    Inputs expected in 'data':
      - jobs: int
      - tasks: int
      - d: 2D int [jobs][tasks]
      - weights: 1D int [jobs]
      - due_dates: 1D int [jobs]
    Result variables used:
      - s: 2D int [jobs][tasks] (start times)
      - w: int (weighted tardiness)
      - end_job, T, end may also be present but are not required
    """
    jobs = _require_int(data, "jobs")
    tasks = _require_int(data, "tasks")
    d = _require_2d_int(data, "d", rows=jobs, cols=tasks)
    weights = _require_1d_int(data, "weights", size=jobs)
    due_dates = _require_1d_int(data, "due_dates", size=jobs)

    instance = _build_instance(model_path)
    instance["jobs"] = int(jobs)
    instance["tasks"] = int(tasks)
    instance["d"] = d
    instance["weights"] = weights
    instance["due_dates"] = due_dates

    result = _solve_instance(instance, search=search)

    if not result.status.has_solution():
        raise RuntimeError("MiniZinc did not produce a feasible solution")

    s = _require_result_2d(result, "s", rows=jobs, cols=tasks)
    w = _require_result_int(result, "w")

    # Normalize machines
    machines = [Machine(id=f"M{j}", name=f"M{j}") for j in range(1, tasks + 1)]

    # Build operations
    ops: List[Operation] = []
    for i in range(1, jobs + 1):
        for j in range(1, tasks + 1):
            start = float(s[i - 1][j - 1])
            duration = float(d[i - 1][j - 1])
            end = start + duration
            ops.append(
                Operation(
                    jobId=f"J{i}",
                    machineId=f"M{j}",
                    opId=f"J{i}-{j}",
                    start=start,
                    end=end,
                    duration=duration,
                )
            )

    makespan = max((op.end for op in ops), default=0.0)

    stats: Dict[str, float] = {
        "w": float(w),
    }
    # Optionally, compute additional stats (not required):
    # end_job = [ s[i,tasks] + d[i,tasks] ]; tardiness count, etc. (omitted to keep minimal)

    solution = Solution(
        makespan=float(makespan),
        machines=machines,
        operations=ops,
        stats={k: float(v) for k, v in stats.items()},
    )
    return solution, stats


def _run_jobshop_mantenimiento(
    *,
    model_path: str,
    data: Dict[str, Any],
    search: SearchConfig,
) -> Tuple[Solution, Dict[str, float]]:
    """
    Inputs expected in 'data':
      - JOBS: int
      - TASKS: int
      - PROC_TIME: 2D int [JOBS][TASKS]
      - MAX_MAINT_WINDOWS: int
      - MAINT_START: 2D int [TASKS][MAX_MAINT_WINDOWS]
      - MAINT_END: 2D int [TASKS][MAX_MAINT_WINDOWS]
      - MAINT_ACTIVE: 2D bool [TASKS][MAX_MAINT_WINDOWS]
    Result variables used:
      - S: 2D int [JOBS][TASKS] (start times)
      - END: int (makespan)
    """
    JOBS = _require_int(data, "JOBS")
    TASKS = _require_int(data, "TASKS")
    PROC_TIME = _require_2d_int(data, "PROC_TIME", rows=JOBS, cols=TASKS)
    MAX_MW = _require_int(data, "MAX_MAINT_WINDOWS")
    MAINT_START = _require_2d_int(data, "MAINT_START", rows=TASKS, cols=MAX_MW)
    MAINT_END = _require_2d_int(data, "MAINT_END", rows=TASKS, cols=MAX_MW)
    MAINT_ACTIVE = _require_2d_bool(data, "MAINT_ACTIVE", rows=TASKS, cols=MAX_MW)

    instance = _build_instance(model_path)
    instance["JOBS"] = int(JOBS)
    instance["TASKS"] = int(TASKS)
    instance["PROC_TIME"] = PROC_TIME
    instance["MAX_MAINT_WINDOWS"] = int(MAX_MW)
    instance["MAINT_START"] = MAINT_START
    instance["MAINT_END"] = MAINT_END
    instance["MAINT_ACTIVE"] = MAINT_ACTIVE

    result = _solve_instance(instance, search=search)

    if not result.status.has_solution():
        raise RuntimeError("MiniZinc did not produce a feasible solution")

    S = _require_result_2d(result, "S", rows=JOBS, cols=TASKS)
    END = _require_result_int(result, "END")

    machines = [Machine(id=f"M{j}", name=f"M{j}") for j in range(1, TASKS + 1)]

    ops: List[Operation] = []
    for i in range(1, JOBS + 1):
        for j in range(1, TASKS + 1):
            start = float(S[i - 1][j - 1])
            duration = float(PROC_TIME[i - 1][j - 1])
            end = start + duration
            ops.append(
                Operation(
                    jobId=f"J{i}",
                    machineId=f"M{j}",
                    opId=f"J{i}-{j}",
                    start=start,
                    end=end,
                    duration=duration,
                )
            )

    # Stats for maintenance (optional)
    maint_windows = 0
    maint_time = 0
    for m in range(TASKS):
        for k in range(MAX_MW):
            if bool(MAINT_ACTIVE[m][k]):
                maint_windows += 1
                dur = max(0, int(MAINT_END[m][k]) - int(MAINT_START[m][k]))
                maint_time += dur

    stats: Dict[str, float] = {
        "maint_windows": float(maint_windows),
        "maint_time": float(maint_time),
    }

    solution = Solution(
        makespan=float(END),
        machines=machines,
        operations=ops,
        stats=stats,
    )
    return solution, stats


def _build_instance(model_path: str) -> Instance:
    # Use default solver (gecode) if available, else chuffed.
    solver = Solver.lookup("gecode") or Solver.lookup("chuffed")
    if solver is None:
        raise RuntimeError("No MiniZinc solver found (e.g., 'gecode' or 'chuffed'). Ensure MiniZinc is installed and on PATH.")
    model = Model(model_path)
    return Instance(solver, model)


def _solve_instance(instance: Instance, *, search: SearchConfig) -> Result:
    timeout: _dt.timedelta | None = None
    if search.timeLimitSec and search.timeLimitSec > 0:
        timeout = _dt.timedelta(seconds=float(search.timeLimitSec))
    # maxSolutions currently unused; could be mapped to 'all_solutions'
    if timeout is not None:
        return instance.solve(timeout=timeout)
    return instance.solve()


# Result extraction helpers ----------------------------------------------------


def _require_result_int(result: Result, key: str) -> int:
    if key not in result:
        raise RuntimeError(f"Result missing key '{key}'")
    val = result[key]
    try:
        return int(val)  # type: ignore[arg-type]
    except Exception as exc:
        raise RuntimeError(f"Result key '{key}' is not an int: {val}") from exc


def _require_result_2d(result: Result, key: str, *, rows: int, cols: int) -> List[List[int]]:
    if key not in result:
        raise RuntimeError(f"Result missing key '{key}'")
    val = result[key]
    # MiniZinc Python typically returns nested lists for arrays
    try:
        mat = [[int(val[i][j]) for j in range(cols)] for i in range(rows)]  # type: ignore[index]
        return mat
    except Exception as exc:
        raise RuntimeError(f"Result key '{key}' is not a 2D int matrix with shape [{rows}][{cols}]") from exc


# Input validation helpers -----------------------------------------------------


def _require_int(data: Dict[str, Any], key: str) -> int:
    if key not in data:
        raise ValueError(f"Missing required key '{key}'")
    try:
        return int(data[key])
    except Exception as exc:
        raise ValueError(f"Key '{key}' must be an integer") from exc


def _require_1d_int(data: Dict[str, Any], key: str, *, size: int) -> List[int]:
    if key not in data:
        raise ValueError(f"Missing required key '{key}'")
    arr = data[key]
    if not isinstance(arr, list):
        raise ValueError(f"Key '{key}' must be a 1D list of int")
    if len(arr) != size:
        raise ValueError(f"Key '{key}' must have length {size}")
    try:
        return [int(x) for x in arr]
    except Exception as exc:
        raise ValueError(f"Key '{key}' must contain integers") from exc


def _require_2d_int(data: Dict[str, Any], key: str, *, rows: int, cols: int) -> List[List[int]]:
    if key not in data:
        raise ValueError(f"Missing required key '{key}'")
    mat = data[key]
    if isinstance(mat, list) and mat and all(isinstance(r, list) for r in mat):
        if len(mat) != rows or any(len(r) != cols for r in mat):
            raise ValueError(f"Key '{key}' must be a 2D list with shape [{rows}][{cols}]")
        try:
            return [[int(v) for v in row] for row in mat]
        except Exception as exc:
            raise ValueError(f"Key '{key}' must contain integers") from exc
    # Support flat list from DZN parse
    if isinstance(mat, list) and (rows * cols == len(mat)):
        out: List[List[int]] = []
        idx = 0
        for _ in range(rows):
            out.append([int(mat[idx + j]) for j in range(cols)])
            idx += cols
        return out
    raise ValueError(f"Key '{key}' must be a 2D list of ints with shape [{rows}][{cols}]")


def _require_2d_bool(data: Dict[str, Any], key: str, *, rows: int, cols: int) -> List[List[bool]]:
    if key not in data:
        raise ValueError(f"Missing required key '{key}'")
    mat = data[key]
    if isinstance(mat, list) and mat and all(isinstance(r, list) for r in mat):
        if len(mat) != rows or any(len(r) != cols for r in mat):
            raise ValueError(f"Key '{key}' must be a 2D list with shape [{rows}][{cols}]")
        try:
            return [[bool(v) for v in row] for row in mat]
        except Exception as exc:
            raise ValueError(f"Key '{key}' must contain booleans") from exc
    # Support flat list
    if isinstance(mat, list) and (rows * cols == len(mat)):
        out: List[List[bool]] = []
        idx = 0
        for _ in range(rows):
            out.append([bool(_parse_bool(mat[idx + j])) for j in range(cols)])
            idx += cols
        return out
    raise ValueError(f"Key '{key}' must be a 2D list of bool with shape [{rows}][{cols}]")


def _parse_bool(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(int(x))
    if isinstance(x, str):
        t = x.strip().lower()
        if t in {"true", "t", "1"}:
            return True
        if t in {"false", "f", "0"}:
            return False
    raise ValueError(f"Cannot parse boolean from {x!r}")


# DZN parsing ------------------------------------------------------------------


_DZN_STMT_SEP = re.compile(r";\s*(?=(?:[^\"%]|\"[^\"]*\"|%[^\n]*\n)*$)", re.MULTILINE)
_DZN_COMMENT = re.compile(r"%[^\n]*")
_DZN_WS = re.compile(r"\s+")


def _parse_dzn(text: str) -> Dict[str, Any]:
    """
    Minimal DZN-like parser for the expected instances.
    Supports:
      - int scalars: name = 42;
      - 1D arrays of int/bool: name = [1,2,3]; or [true, false, true];
      - 2D arrays via array2d(..., [flat...]);
    Returns a dict; 2D arrays might be left flat and reshaped by consumers.
    """
    no_comments = _DZN_COMMENT.sub("", text)
    # Keep newlines to better handle large arrays; split by ';'
    statements = [s.strip() for s in no_comments.split(";") if s.strip()]
    data: Dict[str, Any] = {}

    for stmt in statements:
        # Expect "key = value"
        parts = stmt.split("=", 1)
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        val = parts[1].strip()

        # array2d(...)
        m_arr2d = re.match(r"array2d\s*\(\s*[^,]+,\s*[^,]+,\s*\[(.*)\]\s*\)\s*$", val, re.IGNORECASE | re.DOTALL)
        if m_arr2d:
            flat_str = m_arr2d.group(1)
            flat_vals = _split_array_values(flat_str)
            # keep flat; consumer will reshape with known dims
            data[key] = flat_vals
            continue

        # 1D array: [ ... ]
        m_arr = re.match(r"\[\s*(.*)\s*\]\s*$", val, re.DOTALL)
        if m_arr:
            items_str = m_arr.group(1)
            items = _split_array_values(items_str)
            data[key] = items
            continue

        # Scalar int or bool
        v = val
        # Strip trailing text artifacts
        v = v.strip()
        # Bool?
        if v.lower() in {"true", "false"}:
            data[key] = (v.lower() == "true")
            continue
        # Int?
        try:
            data[key] = int(v)
            continue
        except Exception:
            pass

        # Fallback raw string
        data[key] = v

    return data


def _split_array_values(items_str: str) -> List[Any]:
    # Remove newlines, repeated whitespace
    s = items_str.strip()
    # Replace newlines with spaces to simplify splitting
    s = re.sub(r"\s+", " ", s)
    # Split by comma
    tokens = [t.strip() for t in s.split(",") if t.strip()]
    out: List[Any] = []
    for t in tokens:
        tl = t.lower()
        if tl in {"true", "false"}:
            out.append(tl == "true")
        else:
            try:
                out.append(int(t))
            except Exception:
                # Fallback keep as raw token
                out.append(t)
    return out