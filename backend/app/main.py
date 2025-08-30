from typing import List, Optional, Literal
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .logic import simulate_campaign, top_prospects, explain_decision
from .logic import schema_mapping
from .logic import segment_customers
from .logic import load_df, DATA_PATH, _last_schema_mapping


app = FastAPI(title="BIAT Agentic Optimization API", version="0.1.0", debug=True)  # debug=True helps while developing

# CORS for Vite (default :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CampaignParams(BaseModel):
    template: Literal["Baseline","CashToDigital","LoyaltyBoost","AggressiveRate"] = "Baseline"
    w_cash: float = Field(0.4, ge=0, le=1)
    w_dig: float = Field(0.6, ge=0, le=1)
    governorates: Optional[List[str]] = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/simulate-campaign")
def api_simulate_campaign(p: CampaignParams):
    df = simulate_campaign(p.template, p.w_cash, p.w_dig, p.governorates)
    return {"governorate_scores": df.to_dict(orient="records")}

@app.get("/top-prospects")
def api_top_prospects(threshold: float = Query(0.7, ge=0, le=1), limit: int = Query(100, ge=1, le=1000)):
    df = top_prospects(threshold, limit)
    return {"prospects": df.to_dict(orient="records")}

@app.get("/agent/{agent_id}/decisions")
def api_explain(agent_id: str):
    trace = explain_decision(agent_id)
    return {"agent_id": agent_id, "trace": trace}


@app.get("/schema")
def api_schema():
    load_df()  # ensure loader initializes and fills mapping
    return {"data_path": str(DATA_PATH), "mapping": _last_schema_mapping}


class SegReq(BaseModel):
    n_clusters: int = 4

@app.post("/segments")
def api_segments(req: SegReq):
    try:
        return segment_customers(req.n_clusters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))