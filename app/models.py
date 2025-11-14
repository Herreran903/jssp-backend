from __future__ import annotations

from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict

# New SolverConfig schema as per specification
class SolverConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problemType: Literal["jssp_maint", "tardanza_ponderada"]
    solver: Literal["chuffed", "gecode", "or-tools"]
    searchHeuristic: Literal[
        "input_order",
        "first_fail",
        "smallest",
        "largest",
        "dom_w_deg",
        "impact",
        "activity"
    ]
    valueChoice: Literal[
        "indomain_min",
        "indomain_max",
        "indomain_middle",
        "indomain_median",
        "indomain_random",
        "indomain_split"
    ]
    timeLimitSec: float = Field(ge=0)
    maxSolutions: int = Field(ge=1)


class Machine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jobId: str
    machineId: str
    opId: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    duration: float = Field(ge=0)


class Solution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    makespan: float = Field(ge=0)
    machines: List[Machine]
    operations: List[Operation]
    stats: Dict[str, float]


class SolutionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["PENDING", "RUNNING", "COMPLETED", "ERROR"]
    solution: Optional[Solution] = None
    logs: Optional[List[str]] = None