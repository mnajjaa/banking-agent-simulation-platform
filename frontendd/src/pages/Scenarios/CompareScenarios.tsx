import { useEffect, useMemo, useState } from "react";
import PageMeta from "../../components/common/PageMeta";
import ComponentCard from "../../components/common/ComponentCard";
import { compare, simulate, type SimRequest } from "../../lib/api";
import {
  CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend,
  ScatterChart, Scatter, LabelList, ReferenceLine, ReferenceArea,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import Chart from "react-apexcharts";

// base request used for all variants
const makeBase = (): SimRequest => ({
  scenario: "Fermeture d'Agence",
  intensity: "Moyenne",
  segment: "Tous les segments",
  region: "Sousse",
  duration_months: 6,
});

// default variants to compare
const VARIANTS = [
  (b: SimRequest) => b,
  (b: SimRequest) => ({ ...b, scenario: "Currency Devaluation" }),
  (b: SimRequest) => ({ ...b, scenario: "Energy Crisis" }),
  (b: SimRequest) => ({ ...b, scenario: "Political Uncertainty" }),
  (b: SimRequest) => ({ ...b, scenario: "Digital Transformation" }),
];

type ScenarioPoint = {
  name: string;
  adoption: number;           // change vs baseline (fraction)
  revenue: number;            // change vs baseline (fraction)
  retention: number;          // -Δ churn (positive = churn improved)
  satisfaction: number;       // change vs baseline
  segRev: { Premium: number; SME: number; "Mass Market": number }; // TND change
  worstRegions: { region: string; delta: number }[];
};

export default function CompareScenarios() {
  const [points, setPoints] = useState<ScenarioPoint[]>([]);
  const [showChurn, setShowChurn] = useState(false);
  const [activeSeg, setActiveSeg] = useState<"Premium" | "SME" | "Mass Market">("Premium");

  useEffect(() => { run(); }, []);

  const run = async () => {
    const base = makeBase();
    const cmp = await compare(VARIANTS.map(v => v(base)));
    const rows = cmp.data as { scenario: string; adoption_change: number; revenue_change: number }[];

    const baseline = await simulate({ ...base, scenario: "Baseline" });
    const baseK = baseline.data.kpis;

    const detailed: ScenarioPoint[] = [];
    for (const r of rows) {
      const sim = await simulate({ ...base, scenario: r.scenario });
      const k = sim.data.kpis;
      const segs = sim.data.segments as Array<{ name: string; revenue_impact_tnd: number }>;
      const regs = sim.data.regional as Array<{ region: string; delta_clients: number }>;

      const segMap: any = { Premium: 0, SME: 0, "Mass Market": 0 };
      segs.forEach(s => (segMap[s.name] = s.revenue_impact_tnd));

      const worst = [...regs]
        .sort((a, b) => a.delta_clients - b.delta_clients)
        .slice(0, 3)
        .map(x => ({ region: x.region, delta: x.delta_clients }));

      detailed.push({
        name: r.scenario,
        adoption: r.adoption_change,
        revenue: r.revenue_change,
        retention: baseK.churn_rate - k.churn_rate, // positive = better
        satisfaction: k.satisfaction - baseK.satisfaction,
        segRev: segMap,
        worstRegions: worst,
      });
    }
    setPoints(detailed);
  };

  const pct = (v: number) => (v * 100).toFixed(1) + "%";

  // ===== Scatter & Radar =====
  const scatterData = useMemo(
    () => points.map(p => ({ x: p.adoption, y: p.revenue, name: p.name })),
    [points]
  );

  const radarData = useMemo(() => {
    const rows: any[] = [
      { metric: "Adoption change" },
      { metric: "Revenue change" },
      { metric: showChurn ? "Churn change" : "Retention change" },
      { metric: "Satisfaction change" },
    ];
    for (const p of points) {
      rows[0][p.name] = p.adoption;
      rows[1][p.name] = p.revenue;
      rows[2][p.name] = showChurn ? -p.retention : p.retention;
      rows[3][p.name] = p.satisfaction;
    }
    return rows;
  }, [points, showChurn]);

  // ===== Single segment bar (with toggle) =====
  const segCategories = useMemo(() => points.map(p => p.name), [points]);
  const segPremium = useMemo(() => points.map(p => p.segRev.Premium), [points]);
  const segSME     = useMemo(() => points.map(p => p.segRev.SME), [points]);
  const segMass    = useMemo(() => points.map(p => p.segRev["Mass Market"]), [points]);

  // unified Y range across segments for comparability
  const yMin = useMemo(() => Math.min(...segPremium, ...segSME, ...segMass, 0), [segPremium, segSME, segMass]);
  const yMax = useMemo(() => Math.max(...segPremium, ...segSME, ...segMass, 0), [segPremium, segSME, segMass]);
  const yPad = useMemo(() => Math.max(Math.abs(yMin), Math.abs(yMax)) * 0.1, [yMin, yMax]);
  const yRange: [number, number] = useMemo(
    () => [Math.floor(Math.min(0, yMin - yPad)), Math.ceil(Math.max(0, yMax + yPad))],
    [yMin, yMax, yPad]
  );

  const segColorMap: Record<"Premium" | "SME" | "Mass Market", string> = {
    Premium: "#465FFF",
    SME: "#16a34a",
    "Mass Market": "#f59e0b",
  };

  const segData = useMemo(() => {
    if (activeSeg === "Premium") return segPremium;
    if (activeSeg === "SME")     return segSME;
    return segMass;
  }, [activeSeg, segPremium, segSME, segMass]);

  const segOptions = useMemo(() => ({
    colors: [segColorMap[activeSeg]],
    chart: { fontFamily: "Outfit, sans-serif", type: "bar" as const, toolbar: { show: false }, animations: { enabled: true } },
    plotOptions: { bar: { horizontal: false, columnWidth: "45%", borderRadius: 6, borderRadiusApplication: "end" } },
    dataLabels: { enabled: false },
    stroke: { show: true, width: 4, colors: ["transparent"] },
    grid: { yaxis: { lines: { show: true } } },
    xaxis: { categories: segCategories, axisBorder: { show: false }, axisTicks: { show: false }, labels: { rotate: -10 } },
    yaxis: { min: yRange[0], max: yRange[1], tickAmount: 5, labels: { formatter: (v: number) => Intl.NumberFormat().format(v) } },
    tooltip: { y: { formatter: (v: number) => `${Intl.NumberFormat().format(v)} TND` } },
    annotations: { yaxis: [{ y: 0, borderColor: "#9ca3af", strokeDashArray: 4 }] },
    fill: { opacity: 1 },
  }), [activeSeg, segCategories, yRange]);

  // ===== Insights =====
  const insights = useMemo(() =>
    points.map(p => {
      const churnDelta = -p.retention; // Δchurn (negative = improved)
      const list = showChurn
        ? [["Adoption", p.adoption], ["Revenue", p.revenue], ["Churn", churnDelta], ["Satisfaction", p.satisfaction]]
        : [["Adoption", p.adoption], ["Revenue", p.revenue], ["Retention", p.retention], ["Satisfaction", p.satisfaction]];
      const best = [...list].sort((a, b) => Math.abs(Number(b[1])) - Math.abs(Number(a[1])))[0] as [string, number];
      return { name: p.name, bestMetric: best, worstRegions: p.worstRegions };
    }), [points, showChurn]
  );

  const colors = ["#2563eb", "#16a34a", "#f59e0b", "#ef4444", "#7c3aed", "#0ea5e9", "#059669"];

  return (
    <>
      <PageMeta title="Compare Scenarios" description="Multi-scenario comparison" />
      <div className="grid grid-cols-12 gap-4 md:gap-6">
       <div className="col-span-12 xl:col-span-3">
        {/* 👇 becomes sticky on desktop; normal flow on mobile */}
        <div className="xl:sticky xl:top-24 xl:max-h-[calc(100vh-6rem)] xl:flex xl:flex-col xl:gap-4">
   
          <ComponentCard title="Options">
            {/* Retention ↔ Churn switch */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">Radar axis</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Retention</span>
                <div
                  onClick={() => setShowChurn(v => !v)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full cursor-pointer transition ${
                    showChurn ? "bg-gray-900 dark:bg-white" : "bg-gray-300"
                  }`}
                  title="Toggle Retention/Churn on the radar"
                >
                  <span
                    className={`inline-block h-5 w-5 transform rounded-full bg-white dark:bg-gray-900 transition ${
                      showChurn ? "translate-x-5" : "translate-x-1"
                    }`}
                  />
                </div>
                <span className="text-xs text-gray-500">Churn</span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Switch shows <b>Retention change</b> (−Δ churn) or <b>Churn change</b> directly on the radar chart.
            </p>
          </ComponentCard>

          {/* Insights */}
          {points.length > 0 && (
            <ComponentCard title="Insights">
            <div className="max-h-[calc(100vh-14rem)] overflow-auto pr-2">

              <ul className="space-y-2 text-sm">
                {insights.map(i => (
                  <li key={i.name}>
                    <span className="font-medium">{i.name}:</span>{" "}
                    strongest effect on <b>{i.bestMetric[0]}</b> ({pct(Number(i.bestMetric[1]))}).<br />
                    <span className="text-gray-500">Worst regions:</span>{" "}
                    {i.worstRegions.map(w => `${w.region} (${w.delta >= 0 ? "+" : ""}${w.delta})`).join(", ")}
                  </li>
                ))}
              </ul>
            </div>
                
            </ComponentCard>
          )}
        </div>
    </div>

        {/* Right column */}
        <div className="col-span-12 xl:col-span-9 space-y-4">
          
{/* Balanced Scorecard */}
          <ComponentCard title="Balanced Scorecard (change vs baseline)">
            <div className="w-full h-96">
              <ResponsiveContainer>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" />
                  <PolarRadiusAxis tickFormatter={pct} />
                  {points.map((p, i) => (
                    <Radar
                      key={p.name}
                      dataKey={p.name}
                      name={p.name}
                      stroke={colors[i % colors.length]}
                      fill={colors[i % colors.length]}
                      fillOpacity={0.25}
                    />
                  ))}
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </ComponentCard>
          {/* Revenue Impact by Segment — Single chart with segment toggle */}
          <ComponentCard title="Revenue impact by segment (TND)">
            <div className="mb-3">
              <div className="inline-flex rounded-xl bg-gray-100 dark:bg-white/10 p-1">
                {(["Premium","SME","Mass Market"] as const).map(seg => (
                  <button
                    key={seg}
                    onClick={() => setActiveSeg(seg)}
                    className={`px-4 py-1.5 text-sm rounded-lg transition ${
                      activeSeg === seg
                        ? "bg-white shadow text-gray-900 dark:bg-gray-900 dark:text-white"
                        : "text-gray-600 dark:text-gray-300"
                    }`}
                  >
                    {seg}
                  </button>
                ))}
              </div>
            </div>

            <Chart options={segOptions as any} series={[{ name: activeSeg, data: segData }]} type="bar" height={260} />

            <p className="text-xs text-gray-500 mt-2">
              Same scale across segments to keep magnitudes comparable. Values are Δ revenue (TND) vs baseline.
            </p>
          </ComponentCard>

          {/* Portfolio View */}
          <ComponentCard title="Portfolio View — Revenue change vs Adoption change">
            <div className="w-full h-80">
              <ResponsiveContainer>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" />
                  {/* Quadrant tints */}
                  <ReferenceArea x1={0} x2={1} y1={0} y2={1} fill="#ECFDF5" fillOpacity={0.5} />
                  <ReferenceArea x1={-1} x2={0} y1={-1} y2={0} fill="#FEF2F2" fillOpacity={0.5} />
                  <XAxis type="number" dataKey="x" name="Adoption change" tickFormatter={pct} />
                  <YAxis type="number" dataKey="y" name="Revenue change" tickFormatter={pct} />
                  <Tooltip formatter={(v: any) => [pct(v as number), ""]} />
                  <Legend />
                  <ReferenceLine x={0} stroke="#9ca3af" />
                  <ReferenceLine y={0} stroke="#9ca3af" />
                  <Scatter name="Scenarios" data={scatterData} fill="#2563eb">
                    <LabelList dataKey="name" position="top" />
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Top-right = win-win (revenue ↑ & adoption ↑). Top-left = revenue ↑ / adoption ↓. Bottom-right = adoption ↑ / revenue ↓.
              Bottom-left = both ↓ (avoid). This view helps rank scenarios on a growth-vs-adoption frontier.
            </p>
          </ComponentCard>
        </div>
      </div>
    </>
  );
}
