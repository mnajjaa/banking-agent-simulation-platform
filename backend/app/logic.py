from functools import lru_cache
from typing import Iterable, List, Optional
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import math

from pathlib import Path
import re

# Resolve data path relative to backend/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "tuniind.csv"

_last_schema_mapping: dict[str, str] = {}

# REQUIRED columns + synonyms + defaults
REQUIRED = {
    "id":                          {"dtype": "string", "syn": ["agent_id", "merchant_id"]},
    "name":                        {"dtype": "string", "syn": ["merchant_name", "agent_name"]},
    "governorate":                 {"dtype": "string", "syn": ["region", "state", "gov"] , "default": "Unknown"},
    "business_size":               {"dtype": "string", "syn": ["size", "segment"],       "default": "SME"},
    "cash_usage_ratio":            {"dtype": "float",  "syn": ["cash_usage","cash_rate","cash_ratio","cash_usage_rate"], "default": 0.5},
    "digital_payment_adoption":    {"dtype": "float",  "syn": ["digital_adoption","digital_ratio","digital_payments","dpa"], "default": 0.5},
}

# if True -> fail fast when a critical field can't be found; set to False to auto-fill defaults
STRICT = True

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _find_column(df: pd.DataFrame, wanted: str, synonyms: list[str]) -> str | None:
    norm_map = { _norm(c): c for c in df.columns }
    # exact or synonym match ignoring case/underscores/spaces
    for key in [wanted, *synonyms]:
        hit = norm_map.get(_norm(key))
        if hit: return hit
    return None

_last_schema_mapping: dict[str, str] = {}

@lru_cache(maxsize=1)
def load_df(path: str | Path = DATA_PATH) -> pd.DataFrame:
    """Load your French CSV and map/produce the fields the app expects."""
    global _last_schema_mapping
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found at {path} (expected backend/data/tuniind.csv)")

    # accents-safe; if you ever get Unicode errors, try encoding='latin1'
    df = pd.read_csv(path, encoding="utf-8-sig")
    mapping = {}

    # name
    if "Dénomination" in df.columns:
        df.rename(columns={"Dénomination": "name"}, inplace=True); mapping["name"] = "Dénomination"
    elif "Raison Sociale" in df.columns:
        df.rename(columns={"Raison Sociale": "name"}, inplace=True); mapping["name"] = "Raison Sociale"
    else:
        df["name"] = ""; mapping["name"] = "[created empty]"

    # governorate
    if "Gouvernorat" in df.columns:
        df.rename(columns={"Gouvernorat": "governorate"}, inplace=True); mapping["governorate"] = "Gouvernorat"
    else:
        df["governorate"] = "Unknown"; mapping["governorate"] = "[created default Unknown]"

    # id (auto sequence if missing)
    if "id" not in df.columns:
        df.insert(0, "id", range(1, len(df) + 1)); mapping["id"] = "[created auto sequence]"

    # business_size placeholder
    if "business_size" not in df.columns:
        df["business_size"] = "SME"; mapping["business_size"] = "[created default SME]"

    # knobs used by scoring (defaults 0.5)
    for col, default in [("cash_usage_ratio", 0.5), ("digital_payment_adoption", 0.5)]:
        if col not in df.columns:
            df[col] = default; mapping[col] = f"[created default {default}]"
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default).clip(0, 1)

    # baseline score if missing
    if "conversion_probability" not in df.columns:
        df["conversion_probability"] = (
            (1 - df["cash_usage_ratio"]) * 0.4 + df["digital_payment_adoption"] * 0.6
        ).clip(0, 1)
        mapping["conversion_probability"] = "[derived (0.4/0.6 blend)]"

    _last_schema_mapping = mapping
    return df

def schema_mapping() -> dict:
    """Optional helper you can expose via an endpoint for debugging."""
    return {"data_path": str(DATA_PATH), "mapping": _last_schema_mapping}
