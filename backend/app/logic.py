# ---------- Imports ----------
from functools import lru_cache
from typing import Iterable, List, Optional, Dict, Literal
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import math
from pathlib import Path
import re

# AgentPy (optional at import-time; friendly error if missing when used)
try:
    import agentpy as ap
    _AGENTPY_AVAILABLE = True
except Exception as _e:
    ap = None
    _AGENTPY_AVAILABLE = False
    _AGENTPY_IMPORT_ERROR = _e

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

    # --- Standardize name ---
    if "Dénomination" in df.columns:
        df.rename(columns={"Dénomination": "name"}, inplace=True); mapping["name"] = "Dénomination"
    elif "Raison Sociale" in df.columns:
        df.rename(columns={"Raison Sociale": "name"}, inplace=True); mapping["name"] = "Raison Sociale"
    else:
        df["name"] = ""; mapping["name"] = "[created empty]"

    # --- Standardize governorate ---
    if "Gouvernorat" in df.columns:
        df.rename(columns={"Gouvernorat": "governorate"}, inplace=True); mapping["governorate"] = "Gouvernorat"
    else:
        df["governorate"] = "Unknown"; mapping["governorate"] = "[created default Unknown]"

    # --- Ensure ID ---
    if "id" not in df.columns:
        df.insert(0, "id", range(1, len(df) + 1)); mapping["id"] = "[created auto sequence]"

    # --- Business size heuristic from employment ---
    if "Emploi" in df.columns:
        df["business_size"] = pd.to_numeric(df["Emploi"], errors="coerce").fillna(0).apply(
            lambda x: "micro" if x < 50 else ("SME" if x < 250 else "large")
        )
        mapping["business_size"] = "derived from Emploi"
    else:
        df["business_size"] = "SME"; mapping["business_size"] = "[created default SME]"

    # --- Derive cash_usage_ratio ---
    def estimate_cash_usage(row):
        secteur = str(row.get("Secteur", "")).lower()
        size = row.get("business_size", "SME")
        val = 0.5
        if size == "micro": val += 0.2
        if size == "large": val -= 0.2
        if "agric" in secteur or "textile" in secteur or "commerce" in secteur:
            val += 0.2
        if "finance" in secteur or "banque" in secteur or "télécom" in secteur or "tech" in secteur:
            val -= 0.2
        return max(0, min(1, val))

    if "cash_usage_ratio" not in df.columns:
        df["cash_usage_ratio"] = df.apply(estimate_cash_usage, axis=1)
        mapping["cash_usage_ratio"] = "heuristic from Secteur + business_size"

    # --- Derive digital_payment_adoption ---
    def estimate_digital_adoption(row):
        secteur = str(row.get("Secteur", "")).lower()
        size = row.get("business_size", "SME")
        foreign = str(row.get("Pays du Participant \n    Etranger", "")).strip()
        val = 0.5
        if size == "large": val += 0.2
        if "finance" in secteur or "banque" in secteur or "télécom" in secteur or "tech" in secteur:
            val += 0.3
        if foreign and foreign.lower() not in ["", "nan"]:
            val += 0.1
        return max(0, min(1, val))

    if "digital_payment_adoption" not in df.columns:
        df["digital_payment_adoption"] = df.apply(estimate_digital_adoption, axis=1)
        mapping["digital_payment_adoption"] = "heuristic from Secteur + size + foreign participation"

    # --- Derived conversion probability ---
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
    km = KMeans(n_init=10, n_clusters=k, random_state=42).fit(X)

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
    if "Emploi" not in summary.columns and "__emp_num" in df:
        summary.rename(columns={"__emp_num":"Emploi"}, inplace=True)

    return {"points": points, "summary": summary.to_dict(orient="records")}

