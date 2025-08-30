import { useEffect, useState } from "react";
import Plot from "react-plotly.js";

import { api } from "../lib/api";

type Point = { x: number; y: number; z: number; cluster: number };
type SummaryRow = {
  cluster: number;
  Capital_en_DT: number;
  Emploi: number;
  Credit_Worthiness: number;
  Loyalty_Score: number;
  Digital_Adoption: number;
  Count: number;
};

export default function Segments() {
  const [k, setK] = useState(4);
  const [points, setPoints] = useState<Point[]>([]);
  const [rows, setRows] = useState<SummaryRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setErr(null);
    try {
      const r = await api.post("/segments", { n_clusters: k });
      setPoints(r.data.points || []);
      setRows(r.data.summary || []);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "Failed to load segments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clusters = [...new Set(points.map((p) => p.cluster))];
  const traces = clusters.map((c) => {
    const pts = points.filter((p) => p.cluster === c);
    return {
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      z: pts.map((p) => p.z),
      mode: "markers",
      type: "scatter3d",
      name: `Cluster ${c}`,
      marker: { size: 4, opacity: 0.85 },
    } as any;
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <label className="text-sm text-gray-600">Clusters</label>
        <input
          type="number"
          value={k}
          min={2}
          max={8}
          onChange={(e) => setK(+e.target.value)}
          className="border rounded px-2 py-1 w-20"
        />
        <button
          onClick={run}
          disabled={loading}
          className="px-3 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
        >
          {loading ? "Running…" : "Run"}
        </button>
        {err && <span className="text-red-600 text-sm ml-3">{err}</span>}
      </div>

      <div className="bg-white rounded-xl p-3 shadow">
        <Plot
          data={traces}
          layout={
            {
              title: "Customer Segments (3D View)",
              autosize: true,
              height: 500,
              scene: {
                xaxis: { title: "Capital (DT)" },
                yaxis: { title: "Employment" },
                zaxis: { title: "Credit Index" },
              },
              margin: { l: 0, r: 0, t: 40, b: 0 },
            } as any
          }
          style={{ width: "100%", height: "100%" }}
          config={{ displaylogo: false, responsive: true } as any}
        />
      </div>

      <div className="bg-white rounded-xl p-4 shadow overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr>
              {[
                "Cluster",
                "Capital_en_DT",
                "Emploi",
                "Credit_Worthiness",
                "Loyalty_Score",
                "Digital_Adoption",
                "Count",
              ].map((h) => (
                <th key={h} className="text-left pr-4 py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.cluster} className="border-t">
                <td className="py-1">{r.cluster}</td>
                <td>{r.Capital_en_DT.toFixed(0)}</td>
                <td>{r.Emploi.toFixed(0)}</td>
                <td>{r.Credit_Worthiness.toFixed(2)}</td>
                <td>{r.Loyalty_Score.toFixed(2)}</td>
                <td>{r.Digital_Adoption.toFixed(2)}</td>
                <td>{r.Count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
