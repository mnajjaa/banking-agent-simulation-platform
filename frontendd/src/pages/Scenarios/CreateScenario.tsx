import { useEffect, useMemo, useState } from "react";
import PageMeta from "../../components/common/PageMeta";
import ComponentCard from "../../components/common/ComponentCard";
import Button from "../../components/ui/button/Button";
import Badge from "../../components/ui/badge/Badge";
import Chart from "react-apexcharts";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  GroupIcon,
  BoxIconLine,
} from "../../icons";
import { simulate, type SimRequest } from "../../lib/api";

const REGIONS = ["Tunis","Sfax","Sousse","Kairouan","Bizerte","Gabès","Ariana","La Marsa"] as const;
const SCENARIOS = [
  "Fermeture d'Agence","Currency Devaluation","Energy Crisis",
  "Political Uncertainty","Digital Transformation","Tourism Recovery",
  "Export Boom","Economic Recovery","Regional Instability","Baseline",
] as const;

const DEFAULT_CONF: SimRequest = {
  scenario: "Fermeture d'Agence",
  intensity: "Moyenne",
  segment: "Tous les segments",
  region: "Sousse",
  duration_months: 6,
};

export default function CreateScenario() {
  const [conf, setConf] = useState<SimRequest>({ ...DEFAULT_CONF });
  const [res, setRes] = useState<any>(null);
  const [base, setBase] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // auto-run defaults
  useEffect(() => { runSim(); /* eslint-disable-next-line */ }, []);

  const runSim = async () => {
    setLoading(true);
    try {
      // compute baseline with same parameters but scenario "Baseline"
      const [b, s] = await Promise.all([
        simulate({ ...conf, scenario: "Baseline" }),
        simulate(conf),
      ]);
      setBase(b.data);
      setRes(s.data);
    } finally { setLoading(false); }
  };

  const resetAll = async () => {
    setConf({ ...DEFAULT_CONF });
    const [b, s] = await Promise.all([
      simulate({ ...DEFAULT_CONF, scenario: "Baseline" }),
      simulate(DEFAULT_CONF),
    ]);
    setBase(b.data);
    setRes(s.data);
  };

  // Slider cosmetics
  const min = 1, max = 24;
  const pctFill = useMemo(() => ((conf.duration_months - min) / (max - min)) * 100, [conf.duration_months]);
  const setMonths = (m: number) => setConf(c => ({ ...c, duration_months: Math.min(max, Math.max(min, m)) }));

  // helpers
  const fmtPct = (v:number) => (v*100).toFixed(1) + "%";
  const num = (n:number) => Intl.NumberFormat().format(n);

  // ===== KPI cards (styled like template) =====
  const kpis = useMemo(() => {
    if (!res || !base) return [];
    const k = res.kpis;
    const kb = base.kpis;
    return [
      {
        title: "Clients",
        value: num(k.clients),
        deltaText: (k.diff_clients>=0?"+":"") + num(k.diff_clients),
        goodWhenHigher: true,
        icon: <GroupIcon className="size-6 text-gray-800 dark:text-white/90" />,
      },
      {
        title: "Satisfaction",
        value: fmtPct(k.satisfaction),
        delta: (k.satisfaction - kb.satisfaction),
        goodWhenHigher: true,
        icon: <BoxIconLine className="size-6 text-gray-800 dark:text-white/90" />,
      },
      {
        title: "Taux de Churn",
        value: fmtPct(k.churn_rate),
        delta: (k.churn_rate - kb.churn_rate), // lower is better
        goodWhenHigher: false,
        icon: <BoxIconLine className="size-6 text-gray-800 dark:text-white/90" />,
      },
      {
        title: "Digital",
        value: fmtPct(k.digital_adoption),
        delta: (k.digital_adoption - kb.digital_adoption),
        goodWhenHigher: true,
        icon: <BoxIconLine className="size-6 text-gray-800 dark:text-white/90" />,
      },
    ];
  }, [res, base]);

  // ===== Regional bar (Δ clients) =====
  const regional = useMemo(() => {
    if (!res) return { cats: [], vals: [], colors: [] as string[] };
    const rows = [...res.regional]; // [{region, delta_clients, ...}]
    // sort by magnitude (biggest hits first)
    rows.sort((a:any,b:any)=>Math.abs(b.delta_clients)-Math.abs(a.delta_clients));
    const cats = rows.map((r:any)=>r.region);
    const vals = rows.map((r:any)=>r.delta_clients);
    const colors = vals.map((v:number)=> v<0 ? "#ef4444" : "#16a34a");
    return { cats, vals, colors };
  }, [res]);

  const regionalOptions = useMemo(() => ({
    chart: { type: "bar", fontFamily: "Outfit, sans-serif", toolbar: { show: false } },
    plotOptions: { bar: { horizontal: true, borderRadius: 6, distributed: true } },
    colors: regional.colors,
    grid: { xaxis: { lines: { show: true } } },
    dataLabels: { enabled: false },
    xaxis: {
      categories: regional.cats,
      axisBorder: { show: false }, axisTicks: { show: false },
      labels: { formatter: (v:number)=> num(v) },
    },
    tooltip: { x: { show: true }, y: { formatter: (v:number)=> num(v) + " clients" } },
    annotations: { xaxis: [{ x: 0, borderColor: "#9ca3af", strokeDashArray: 4 }] },
  }), [regional]);

  // ===== Segment donut (abs TND) =====
  const segDonut = useMemo(() => {
    if (!res) return { labels: [], data: [] as number[] };
    const s = res.segments || [];
    const labels = s.map((r:any)=>r.name);
    const data = s.map((r:any)=>Math.abs(r.revenue_impact_tnd||0));
    return { labels, data };
  }, [res]);

  const segDonutOpts = useMemo(() => ({
    chart: { type: "donut", fontFamily: "Outfit, sans-serif", toolbar: { show: false } },
    labels: segDonut.labels,
    colors: ["#465FFF","#16a34a","#f59e0b","#7c3aed","#0ea5e9"],
    legend: { position: "bottom" as const },
    dataLabels: { enabled: false },
    tooltip: { y: { formatter: (v:number)=> num(v) + " TND" } },
  }), [segDonut]);

  return (
    <>
      <PageMeta title="Create Scenario" description="Build and run a what-if scenario" />
      <div className="grid grid-cols-12 gap-4 md:gap-6">
        {/* ===== Sticky Config ===== */}
        <div className="col-span-12 xl:col-span-4">
          <div className="xl:sticky xl:top-24 xl:max-h-[calc(100vh-6rem)] xl:overflow-auto xl:pb-2">
            <ComponentCard title="Configuration du Scénario">
              <label className="text-sm">Type de Scénario</label>
              <select className="input" value={conf.scenario}
                onChange={(e)=>setConf({...conf, scenario: e.target.value as any})}>
                {SCENARIOS.map(s => <option key={s}>{s}</option>)}
              </select>

              <label className="text-sm">Intensité</label>
              <select className="input" value={conf.intensity}
                onChange={(e)=>setConf({...conf, intensity: e.target.value as any})}>
                {["Faible","Moyenne","Forte"].map(i => <option key={i}>{i}</option>)}
              </select>

              <label className="text-sm">Segment Ciblé</label>
              <select className="input" value={conf.segment}
                onChange={(e)=>setConf({...conf, segment: e.target.value as any})}>
                {["Tous les segments","Premium","SME","Mass Market"].map(i => <option key={i}>{i}</option>)}
              </select>

              <label className="text-sm">Région</label>
              <select className="input" value={conf.region}
                onChange={(e)=>setConf({...conf, region: e.target.value as any})}>
                {REGIONS.map(r => <option key={r}>{r}</option>)}
              </select>

              {/* Enhanced slider */}
              <div className="flex items-center justify-between mt-2 mb-1">
                <span className="text-sm">Durée (mois)</span>
                <span className="text-xs rounded-full px-2 py-0.5 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
                  {conf.duration_months} mois
                </span>
              </div>

              <div className="relative">
                {/* value bubble */}
                <div
                  className="absolute -top-6 translate-x-[-50%] text-xs px-2 py-0.5 rounded-md bg-gray-800 text-white dark:bg-gray-200 dark:text-gray-900"
                  style={{ left: `calc(${pctFill}% + 8px)` }}
                >
                  {conf.duration_months}
                </div>

                <input
                  type="range"
                  min={min}
                  max={max}
                  value={conf.duration_months}
                  onChange={(e)=>setMonths(+e.target.value)}
                  className="range w-full"
                  style={{
                    background: `linear-gradient(90deg, var(--c-active) ${pctFill}%, var(--c-track) ${pctFill}%)`,
                  }}
                />
                {/* ticks */}
                <div className="mt-1 flex justify-between text-[10px] text-gray-500">
                  <span>1</span><span>6</span><span>12</span><span>18</span><span>24</span>
                </div>
              </div>

              {/* quick picks */}
              <div className="flex flex-wrap gap-2 mt-3">
                {[3,6,12,24].map(n => (
                  <Button key={n} variant={conf.duration_months===n ? "primary" : "outline"} size="sm" onClick={()=>setMonths(n)}>
                    {n}m
                  </Button>
                ))}
              </div>

              <div className="flex gap-3 mt-4">
                <Button variant="primary" size="md" startIcon={<BoxIconLine className="size-5" />} onClick={runSim} disabled={loading}>
                  Lancer la Simulation
                </Button>
                <Button variant="outline" size="md" onClick={resetAll}>Réinitialiser</Button>
              </div>
            </ComponentCard>
          </div>
        </div>

        {/* ===== Results ===== */}
        <div className="col-span-12 xl:col-span-8 space-y-4">
          {res && base && (
            <>
              {/* KPI metrics row (template look) */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 lg:grid-cols-4">
                {kpis.map((m, idx) => (
                  <div key={idx} className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] md:p-6">
                    <div className="flex items-center justify-center w-12 h-12 bg-gray-100 rounded-xl dark:bg-gray-800">
                      {m.icon}
                    </div>
                    <div className="flex items-end justify-between mt-5">
                      <div>
                        <span className="text-sm text-gray-500 dark:text-gray-400">{m.title}</span>
                        <h4 className="mt-2 font-bold text-gray-800 text-title-sm dark:text-white/90">{m.value}</h4>
                      </div>
                      {"delta" in m ? (
                        <Badge color={(m.goodWhenHigher ? (m.delta as number) >= 0 : (m.delta as number) <= 0) ? "success" : "error"}>
                          {(m.goodWhenHigher ? (m.delta as number) >= 0 : (m.delta as number) <= 0) ? <ArrowUpIcon /> : <ArrowDownIcon />}
                          {fmtPct(Math.abs(m.delta as number))}
                        </Badge>
                      ) : (
                        <Badge color={(m as any).deltaText?.startsWith("+") ? "success" : "error"}>
                          {(m as any).deltaText?.startsWith("+") ? <ArrowUpIcon /> : <ArrowDownIcon />}
                          {(m as any).deltaText}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Regional impact bar & Segment donut */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <ComponentCard title="Impact régional (Δ clients)">
                  <div className="max-w-full overflow-x-auto custom-scrollbar">
                    <div className="min-w-[600px]">
                      <Chart
                        options={regionalOptions as any}
                        series={[{ name: "Δ clients", data: regional.vals }]}
                        type="bar"
                        height={320}
                      />
                    </div>
                  </div>
                </ComponentCard>

                <ComponentCard title="Répartition de l'impact revenus par segment (|TND|)">
                  <Chart
                    options={segDonutOpts as any}
                    series={segDonut.data}
                    type="donut"
                    height={320}
                  />
                </ComponentCard>
              </div>

              {/* Regional table */}
              <ComponentCard title="Impact Régional (Table)">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500">
                        <th className="p-2">Région</th><th className="p-2">Clients Actuels</th>
                        <th className="p-2">Changement Estimé</th><th className="p-2">Niveau de Risque</th>
                      </tr>
                    </thead>
                    <tbody>
                      {res.regional.map((r:any)=>(
                        <tr key={r.region}>
                          <td className="p-2">{r.region}</td>
                          <td className="p-2">{r.current_clients}</td>
                          <td className={`p-2 ${r.delta_clients<0?"text-red-600":"text-green-700"}`}>{r.delta_clients}</td>
                          <td className="p-2"><span className="px-2 py-1 rounded bg-rose-100 text-rose-700">{r.risk}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ComponentCard>

              {/* Segment cards */}
              <div className="grid md:grid-cols-3 gap-4">
                {res.segments.map((s:any)=>(
                  <ComponentCard key={s.name} title={s.name}>
                    <div className="text-sm text-gray-600">Clients actuels</div>
                    <div className="text-xl font-semibold">{s.current_clients}</div>
                    <div className="text-sm text-gray-600 mt-1">Changement estimé</div>
                    <div className={`text-xl font-semibold ${s.delta_clients<0?"text-red-600":"text-green-700"}`}>{s.delta_clients}</div>
                    <div className="text-sm text-gray-600 mt-1">Impact revenus (TND)</div>
                    <div className="text-xl font-semibold">{num(s.revenue_impact_tnd)}</div>
                  </ComponentCard>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* slider styles */}
      <style>{`
        :root{
          --c-active: #2563eb; /* blue-600 */
          --c-track: #e5e7eb;  /* gray-200 */
        }
        .input{ width:100%; margin:6px 0 12px; padding:8px 10px; border:1px solid #e5e7eb; border-radius:10px; }
        .range{
          -webkit-appearance: none;
          appearance: none;
          height: 8px;
          border-radius: 999px;
          outline: none;
        }
        .range::-webkit-slider-thumb{
          -webkit-appearance: none;
          appearance: none;
          width: 18px; height: 18px;
          border-radius: 999px;
          background: white;
          border: 2px solid var(--c-active);
          box-shadow: 0 1px 2px rgba(0,0,0,.15);
          cursor: pointer;
        }
        .range::-moz-range-thumb{
          width: 18px; height: 18px;
          border-radius: 999px;
          background: white;
          border: 2px solid var(--c-active);
          box-shadow: 0 1px 2px rgba(0,0,0,.15);
          cursor: pointer;
        }
        .dark .range::-webkit-slider-thumb{ background:#111827; border-color:#60a5fa; }
        .dark .range::-moz-range-thumb{ background:#111827; border-color:#60a5fa; }
      `}</style>
    </>
  );
}
