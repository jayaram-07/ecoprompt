import { useEffect, useState } from "react";
import axios from "axios";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const ROUTE_LABELS = {
  deterministic: "Deterministic",
  knowledge_kb: "Knowledge KB",
  local: "Local Model",
  groq: "Groq"
};

const ROUTE_COLORS = {
  deterministic: "#10b981",
  knowledge_kb: "#0ea5e9",
  local: "#6366f1",
  groq: "#ef4444"
};

function formatRouteTick(value) {
  switch (value) {
    case "Knowledge KB":
      return "Knowledge";
    case "Local Model":
      return "Local";
    default:
      return value;
  }
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);

  const fetchMetrics = async () => {
    try {
      const res = await axios.get("https://ecoprompt-backend-1078329158947.asia-south1.run.app/metrics");
      setMetrics(res.data);
    } catch (err) {
      console.error("Error fetching metrics:", err);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 3000);
    return () => clearInterval(interval);
  }, []);

  if (!metrics) {
    return <div className="dashboard-loading">Loading analytics...</div>;
  }

  const historyData =
    metrics.history?.map((item) => ({
      time: new Date(item.timestamp * 1000).toLocaleTimeString(),
      latency: item.latency_ms,
    })) || [];

  const routeDistributionData = Object.entries(
    metrics.route_distribution_chart || {},
  )
    .map(([route, count]) => ({
      route,
      label: ROUTE_LABELS[route] || route,
      count,
      fill: ROUTE_COLORS[route] || "#64748b",
    }))
    .filter((item) => item.count > 0);

  const routeLatencyData = Object.entries(
    metrics.route_avg_latency_ms || {},
  )
    .map(([route, latency]) => ({
      route,
      label: ROUTE_LABELS[route] || route,
      latency,
      fill: ROUTE_COLORS[route] || "#64748b",
    }))
    .filter((item) => metrics.route_distribution?.[item.route] > 0);

  const routeEnergyData = Object.entries(
    metrics.route_energy_kwh || {},
  )
    .map(([route, energy]) => ({
      route,
      label: ROUTE_LABELS[route] || route,
      energy,
      fill: ROUTE_COLORS[route] || "#64748b",
    }))
    .filter((item) => metrics.route_distribution?.[item.route] > 0);

  return (
    <div className="dashboard-shell">
      <header className="dashboard-simple-header">
        <div className="header-main">
          <h1>Analytics Dashboard</h1>
          <div className="status-badge">
            <span className="status-dot"></span>
            Groq Fallback: <strong>{metrics.fallback_rate_groq}%</strong>
          </div>
        </div>
        <p className="header-subtitle">Real-time performance and financial telemetry for EcoPrompt.</p>
      </header>

      <div className="metric-grid">
        <MetricCard
          title="Total Prompts"
          value={metrics.total_prompts}
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z"/></svg>}
          footer="Live traffic"
        />
        <MetricCard
          title="Cloud Avoidance"
          value={`${metrics.cloud_avoidance_rate}%`}
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/></svg>}
          footer="Local dominance"
        />
        <MetricCard
          title="Avg Latency"
          value={`${metrics.avg_latency_ms} ms`}
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m13 2-2 10h8l-2 10"/></svg>}
          footer="End-to-end"
        />
        <MetricCard
          title="GPT-4o Baseline"
          value={`₹${metrics.gpt4o_baseline_cost_inr}`}
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/></svg>}
          footer="OpenAI Market Rate"
        />
        <MetricCard
          title="Our Cost"
          value={`₹${metrics.estimated_cost_usd}`}
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>}
          footer="Cloud + Energy"
        />
        <MetricCard
          title="Estimated Savings"
          value={`₹${metrics.estimated_cost_saved_usd}`}
          icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/></svg>}
          footer="Total Net Profit"
        />
      </div>

      <div className="chart-grid">
        <ChartCard title="Route Distribution">
          <div className="chart-card-body">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={routeDistributionData} margin={{ left: -20, right: 10, bottom: 42 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="label" tickFormatter={formatRouteTick} tick={{ fontSize: 11 }} stroke="#94a3b8" interval={0} angle={-18} textAnchor="end" height={54} />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
                <Tooltip cursor={{ fill: 'transparent' }} />
                <Bar dataKey="count" radius={[10, 10, 0, 0]}>
                  {routeDistributionData.map((entry) => (
                    <Cell key={entry.route} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Average Latency (ms)">
          <div className="chart-card-body">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={routeLatencyData} margin={{ left: -20, right: 10, bottom: 42 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="label" tickFormatter={formatRouteTick} tick={{ fontSize: 11 }} stroke="#94a3b8" interval={0} angle={-18} textAnchor="end" height={54} />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip formatter={(value) => [`${value} ms`, "Latency"]} cursor={{ fill: 'transparent' }} />
                <Bar dataKey="latency" radius={[10, 10, 0, 0]}>
                  {routeLatencyData.map((entry) => (
                    <Cell key={entry.route} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Energy By Route (kWh)">
          <div className="chart-card-body">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={routeEnergyData} margin={{ left: -20, right: 10, bottom: 42 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="label" tickFormatter={formatRouteTick} tick={{ fontSize: 11 }} stroke="#94a3b8" interval={0} angle={-18} textAnchor="end" height={54} />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip formatter={(value) => [value, "Energy"]} cursor={{ fill: 'transparent' }} />
                <Bar dataKey="energy" radius={[10, 10, 0, 0]}>
                  {routeEnergyData.map((entry) => (
                    <Cell key={entry.route} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>

      <ChartCard title="Latency Trend">
        <div className="latency-trend-body">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={historyData}>
              <defs>
                <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                </linearGradient>
              </defs>

              <XAxis
                dataKey="time"
                tick={{ fontSize: 12 }}
                stroke="#aaa"
              />

              <YAxis
                tick={{ fontSize: 12 }}
                stroke="#aaa"
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "none",
                  borderRadius: 12,
                  color: "#fff",
                }}
              />

              <Legend />
              <Area
                type="monotone"
                dataKey="latency"
                stroke="#4f46e5"
                strokeWidth={3}
                fill="url(#colorLatency)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>
    </div>
  );
}

function MetricCard({ title, value, icon, footer }) {
  return (
    <div className="metric-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {icon && <span style={{ color: "var(--primary)", opacity: 0.8 }}>{icon}</span>}
      </div>
      <p>{value}</p>
      {footer && <div className="metric-card-footer">{footer}</div>}
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <div className="chart-card">
      <h2>{title}</h2>
      {children}
    </div>
  );
}
                             
