import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

type Item = { name: string; value: number };
export default function BarChartOneDynamic({
  data,
  yTick = (v: number) => `${(v * 100).toFixed(1)}%`,
  height = 280,
}: { data: Item[]; yTick?: (v:number)=>string; height?: number }) {
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis tickFormatter={yTick} />
          <Tooltip formatter={(v: any) => [yTick(Number(v)), ""]} />
          <Bar dataKey="value" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