# ---------- Scenario engine ----------
ScenarioType = Literal[
    "Fermeture d'Agence","Currency Devaluation","Energy Crisis","Political Uncertainty",
    "Digital Transformation","Tourism Recovery","Export Boom","Economic Recovery","Regional Instability","Baseline"
]
Intensity = Literal["Faible","Moyenne","Forte"]
Segment = Literal["Tous les segments","Premium","SME","Mass Market"]
RegionName = Literal[  "Tunis","Ariana","Ben Arous","Manouba",
    "Nabeul","Zaghouan","Bizerte","Beja","Jendouba","Kef","Siliana",
    "Sousse","Monastir","Mahdia","Kairouan","Kasserine","Sidi Bouzid",
    "Sfax","Gabes","Medenine","Tataouine",
    "Gafsa","Tozeur","Kebili"]

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
REGIONS: List[RegionName] = [
    "Tunis","Ariana","Ben Arous","Manouba",
    "Nabeul","Zaghouan","Bizerte","Beja","Jendouba","Kef","Siliana",
    "Sousse","Monastir","Mahdia","Kairouan","Kasserine","Sidi Bouzid",
    "Sfax","Gabes","Medenine","Tataouine",
    "Gafsa","Tozeur","Kebili"
]

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _baseline() -> dict:
    df = load_df()
    total = len(df)
    satisfaction = df["conversion_probability"].mean() if "conversion_probability" in df else 0.85
    digital = df["digital_payment_adoption"].mean() if "digital_payment_adoption" in df else 0.48
    churn = 0.25
    reg_counts = df["governorate"].value_counts().reindex(REGIONS).fillna(max(1,total//len(REGIONS))).astype(int).to_dict()
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

# ---- Churn severity knobs ----
CHURN_SEVERITY = 2.0  # increase to make churn swings more violent
SEG_CHURN_ELASTICITY = {"Premium": 0.7, "SME": 1.0, "Mass Market": 1.3}  # Premium stickier, Mass more fragile
REGIONAL_CHURN_MULT = 1.5  # extra churn sensitivity in targeted region for certain scenarios
DIGITAL_SHIELD = 0.60      # above this average digital adoption, churn impact is dampened

def _population_means() -> dict[str, float]:
    df = load_df()
    avg_cash = float(df["cash_usage_ratio"].mean()) if "cash_usage_ratio" in df else 0.5
    avg_dig  = float(df["digital_payment_adoption"].mean()) if "digital_payment_adoption" in df else 0.5
    return {"avg_cash": avg_cash, "avg_dig": avg_dig}

def simulate(scenario: ScenarioType, intensity: Intensity, segment: Segment,
             region: RegionName, duration_months: int = 6) -> dict:
    base = _baseline()
    c = COEFF[scenario]; m = INT_MULT[intensity]; months = duration_months

    # --- clients / sat / digital (unchanged shape) ---
    clients_delta_ratio = c["clients"] * m * (months / 6.0)
    sat_delta = c["sat"] * m * (months / 6.0)
    digital_delta = c["digital"] * m * (months / 6.0)

    total = base["total_clients"]
    diff_clients = round(total * clients_delta_ratio)

    # --- SEVERE CHURN CALC ---
    pop = _population_means()
    base_churn = base["churn"]

    # raw churn impulse from scenario, scaled hard
    churn_impulse = c["churn"] * m * (months / 6.0) * CHURN_SEVERITY

    # behavior coupling: more cash -> more churn; more digital -> less churn (centered at 0.5)
    behavior_adj = 1.0 + 0.6 * (pop["avg_cash"] - 0.5) - 0.6 * (pop["avg_dig"] - 0.5)

    # digital shield dampens positive spikes
    if pop["avg_dig"] >= DIGITAL_SHIELD and churn_impulse > 0:
        churn_impulse *= 0.7

    severe_churn = _clamp(base_churn + churn_impulse * behavior_adj, 0.0, 1.0)

    kpis = dict(
        clients=total + diff_clients,
        diff_clients=diff_clients,
        satisfaction=_clamp(base["satisfaction"] + sat_delta, 0.0, 1.0),
        churn_rate=severe_churn,
        digital_adoption=_clamp(base["digital"] + digital_delta, 0.0, 1.0),
    )

    # --- Regional view with churn shock on targeted region for stress scenarios ---
    regional = []
    bias = c.get("region_bias", 0.0)
    for r_name, cur in base["regions"].items():
        weight = 1.0 + (bias if (scenario == "Fermeture d'Agence" and r_name == region) else 0.0)
        d = round(cur * clients_delta_ratio * weight)

        reg_churn_mult = 1.0
        if scenario in ("Fermeture d'Agence", "Regional Instability") and r_name == region:
            reg_churn_mult = REGIONAL_CHURN_MULT

        local_churn = _clamp(severe_churn * reg_churn_mult, 0.0, 1.0)
        if d < 0 or local_churn > 0.35:
            risk = "High"
        elif local_churn < 0.18 and d >= 0:
            risk = "Low"
        else:
            risk = "Medium"

        regional.append(dict(region=r_name, current_clients=int(cur), delta_clients=int(d), risk=risk))

    # --- Segments with churn elasticity (affects how fragile each segment is) ---
    segments = []
    rev_per = {"Premium": 26000, "SME": 7000, "Mass Market": 6700}
    for s_name, cur in base["segments"].items():
        if segment != "Tous les segments" and s_name != segment:
            delta = 0
            seg_churn = severe_churn
        else:
            seg_el = SEG_CHURN_ELASTICITY.get(s_name, 1.0)
            seg_multiplier = 1.15 if (s_name == "Premium" and clients_delta_ratio < 0) else 1.0
            delta = round(cur * clients_delta_ratio * seg_multiplier)
            seg_churn = _clamp(severe_churn * seg_el, 0.0, 1.0)

        segments.append(dict(
            name=s_name,
            current_clients=int(cur),
            delta_clients=int(delta),
            revenue_impact_tnd=float(delta) * float(rev_per[s_name]),
            # churn_rate=seg_churn  # uncomment if you want to expose per-segment churn
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

# ---------- ABM with AgentPy (minimal change; additive only) ----------
if _AGENTPY_AVAILABLE:

    class RetailerAgent(ap.Agent):
        """Retailer/merchant agent with a simple monthly drift on conversion_probability."""
        def setup(self):
            # attributes will be set by the model after creation
            pass

        def step(self):
            # Drift driven by scenario intensity; slight bias if already digital-friendly
            drift = self.model.step_drift  # small signed float per step
            bias = 0.01 if getattr(self, "digital_payment_adoption", 0.5) > 0.6 else 0.0
            cp = getattr(self, "conversion_probability", 0.5)
            cp = max(0.0, min(1.0, cp + drift + bias))
            self.conversion_probability = cp  # update in-place

    class BankingModel(ap.Model):
        """Minimal ABM around your CSV, using AgentPy."""
        def setup(self):
            # Read params
            scenario = self.p.get("scenario", "Baseline")
            intensity = self.p.get("intensity", "Moyenne")
            steps = int(self.p.get("steps", 6))
            seed = int(self.p.get("seed", 42))

            # Translate scenario to per-step drift (use satisfaction delta as proxy)
            c = COEFF.get(scenario, COEFF["Baseline"])
            m = INT_MULT.get(intensity, 1.0)
            # assume 6 months baseline for coefficients; scale to desired steps
            monthly_sat_delta = c["sat"] * m  # per 6 months originally
            # make per-step drift small enough to not saturate quickly
            self.step_drift = (monthly_sat_delta / 4.0)  # ~ per month

            # Load agents from CSV
            df = load_df().copy()
            n = len(df)
            self.df_index = df.index.to_list()

            # Create AgentList and assign attributes
            self.agents = ap.AgentList(self, n, RetailerAgent)
            for agent, (_, row) in zip(self.agents, df.iterrows()):
                agent.id_str = str(row.get("id", ""))
                agent.name = str(row.get("name", ""))
                agent.governorate = str(row.get("governorate", "Unknown"))
                agent.business_size = str(row.get("business_size", "SME"))
                agent.cash_usage_ratio = float(row.get("cash_usage_ratio", 0.5) or 0.0)
                agent.digital_payment_adoption = float(row.get("digital_payment_adoption", 0.5) or 0.0)
                agent.conversion_probability = float(row.get("conversion_probability", 0.5) or 0.0)

            self.kpis = {}  # will be filled in end()

        def step(self):
            # Random order each step for micro-stochasticity
            self.agents.shuffle()
            self.agents.step()

        def end(self):
            # Compute KPIs at the end similar to your baseline
            n = len(self.agents)
            if n == 0:
                self.kpis = dict(total_clients=0, satisfaction=0.0, digital=0.0, churn=0.0)
                return
            avg_conv = sum(a.conversion_probability for a in self.agents) / n
            avg_dig = sum(a.digital_payment_adoption for a in self.agents) / n
            # churn proxy: steeper slope vs conversion & digital (more severe)
            churn = _clamp(0.35 - 1.60 * (avg_conv - 0.5) - 0.30 * (avg_dig - 0.5), 0.0, 1.0)
            self.kpis = dict(total_clients=n, satisfaction=float(avg_conv), digital=float(avg_dig), churn=float(churn))

    def run_abm_preview(scenario: ScenarioType = "Baseline",
                        intensity: Intensity = "Moyenne",
                        steps: int = 6,
                        seed: int = 42) -> dict:
        """Run the AgentPy model quickly and return KPIs."""
        pars = dict(scenario=scenario, intensity=intensity, steps=int(steps), seed=int(seed))
        model = BankingModel(pars)
        # AgentPy's Model has .run() which calls setup/step/end using self.p.steps iterations
        model.run()
        return model.kpis

    def simulate_with_abm(scenario: ScenarioType, intensity: Intensity, segment: Segment,
                          region: RegionName, duration_months: int = 6, seed: int = 42) -> dict:
        """Deterministic simulate + ABM preview bundled."""
        det = simulate(scenario, intensity, segment, region, duration_months)
        abm = run_abm_preview(scenario=scenario, intensity=intensity, steps=duration_months, seed=seed)
        det["abm_preview"] = abm
        return det

else:
    # AgentPy not available: provide friendly error functions so the API doesn't crash at import
    def run_abm_preview(*args, **kwargs):
        raise ImportError(
            "AgentPy is not installed. Install it with:\n"
            "    python -m pip install agentpy\n"
            f"Original import error: {_AGENTPY_IMPORT_ERROR!r}"
        )

    def simulate_with_abm(*args, **kwargs):
        raise ImportError(
            "AgentPy is not installed. Install it with:\n"
            "    python -m pip install agentpy\n"
            f"Original import error: {_AGENTPY_IMPORT_ERROR!r}"
        )
