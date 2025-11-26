import React, { useState } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';
import { ArrowRight, Activity, TrendingUp, ShieldAlert, PieChartIcon, RefreshCw } from 'lucide-react';

interface Metrics {
  annual_return: number;
  volatility: number;
  sharpe: number;
  max_drawdown: number;
}

interface PortfolioData {
  weights: Record<string, number>;
  metrics: Metrics;
  history: { date: string; value: number }[];
}

const COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#6366f1'];

export default function App() {
  const [inputTickers, setInputTickers] = useState("AAPL,MSFT,GOOGL,AMZN,TSLA,JPM,JNJ,V,NVDA,PG");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PortfolioData | null>(null);
  const [error, setError] = useState("");

  const handleOptimize = async () => {
    setLoading(true);
    setError("");
    try {
      const tickers = inputTickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean);
      const res = await axios.post('http://localhost:8000/api/optimize', { tickers });
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Optimization failed");
    } finally {
      setLoading(false);
    }
  };

  const pieData = data ? Object.entries(data.weights).map(([name, value]) => ({ name, value: value * 100 })) : [];

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">

        <div className="flex justify-between items-center border-b border-slate-700 pb-6">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-emerald-400 to-blue-500 bg-clip-text text-transparent">
              AI Portfolio Optimizer 2025
            </h1>
            <p className="text-slate-400">HRP + Ledoit-Wolf Shrinkage</p>
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <div className="flex gap-4">
            <input
              value={inputTickers}
              onChange={e => setInputTickers(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500 outline-none"
              placeholder="AAPL, MSFT, GOOGL..."
            />
            <button
              onClick={handleOptimize}
              disabled={loading}
              className="bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 px-8 py-3 rounded-lg flex items-center gap-2 font-semibold"
            >
              {loading ? <RefreshCw className="animate-spin w-5 h-5" /> : <ArrowRight className="w-5 h-5" />}
              {loading ? "Optimizing..." : "Optimize"}
            </button>
          </div>
          {error && <p className="text-red-400 mt-4">{error}</p>}
        </div>

        {data && (
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Metrics */}
            <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard icon={<TrendingUp />} label="Annual Return" value={`${(data.metrics.annual_return ).toFixed(2)}%`} color="text-emerald-400" />
              <MetricCard icon={<Activity />} label="Volatility" value={`${(data.metrics.volatility ).toFixed(2)}%`} color="text-blue-400" />
              <MetricCard icon={<ShieldAlert />} label="Sharpe Ratio" value={data.metrics.sharpe.toFixed(2)} color="text-yellow-400" />
              <MetricCard icon={<PieChartIcon />} label="Max Drawdown" value={`${(data.metrics.max_drawdown).toFixed(2)}%`} color="text-red-400" />
            </div>

            {/* Pie Chart */}
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h3 className="text-lg font-semibold mb-4">Allocation</h3>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={pieData} innerRadius={60} outerRadius={100} dataKey="value" paddingAngle={3}>
                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-4 space-y-2">
                {Object.entries(data.weights).map(([t, w], i) => (
                  <div key={t} className="flex justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                      {t}
                    </span>
                    <span>{(w * 100).toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Performance */}
            <div className="lg:col-span-2 bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h3 className="text-lg font-semibold mb-4">Backtest Performance</h3>
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={data.history}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" stroke="#94a3b8" tickFormatter={d => d.slice(0,4)} />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ background: '#1e293b', border: 'none' }} />
                  <Area type="monotone" dataKey="value" stroke="#10b981" fill="url(#grad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const MetricCard = ({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) => (
  <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 flex items-center gap-4">
    <div className={`p-3 rounded-lg bg-slate-700 ${color}`}>{icon}</div>
    <div>
      <p className="text-slate-400 text-xs">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  </div>
);
