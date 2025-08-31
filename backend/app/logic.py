from functools import lru_cache
from typing import Iterable, List, Optional, Dict, Literal
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import math
from pathlib import Path
import re

# ---------- EXISTING LOADER / HELPERS (unchanged) ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "tuniind.csv"
_last_schema_mapping: dict[str, str] = {}

REQUIRED = {
    "id":                          {"dtype": "string", "syn": ["agent_id", "merchant_id"]},
    "name":                        {"dtype": "string", "syn": ["merchant_name", "agent_name"]},
    "governorate":                 {"dtype": "string", "syn": ["region", "state", "gov"] , "default": "Unknown"},
    "business_size":               {"dtype": "string", "syn": ["size", "segment"],       "default": "SME"},
    "cash_usage_ratio":            {"dtype": "float",  "syn": ["cash_usage","cash_rate","cash_ratio","cash_usage_rate"], "default": 0.5},
    "digital_payment_adoption":    {"dtype": "float",  "syn": ["digital_adoption","digital_ratio","digital_payments","dpa"], "default": 0.5},
}
STRICT = True

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _find_column(df: pd.DataFrame, wanted: str, synonyms: list[str]) -> str | None:
    norm_map = { _norm(c): c for c in df.columns }
    for key in [wanted, *synonyms]:
        hit = norm_map.get(_norm(key))
        if hit: return hit
    return None

@lru_cache(maxsize=1)
def load_df(path: str | Path = DATA_PATH) -> pd.DataFrame:
    global _last_schema_mapping
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found at {path} (expected backend/data/tuniind.csv)")

    df = pd.read_csv(path, encoding="utf-8-sig")
    mapping = {}

    if "Dénomination" in df.columns:
        df.rename(columns={"Dénomination": "name"}, inplace=True); mapping["name"] = "Dénomination"
    elif "Raison Sociale" in df.columns:
        df.rename(columns={"Raison Sociale": "name"}, inplace=True); mapping["name"] = "Raison Sociale"
    else:
        df["name"] = ""; mapping["name"] = "[created empty]"

    if "Gouvernorat" in df.columns:
        df.rename(columns={"Gouvernorat": "governorate"}, inplace=True); mapping["governorate"] = "Gouvernorat"
    else:
        df["governorate"] = "Unknown"; mapping["governorate"] = "[created default Unknown]"

    if "id" not in df.columns:
        df.insert(0, "id", range(1, len(df) + 1)); mapping["id"] = "[created auto sequence]"

    if "business_size" not in df.columns:
        df["business_size"] = "SME"; mapping["business_size"] = "[created default SME]"

    for col, default in [("cash_usage_ratio", 0.5), ("digital_payment_adoption", 0.5)]:
        if col not in df.columns:
            df[col] = default; mapping[col] = f"[created default {default}]"
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default).clip(0, 1)

    if "conversion_probability" not in df.columns:
        df["conversion_probability"] = (
            (1 - df["cash_usage_ratio"]) * 0.4 + df["digital_payment_adoption"] * 0.6
        ).clip(0, 1)
        mapping["conversion_probability"] = "[derived (0.4/0.6 blend)]"

    _last_schema_mapping = mapping
    return df

def schema_mapping() -> dict:
    return {"data_path": str(DATA_PATH), "mapping": _last_schema_mapping}

def _to_number(s: pd.Series) -> pd.Series:
    x = s.astype(str)
    x = x.str.replace("\u00A0", "", regex=False).str.replace("\u202F", "", regex=False).str.replace(" ", "", regex=False)
    x = x.str.replace(",", ".", regex=False)
    x = x.str.replace(r"[^0-9.\-]", "", regex=True)
    x = x.str.replace(r"(\.)(?=.*\.)", "", regex=True)
    return pd.to_numeric(x, errors="coerce")

