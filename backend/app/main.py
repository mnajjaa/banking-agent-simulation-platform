from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .logic import (
    load_df, DATA_PATH, _last_schema_mapping,
    segment_customers,
    simulate, compare,
    run_abm_preview, simulate_with_abm,
    # Type aliases from logic.py (keep API aligned with engine)
    ScenarioType, Intensity, Segment, RegionName
)

app = FastAPI(title="BIAT Agentic Optimization API", version="0.2.0", debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/schema")
def api_schema():
    load_df()
    return {"data_path": str(DATA_PATH), "mapping": _last_schema_mapping}

# -------- Segmentation --------
class SegReq(BaseModel):
    n_clusters: int = 4

@app.post("/segments")
def api_segments(req: SegReq):
    try:
        return segment_customers(req.n_clusters)
    except Exception as e:
        cols = list(load_df().columns)
        raise HTTPException(status_code=400, detail=f"{e}. Available columns: {cols[:20]}...")

# -------- Scenarios (Pydantic models use types from logic.py) --------
class SimRequest(BaseModel):
    scenario: ScenarioType
    intensity: Intensity = "Moyenne"
    segment: Segment = "Tous les segments"
    region: RegionName = "Sousse"
    duration_months: int = Field(6, ge=1, le=24)

@app.post("/simulate")
def api_simulate(req: SimRequest):
    return simulate(
        scenario=req.scenario,
        intensity=req.intensity,
        segment=req.segment,
        region=req.region,
        duration_months=req.duration_months,
    )

class CompareRequest(BaseModel):
    scenarios: List[SimRequest]

@app.post("/compare")
def api_compare(req: CompareRequest):
    payload = [r.dict() for r in req.scenarios]
    return compare(payload)

# -------- ABM endpoints (AgentPy-backed) --------
@app.get("/abm/preview")
def abm_preview(
    scenario: ScenarioType = "Baseline",
    intensity: Intensity = "Moyenne",
    steps: int = 6,
    seed: int = 42
):
    try:
        return run_abm_preview(scenario, intensity, steps, seed)
    except ImportError as e:
        # AgentPy not installed or import failed — return a helpful 501
        raise HTTPException(status_code=501, detail=str(e))

@app.post("/simulate_abm")
def simulate_abm(req: SimRequest, seed: int = 42):
    """Deterministic simulate + ABM preview bundled."""
    try:
        return simulate_with_abm(
            scenario=req.scenario,
            intensity=req.intensity,
            segment=req.segment,
            region=req.region,
            duration_months=req.duration_months,
            seed=seed,
        )
    except ImportError as e:
        raise HTTPException(status_code=501, detail=str(e))
