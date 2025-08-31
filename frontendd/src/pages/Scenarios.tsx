// src/pages/Scenarios.tsx
import { useState } from "react";
import { compare, simulate, type SimRequest, type Scenario } from "../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from "recharts";

const SCENARIOS: Scenario[] = [
  "Fermeture d'Agence","Currency Devaluation","Energy Crisis",
  "Political Uncertainty","Digital Transformation","Tourism Recovery",
  "Export Boom","Economic Recovery","Regional Instability","Baseline",
];
const REGIONS = ["Tunis","Sfax","Sousse","Kairouan","Bizerte","Gabès","Ariana","La Marsa"] as const;

export default function Scenarios() {
  const [conf, setConf] = useState<SimRequest>({
    scenario: "Fermeture d'Agence",
    intensity: "Moyenne",
    segment: "Tous les segments",
    region: "Sousse",
    duration_months: 6,
  });

  const [res, setRes] = useState<any>(null);
  const [cmp, setCmp] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const runSim = async () => {
    setLoading(true);
    try { setRes((await simulate(conf)).data); }
    finally { setLoading(false); }
  };

  const runCompare = async () => {
    const variants: SimRequest[] = [
      conf,
      { ...conf, scenario: "Currency Devaluation" },
      { ...conf, scenario: "Energy Crisis" },
      { ...conf, scenario: "Political Uncertainty" },
      { ...conf, scenario: "Digital Transformation" },
    ];
    const r = await compare(variants);
    setCmp(r.data);
  };

  return (
    <div className="grid grid-cols-12 gap-4 md:gap-6">
      {/* Config */}
      <section className="col-span-12 xl:col-span-4 bg-white dark:bg-gray-900 rounded-2xl p-4 shadow">
        <h3 className="font-semibold mb-2">Configuration du Scénario</h3>

        <label className="text-sm">Type de Scénario</label>
        <select className="input" value={conf.scenario}
          onChange={e=>setConf({...conf, scenario: e.target.value as any})}>
          {SCENARIOS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        <label className="text-sm">Intensité</label>
        <select className="input" value={conf.intensity}
          onChange={e=>setConf({...conf, intensity: e.target.value as any})}>
          {["Faible","Moyenne","Forte"].map(i => <option key={i}>{i}</option>)}
        </select>

        <label className="text-sm">Segment Ciblé</label>
        <select className="input" value={conf.segment}
          onChange={e=>setConf({...conf, segment: e.target.value as any})}>
          {["Tous les segments","Premium","SME","Mass Market"].map(i => <option key={i}>{i}</option>)}
        </select>

        <label className="text-sm">Région</label>
        <select className="input" value={conf.region}
          onChange={e=>setConf({...conf, region: e.target.value as any})}>
          {REGIONS.map(r => <option key={r}>{r}</option>)}
        </select>

        <label className="text-sm">Durée (mois): <b>{conf.duration_months}</b></label>
        <input type="range" min={1} max={24} value={conf.duration_months}
               onChange={e=>setConf({...conf, duration_months: +e.target.value})}
               className="w-full"/>

        <button className="btn btn-primary mt-3 w-full" onClick={runSim} disabled={loading}>
          Lancer la Simulation
        </button>
        <button className="btn btn-dark mt-2 w-full" onClick={runCompare}>
          Comparer Multi-Scénarios
        </button>
      </section>

      {/* Results */}
      <section className="col-span-12 xl:col-span-8 space-y-4">
        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPI title="Clients" value={res ? `${res.kpis.clients} (${res.kpis.diff_clients>=0?'+':''}${res.kpis.diff_clients})` : "—"} />
          <KPI title="Satisfaction" value={res ? (res.kpis.satisfaction*100).toFixed(1)+'%' : "—"} />
          <KPI title="Taux de Churn" value={res ? (res.kpis.churn_rate*100).toFixed(1)+'%' : "—"} />
          <KPI title="Digital" value={res ? (res.kpis.digital_adoption*100).toFixed(1)+'%' : "—"} />
        </div>

        {/* Regional Impact */}
        {res && (
          <Card title="Impact Régional">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th className="p-2">Région</th>
                    <th className="p-2">Clients Actuels</th>
                    <th className="p-2">Changement Estimé</th>
                    <th className="p-2">Niveau de Risque</th>
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
          </Card>
        )}

        {/* Segment cards */}
        {res && (
          <div className="grid md:grid-cols-3 gap-4">
            {res.segments.map((s:any)=>(
              <Card key={s.name} title={s.name}>
                <div className="text-sm text-gray-600">Clients actuels</div>
                <div className="text-xl font-semibold">{s.current_clients}</div>
                <div className="text-sm text-gray-600 mt-1">Changement estimé</div>
                <div className={`text-xl font-semibold ${s.delta_clients<0?"text-red-600":"text-green-700"}`}>
                  {s.delta_clients}
                </div>
                <div className="text-sm text-gray-600 mt-1">Impact revenus (TND)</div>
                <div className="text-xl font-semibold">{s.revenue_impact_tnd.toLocaleString()}</div>
              </Card>
            ))}
          </div>
        )}

        {/* Comparison */}
        {cmp.length>0 && (
          <div className="grid md:grid-cols-2 gap-4">
            <Card title="Adoption Rate Change vs Baseline">
              <div className="w-full h-72">
                <ResponsiveContainer>
                  <BarChart data={cmp.map((d:any)=>({Scenario: d.scenario, Change: d.adoption_change}))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="Scenario"/>
                    <YAxis tickFormatter={(v)=> (v*100).toFixed(1)+'%'} />
                    <Tooltip formatter={(v:any)=>[(v*100).toFixed(2)+'%','Δ Adoption']} />
                    <Bar dataKey="Change" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Revenue Impact vs Baseline">
              <div className="w-full h-72">
                <ResponsiveContainer>
                  <BarChart data={cmp.map((d:any)=>({Scenario: d.scenario, Change: d.revenue_change}))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="Scenario"/>
                    <YAxis tickFormatter={(v)=> (v*100).toFixed(1)+'%'} />
                    <Tooltip formatter={(v:any)=>[(v*100).toFixed(2)+'%','Δ Revenue']} />
                    <Bar dataKey="Change" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        )}
      </section>

      <style>{`
        .input{ width:100%; margin:6px 0 12px; padding:8px 10px; border:1px solid #e5e7eb; border-radius:10px; }
        .btn{ @apply rounded-lg px-3 py-2; }
        .btn-primary{ @apply bg-red-600 text-white hover:bg-red-700; }
        .btn-dark{ @apply bg-gray-900 text-white hover:bg-black; }
      `}</style>
    </div>
  );
}

function Card({title, children}:{title:string; children:any}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl p-4 shadow">
      <h3 className="font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}

function KPI({title, value}:{title:string; value:string}) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl p-4 shadow">
      <div className="text-xs text-gray-500">{title}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
