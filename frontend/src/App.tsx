import React, { useState } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as ReTooltip, AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';
import { ArrowRight, Activity, TrendingUp, ShieldAlert, PieChart as PieIcon, RefreshCw } from 'lucide-react';

// --- Types ---
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

function App() {
  const [inputTickers, setInputTickers] = useState("AAPL, MSFT, GOOGL, AMZN, TSLA, JPM, JNJ, V, NVDA, PG");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PortfolioData | null>(null);
  const [error, setError] = useState("");

  const handleOptimize = async () => {
    setLoading(true);
    setError("");
    try {
      const tickers = inputTickers.split(',').map(t => t.trim().toUpperCase()).filter(t => t.length > 0);
      const response = await axios.post('http://localhost:8000/api/optimize', { tickers });
      setData(response.data);
    } catch (err) {
      setError("Optimization failed. Please check ticker symbols.");
    } finally {
      setLoading(false);
    }
  };

  const formatPieData = (weights: Record<string, number>) => {
    return Object.entries(weights).map(([name, value]) => ({ name, value: value * 100 }));
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4 md:p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex justify-between items-center border-b border-slate-700 pb-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-blue-500 bg-clip-text text-transparent">
              AI Portfolio Optimizer 2025
            </h1>
            <p className="text-slate-400 mt-1">Powered by Hierarchical Risk Parity (HRP) & Ledoit-Wolf</p>
          </div>
          <div className="hidden md:block text-xs text-slate-500 text-right">
            Riskfolio-Lib v7.0.1 <br /> Production Ready
          </div>
        </div>

        {/* Input Section */}
        <div className="bg-slate-800 rounded-xl p-6 shadow-lg border border-slate-700">
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Enter Assets (Comma separated)
          </label>
          <div className="flex gap-4">
            <input 
              type="text" 
              value={inputTickers}
              onChange={(e) => setInputTickers(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none transition"
              placeholder="e.g. AAPL, BTC-USD, GLD..."
            />
            <button 
              onClick={handleOptimize}
              disabled={loading}
              className="bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-semibold px-8 py-3 rounded-lg flex items-center gap-2 transition-all shadow-lg hover:shadow-emerald-500/20"
            >
              {loading ? <RefreshCw className="animate-spin w-5 h-5" /> : <ArrowRight className="w-5 h-5" />}
              {loading ? "Optimizing..." : "Rebalance Now"}
            </button>
          </div>
          {error && <p className="text-red-400 mt-3 text-sm">{error}</p>}
        </div>

        {/* Results Dashboard */}
        {data && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in-up">
            
            {/* 1. Metrics Cards */}
            <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-4 gap-4">
               <MetricCard icon={<TrendingUp />} label="Est. Annual Return" value={\\%\} color="text-emerald-400" />
               <MetricCard icon={<Activity />} label="Annual Volatility" value={\\%\} color="text-blue-400" />
               <MetricCard icon={<ShieldAlert />} label="Sharpe Ratio" value={data.metrics.sharpe} color="text-yellow-400" />
               <MetricCard icon={<PieIcon />} label="Max Drawdown" value={\\%\} color="text-red-400" />
            </div>

            {/* 2. Weight Allocation (Pie) */}
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg lg:col-span-1">
              <h3 className="text-lg font-semibold mb-4 text-slate-200">Optimal Allocation (HRP)</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={formatPieData(data.weights)}
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {formatPieData(data.weights).map((entry, index) => (
                        <Cell key={\cell-\\} fill={COLORS[index % COLORS.length]} stroke="rgba(0,0,0,0)" />
                      ))}
                    </Pie>
                    <ReTooltip 
                      contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#fff' }} 
                      itemStyle={{ color: '#fff' }}
                      formatter={(val: number) => \\%\}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 space-y-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                {Object.entries(data.weights).map(([ticker, weight], i) => (
                  <div key={ticker} className="flex justify-between text-sm items-center">
                    <span className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }}></span>
                      {ticker}
                    </span>
                    <span className="font-mono">{ (weight * 100).toFixed(2) }%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 3. Performance Chart (Area) */}
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg lg:col-span-2">
              <h3 className="text-lg font-semibold mb-4 text-slate-200">Historical Performance (Backtest)</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.history}>
                    <defs>
                      <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickFormatter={(str) => str.substring(0,4)} />
                    <YAxis stroke="#94a3b8" fontSize={12} unit="%" />
                    <ReTooltip 
                      contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#fff' }}
                    />
                    <Area type="monotone" dataKey="value" stroke="#10b981" fillOpacity={1} fill="url(#colorValue)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}

const MetricCard = ({ icon, label, value, color }: any) => (
  <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex items-center gap-4">
    <div className={\p-3 rounded-lg bg-slate-700 \\}>
      {icon}
    </div>
    <div>
      <p className="text-slate-400 text-xs uppercase tracking-wider">{label}</p>
      <p className="text-xl font-bold text-slate-100">{value}</p>
    </div>
  </div>
);

export default App;