def segment_customers(n_clusters: int = 4):
    df = load_df().copy()
    cap_col = "Capital en DT"
    emp_col = "Emploi"
    missing = [c for c in (cap_col, emp_col) if c not in df.columns]
    if missing:
        raise ValueError(f"CSV must include columns {missing}. Found: {list(df.columns)}")

    df["__cap_num"] = _to_number(df[cap_col]).fillna(0.0)
    df["__emp_num"] = _to_number(df[emp_col]).fillna(0.0)

    z = pd.DataFrame({"cap": df["__cap_num"], "emp": df["__emp_num"]})
    z = (z - z.mean()) / z.std().replace(0, 1)
    df["__credit_index"] = (0.6 * z["cap"] + 0.4 * z["emp"]).fillna(0.0)

    feat = df[["__cap_num", "__emp_num", "__credit_index"]].rename(
        columns={"__cap_num": "Capital", "__emp_num": "Employment", "__credit_index": "CreditIndex"}
    )
    feat = feat[(feat != 0).any(axis=1)]
    if len(feat) < 2:
        raise ValueError("Not enough valid rows for clustering after cleaning.")

  
    k = max(2, min(int(n_clusters), len(feat)))
    X = StandardScaler().fit_transform(feat)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)

    use_idx = feat.index
    df = df.loc[use_idx].copy()
    df["cluster"] = km.labels_

    points = pd.DataFrame({
        "x": df["__cap_num"].astype(float),
        "y": df["__emp_num"].astype(float),
        "z": df["__credit_index"].astype(float),
        "cluster": df["cluster"].astype(int),
    }).to_dict(orient="records")

    summary = (
        df.groupby("cluster")
          .agg(
              Capital_en_DT=("__cap_num", "median"),
              Emploi=("__emp_num", "median") if "__emp_num" in df else ("__emp_num","median"),
              Credit_Worthiness=("__credit_index", "median"),
              Loyalty_Score=("conversion_probability", "mean"),
              Digital_Adoption=("digital_payment_adoption", "mean"),
              Count=("cluster", "count"),
          )
          .reset_index()
          .fillna(0)
    )
    # Fix a possible typo above if needed
    if "Emploi" not in summary.columns and "__emp_num" in df:
        summary.rename(columns={"__emp_num":"Emploi"}, inplace=True)

    return {"points": points, "summary": summary.to_dict(orient="records")}

# ---------- NEW: Scenario engine (swap coefficients with your notebook later) ----------
ScenarioType = Literal[
    "Fermeture d'Agence","Currency Devaluation","Energy Crisis","Political Uncertainty",
    "Digital Transformation","Tourism Recovery","Export Boom","Economic Recovery","Regional Instability","Baseline"
]
Intensity = Literal["Faible","Moyenne","Forte"]
Segment = Literal["Tous les segments","Premium","SME","Mass Market"]
RegionName = Literal["Tunis","Sfax","Sousse","Kairouan","Bizerte","Gabès","Ariana","La Marsa"]

