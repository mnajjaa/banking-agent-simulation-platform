# Banking Agent Simulation Platform

An interactive **what-if simulator** for banking teams. Model customer behavior across regions and segments, compare multiple macro scenarios side-by-side, and visualize operational risk and revenue impact.

## ✨ Features

- **Create Scenario** – configure intensity, target segment, region, and duration. Sticky config panel, instant default run, KPI cards with deltas.
- **Compare Scenarios** – portfolio view (Revenue change vs Adoption change), radar scorecard (Retention/Churn toggle), segment revenue impact chart with segment switcher, regional risk insights.
- **Beautiful UI** – React + Vite + Tailwind, Recharts & ApexCharts, sticky side panels, and template-consistent components.

---

## 🧱 Tech Stack

**Backend**
- FastAPI (Python)
- Uvicorn
- NumPy / Pandas (simple data transforms)

**Frontend**
- React + Vite + TypeScript
- TailwindCSS
- Recharts & ApexCharts
- Axios

---

## 🧰 Prerequisites (versions)

- **Python:** `3.10+` (tested with **3.11.x**)
- **Node.js:** **20 LTS** recommended (supports `>= 18`); **npm 9+**



---

## ⚙️ Setup

### 1) Backend (Python 3.10+)

```bash
cd backend
python -m venv .venv
# activate:
#  - Windows: .venv\Scripts\activate

pip install -r requirements.txt  # if present
# or minimal set:
pip install fastapi uvicorn pandas numpy

# Run the API
uvicorn app.main:app --reload --port 8000
# Docs → http://localhost:8000/docs
```

### 2) Frontend (Node 20 LTS / >=18)

```bash
cd frontendd
npm i
# set API URL used by src/lib/api.ts
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev  # http://localhost:5173
```

---



## 🔌 API Reference

### POST `/simulate`

Simulates one scenario and returns KPIs, regional impact, and segment impact.



### POST `/compare`

Compares multiple scenarios against the baseline and returns changes vs baseline.



> The frontend augments `/compare` by calling `/simulate` for each scenario to compute additional metrics (retention, satisfaction) and visualizations (segments/regions).

### (Optional) `/segments`

If enabled in your backend, `POST /segments` clusters customers; it expects:


---

## 🖥️ Frontend Pages

- **Scenarios → Create Scenario**  
  Sticky config, auto-run defaults, KPI cards (with deltas vs baseline), regional bar, segment revenue donut, regional table, segment cards.
- **Scenarios → Compare Scenarios**  
  Portfolio View (Revenue change vs Adoption change) with quadrant tints.  
  Radar scorecard (Retention ↔ Churn switch).  
  Segment revenue impact (single chart with toggle for Premium / SME / Mass Market).  
  Sticky Options + Insights panel.

---

## 🔧 Environment Variables

**Frontend (`frontendd/.env`)**
```
VITE_API_URL=http://localhost:8000
```

**Backend (`backend/.env`)**
```
PORT=8000
CORS_ORIGINS=http://localhost:5173
```

---

## 🧪 Quick cURL

```bash
curl -X POST http://localhost:8000/simulate   -H "Content-Type: application/json"   -d '{"scenario":"Fermeture d'''Agence","intensity":"Moyenne","segment":"Tous les segments","region":"Sousse","duration_months":6}'

curl -X POST http://localhost:8000/compare   -H "Content-Type: application/json"   -d '{"scenarios":[{"scenario":"Fermeture d'''Agence","intensity":"Moyenne","segment":"Tous les segments","region":"Sousse","duration_months":6}] }'
```

---






