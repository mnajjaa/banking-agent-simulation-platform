from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .logic import load_df, DATA_PATH, _last_schema_mapping
from .logic import segment_customers
from .logic import simulate, compare  # NEW

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

class SegReq(BaseModel):
    n_clusters: int = 4

@app.post("/segments")
def api_segments(req: SegReq):
    try:
        return segment_customers(req.n_clusters)
    except Exception as e:
        cols = list(load_df().columns)
        raise HTTPException(status_code=400, detail=f"{e}. Available columns: {cols[:20]}...")

# -------- Scenario endpoints --------
class SimRequest(BaseModel):
    scenario: Literal[
        "Fermeture d'Agence","Currency Devaluation","Energy Crisis","Political Uncertainty",
        "Digital Transformation","Tourism Recovery","Export Boom","Economic Recovery","Regional Instability","Baseline"
    ]
    intensity: Literal["Faible","Moyenne","Forte"] = "Moyenne"
    segment: Literal["Tous les segments","Premium","SME","Mass Market"] = "Tous les segments"
    region: Literal["Tunis","Sfax","Sousse","Kairouan","Bizerte","Gabès","Ariana","La Marsa"] = "Sousse"
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