def simulate_campaign(
    template: str = "Baseline",
    w_cash: float = 0.4,
    w_dig: float = 0.6,
    governorates: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    df = load_df().copy()

    # simple template effects (replace with your notebook rules)
    if template == "CashToDigital":
        df["digital_payment_adoption"] = (df["digital_payment_adoption"] + 0.1).clip(0, 1)
    elif template == "LoyaltyBoost":
        df["conversion_probability"] = (df["conversion_probability"] + 0.05).clip(0, 1)
    elif template == "AggressiveRate":
        df["conversion_probability"] = (df["conversion_probability"] + 0.08).clip(0, 1)

    # main scoring knobs
    df["conversion_probability"] = (
        (1 - df["cash_usage_ratio"]) * float(w_cash)
        + df["digital_payment_adoption"] * float(w_dig)
    ).clip(0, 1)

    if governorates:
        df = df[df["governorate"].isin(list(governorates))]

    gov = (
        df.groupby("governorate")["conversion_probability"]
          .mean().reset_index()
          .sort_values("conversion_probability", ascending=False)
    )
    return gov

def top_prospects(threshold: float = 0.7, limit: int = 100) -> pd.DataFrame:
    df = load_df().copy()
    # ensure we have a score:
    if "conversion_probability" not in df.columns:
        df["conversion_probability"] = (
            (1 - df["cash_usage_ratio"]) * 0.4
            + df["digital_payment_adoption"] * 0.6
        ).clip(0, 1)
    return (
        df[df["conversion_probability"] >= float(threshold)]
          .sort_values("conversion_probability", ascending=False)
          .head(limit)[["id", "name", "governorate", "business_size", "conversion_probability"]]
    )

def explain_decision(agent_id: str) -> List[str]:
    df = load_df()
    sub = df[df["id"].astype(str) == str(agent_id)]
    if sub.empty:
        return ["Agent not found."]
    r = sub.iloc[0]
    trace = []
    trace.append(
        "High cash usage → lower conversion" if r.get("cash_usage_ratio",0) > 0.7
        else ("Moderate cash usage → slight penalty" if r.get("cash_usage_ratio",0) > 0.5
              else "Low cash usage → neutral/positive")
    )
    trace.append(
        "Strong digital adoption → higher conversion" if r.get("digital_payment_adoption",0) > 0.6
        else ("Moderate digital adoption → small boost" if r.get("digital_payment_adoption",0) > 0.4
              else "Low digital adoption → small penalty")
    )
    return trace

def _to_number(s: pd.Series) -> pd.Series:
    # French formats: spaces/NBSP as thousands, comma as decimal; strip text like " DT"
    x = s.astype(str)
    x = x.str.replace("\u00A0", "", regex=False).str.replace("\u202F", "", regex=False).str.replace(" ", "", regex=False)
    x = x.str.replace(",", ".", regex=False)
    x = x.str.replace(r"[^0-9.\-]", "", regex=True)
    x = x.str.replace(r"(\.)(?=.*\.)", "", regex=True)  # keep last dot only
    return pd.to_numeric(x, errors="coerce")

def segment_customers(n_clusters: int = 4):
    df = load_df().copy()

    cap_col = "Capital en DT"
    emp_col = "Emploi"
    missing = [c for c in (cap_col, emp_col) if c not in df.columns]
    if missing:
        raise ValueError(f"CSV must include columns {missing}. Found: {list(df.columns)}")

    # sanitize to numeric and keep as explicit numeric columns for later aggregations
    df["__cap_num"] = _to_number(df[cap_col]).fillna(0.0)
    df["__emp_num"] = _to_number(df[emp_col]).fillna(0.0)

    # proxy credit index from standardized cap/emp
    z = pd.DataFrame({"cap": df["__cap_num"], "emp": df["__emp_num"]})
    z = (z - z.mean()) / z.std().replace(0, 1)
    df["__credit_index"] = (0.6 * z["cap"] + 0.4 * z["emp"]).fillna(0.0)

    # features for clustering
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

    # 3D points
    points = pd.DataFrame({
        "x": df["__cap_num"].astype(float),
        "y": df["__emp_num"].astype(float),
        "z": df["__credit_index"].astype(float),
        "cluster": df["cluster"].astype(int),
    }).to_dict(orient="records")

    # summary (use the numeric columns for medians)
    summary = (
        df.groupby("cluster")
          .agg(
              Capital_en_DT=("__cap_num", "median"),
              Emploi=("__emp_num", "median"),
              Credit_Worthiness=("__credit_index", "median"),
              Loyalty_Score=("conversion_probability", "mean"),
              Digital_Adoption=("digital_payment_adoption", "mean"),
              Count=("cluster", "count"),
          )
          .reset_index()
          .fillna(0)
    )

    return {"points": points, "summary": summary.to_dict(orient="records")}
    df = load_df().copy()

    cap_col = "Capital en DT"
    emp_col = "Emploi"
    missing = [c for c in (cap_col, emp_col) if c not in df.columns]
    if missing:
        raise ValueError(f"CSV must include columns {missing}. Found: {list(df.columns)}")

    cap = _to_number(df[cap_col]).fillna(0.0)
    emp = _to_number(df[emp_col]).fillna(0.0)

    # proxy credit index (z-scores of cap/emp)
    z = pd.DataFrame({"cap": cap, "emp": emp})
    z = (z - z.mean()) / z.std().replace(0, 1)
    credit_idx = (0.6 * z["cap"] + 0.4 * z["emp"]).fillna(0.0)

    feat = pd.DataFrame({"Capital": cap, "Employment": emp, "CreditIndex": credit_idx})
    feat = feat[(feat != 0).any(axis=1)]
    if len(feat) < 2:
        raise ValueError("Not enough valid rows for clustering after cleaning.")

    k = max(2, min(int(n_clusters), len(feat)))
    X = StandardScaler().fit_transform(feat)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)

    # attach clusters to the same filtered rows
    use_idx = feat.index
    df = df.loc[use_idx].copy()
    df["cluster"] = km.labels_
    df["__credit_index"] = credit_idx.loc[use_idx]

    points = pd.DataFrame({
        "x": cap.loc[use_idx].astype(float),
        "y": emp.loc[use_idx].astype(float),
        "z": credit_idx.loc[use_idx].astype(float),
        "cluster": df["cluster"].astype(int),
    }).to_dict(orient="records")

    summary = (
        df.groupby("cluster")
          .agg(
              Capital_en_DT=(cap_col, "median"),
              Emploi=(emp_col, "median"),
              Credit_Worthiness=("__credit_index", "median"),
              Loyalty_Score=("conversion_probability", "mean"),
              Digital_Adoption=("digital_payment_adoption", "mean"),
              Count=("cluster", "count"),
          )
          .reset_index()
          .fillna(0)
    )

    return {"points": points, "summary": summary.to_dict(orient="records")}
    df = load_df().copy()

    # your actual numeric columns
    cap_col = "Capital en DT"
    emp_col = "Emploi"

    missing = [c for c in (cap_col, emp_col) if c not in df.columns]
    if missing:
        raise ValueError(f"CSV must include columns {missing}. Found: {list(df.columns)}")

    # numeric features
    num = df[[cap_col, emp_col]].apply(pd.to_numeric, errors="coerce").fillna(0)

    # simple proxy “credit index” from capital & employment
    z = (num - num.mean()) / num.std().replace(0, 1)
    df["__credit_index"] = (0.6 * z[cap_col] + 0.4 * z[emp_col]).fillna(0)

    # features for clustering
    feat = pd.DataFrame({
        "Capital": num[cap_col],
        "Employment": num[emp_col],
        "CreditIndex": df["__credit_index"],
    })

    # avoid degenerate tiny datasets
    feat = feat[(feat != 0).any(axis=1)]
    if len(feat) < 2:
        raise ValueError("Not enough valid rows for clustering. Check numeric values in CSV.")

    k = max(2, min(int(n_clusters), len(feat)))
    X = StandardScaler().fit_transform(feat)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    labels = pd.Series(km.labels_, index=feat.index, name="cluster")

    df = df.join(labels, how="right")

    # 3D scatter points (x: Capital, y: Employment, z: proxy credit index)
    points = pd.DataFrame({
        "x": df[cap_col].astype(float),
        "y": df[emp_col].astype(float),
        "z": df["__credit_index"].astype(float),
        "cluster": df["cluster"].astype(int),
    }).to_dict(orient="records")

    # summary table like your screenshot
    summary = (
        df.groupby("cluster")
          .agg(
              Capital_en_DT=(cap_col, "median"),
              Emploi=(emp_col, "median"),
              Credit_Worthiness=("__credit_index", "median"),
              Loyalty_Score=("conversion_probability", "mean"),
              Digital_Adoption=("digital_payment_adoption", "mean"),
              Count=("cluster", "count"),
          )
          .reset_index()
          .fillna(0)
    )

    return {"points": points, "summary": summary.to_dict(orient="records")}
    df = load_df().copy()

    # helper to find a column among synonyms (case/space/underscore-insensitive)
    def pick(names: list[str]) -> str | None:
        cmap = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
        for n in names:
            key = n.lower().replace(" ", "").replace("_", "")
            if key in cmap:
                return cmap[key]
        return None

    col_cap   = pick(["capital_en_dt","capital","cap","capitaldt","capital_dt"])
    col_emp   = pick(["emploi","employment","employees","headcount","jobs"])
    col_score = pick(["credit_worthiness","credit_score","creditworthiness","creditscore"])

    if not all([col_cap, col_emp, col_score]):
        raise ValueError(
            "Required numeric columns not found. "
            "Need capital, employment, credit score. "
            f"CSV columns: {list(df.columns)}"
        )

    # numeric features, drop rows without enough data
    num = df[[col_cap, col_emp, col_score]].apply(pd.to_numeric, errors="coerce").dropna()
    if num.empty:
        raise ValueError("No valid numeric rows after cleaning (check your CSV values).")

    # clamp k to the available rows (and at least 2)
    k = max(2, min(int(n_clusters), len(num)))

    X = StandardScaler().fit_transform(num)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)

    # attach labels back to original rows
    labels = pd.Series(km.labels_, index=num.index, name="cluster")
    df = df.join(labels, how="right")

    # points for 3D scatter
    points = (
        df[[col_cap, col_emp, col_score, "cluster"]]
        .rename(columns={col_cap: "x", col_emp: "y", col_score: "z"})
        .to_dict(orient="records")
    )

    # summary table (use existing columns if present)
    loyalty_col = "conversion_probability" if "conversion_probability" in df.columns else col_score
    digi_col = "digital_payment_adoption" if "digital_payment_adoption" in df.columns else col_score

    summary = (
        df.groupby("cluster")
          .agg(
              Capital_en_DT=(col_cap, "median"),
              Emploi=(col_emp, "median"),
              Credit_Worthiness=(col_score, "median"),
              Loyalty_Score=(loyalty_col, "mean"),
              Digital_Adoption=(digi_col, "mean"),
              Count=("cluster", "count"),
          )
          .reset_index()
          .fillna(0)
    )

    return {"points": points, "summary": summary.to_dict(orient="records")}