COEFF: Dict[str, Dict[str, float]] = {
    "Fermeture d'Agence":      dict(clients=-0.04, sat=-0.02, churn=+0.03, digital=+0.01, region_bias=+0.5),
    "Currency Devaluation":    dict(clients=-0.02, sat=-0.03, churn=+0.05, digital=+0.00),
    "Energy Crisis":           dict(clients=-0.05, sat=-0.04, churn=+0.06, digital=-0.01),
    "Political Uncertainty":   dict(clients=-0.01, sat=-0.01, churn=+0.02, digital=+0.00),
    "Digital Transformation":  dict(clients=+0.01, sat=+0.01, churn=-0.02, digital=+0.05),
    "Tourism Recovery":        dict(clients=+0.015, sat=+0.01, churn=-0.01, digital=+0.01),
    "Export Boom":             dict(clients=+0.02, sat=+0.015, churn=-0.01, digital=+0.00),
    "Economic Recovery":       dict(clients=+0.01, sat=+0.01, churn=-0.01, digital=+0.00),
    "Regional Instability":    dict(clients=-0.03, sat=-0.02, churn=+0.03, digital=-0.005),
    "Baseline":                dict(clients=0.0, sat=0.0, churn=0.0, digital=0.0),
}
INT_MULT = {"Faible": 0.6, "Moyenne": 1.0, "Forte": 1.5}
REGIONS: List[RegionName] = ["Tunis","Sfax","Sousse","Kairouan","Bizerte","Gabès","Ariana","La Marsa"]

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _baseline() -> dict:
    df = load_df()
    # Build a compact baseline snapshot from the CSV
    total = len(df)
    satisfaction = df["conversion_probability"].mean() if "conversion_probability" in df else 0.85
    digital = df["digital_payment_adoption"].mean() if "digital_payment_adoption" in df else 0.48
    churn = 0.25  # if you have a field, compute it instead
    # region counts (fallback to approx equal if governorate missing)
    reg_counts = df["governorate"].value_counts().reindex(REGIONS).fillna(max(1,total//len(REGIONS))).astype(int).to_dict()
    # segment counts (naive split if business_size missing)
    seg_counts = df["business_size"].value_counts().to_dict()
    for s in ["Premium","SME","Mass Market"]:
        seg_counts.setdefault(s, total//3)
    return dict(
        total_clients=total,
        satisfaction=float(satisfaction),
        churn=float(churn),
        digital=float(digital),
        regions=reg_counts,
        segments={"Premium": seg_counts["Premium"], "SME": seg_counts["SME"], "Mass Market": seg_counts["Mass Market"]},
    )

def simulate(scenario: ScenarioType, intensity: Intensity, segment: Segment,
             region: RegionName, duration_months: int = 6) -> dict:
    base = _baseline()
    c = COEFF[scenario]; m = INT_MULT[intensity]; months = duration_months

    clients_delta_ratio = c["clients"] * m * (months / 6.0)
    sat_delta = c["sat"] * m * (months / 6.0)
    churn_delta = c["churn"] * m * (months / 6.0)
    digital_delta = c["digital"] * m * (months / 6.0)

    total = base["total_clients"]
    diff_clients = round(total * clients_delta_ratio)

    kpis = dict(
        clients=total + diff_clients,
        diff_clients=diff_clients,
        satisfaction=_clamp(base["satisfaction"] + sat_delta, 0.0, 1.0),
        churn_rate=_clamp(base["churn"] + churn_delta, 0.0, 1.0),
        digital_adoption=_clamp(base["digital"] + digital_delta, 0.0, 1.0),
    )

    regional = []
    bias = c.get("region_bias", 0.0)
    for r_name, cur in base["regions"].items():
        weight = 1.0 + (bias if (scenario == "Fermeture d'Agence" and r_name == region) else 0.0)
        d = round(cur * clients_delta_ratio * weight)
        risk = "High" if d < 0 else ("Low" if d > 0 else "Medium")
        regional.append(dict(region=r_name, current_clients=int(cur), delta_clients=int(d), risk=risk))

    segments = []
    rev_per = {"Premium": 26000, "SME": 7000, "Mass Market": 6700}
    for s_name, cur in base["segments"].items():
        if segment != "Tous les segments" and s_name != segment:
            delta = 0
        else:
            seg_multiplier = 1.15 if (s_name == "Premium" and clients_delta_ratio < 0) else 1.0
            delta = round(cur * clients_delta_ratio * seg_multiplier)
        segments.append(dict(
            name=s_name,
            current_clients=int(cur),
            delta_clients=int(delta),
            revenue_impact_tnd=float(delta) * float(rev_per[s_name])
        ))

    return dict(kpis=kpis, regional=regional, segments=segments)

def compare(payload: List[dict]) -> List[dict]:
    base = _baseline()
    base_revenue = 0
    rev_per = {"Premium": 26000, "SME": 7000, "Mass Market": 6700}
    for s_name, cur in base["segments"].items():
        base_revenue += cur * rev_per[s_name]

    out = []
    for p in payload:
        res = simulate(
            scenario=p["scenario"],
            intensity=p.get("intensity","Moyenne"),
            segment=p.get("segment","Tous les segments"),
            region=p.get("region","Sousse"),
            duration_months=p.get("duration_months",6),
        )
        adoption_change = res["kpis"]["digital_adoption"] - base["digital"]
        revenue = base_revenue + sum(seg["revenue_impact_tnd"] for seg in res["segments"])
        revenue_change = (revenue - base_revenue) / base_revenue if base_revenue else 0.0
        out.append(dict(scenario=p["scenario"], adoption_change=adoption_change, revenue_change=revenue_change))
    return out
