import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
} from 'chart.js';

// --- Configuration & Constants ---
ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale);

const API_BASE = "http://localhost:8000";

const CHART_COLORS = [
  'rgba(75, 192, 192, 0.8)', // Teal
  'rgba(255, 99, 132, 0.8)', // Red
  'rgba(255, 205, 86, 0.8)', // Yellow
  'rgba(54, 162, 235, 0.8)', // Blue
  'rgba(153, 102, 255, 0.8)', // Purple
  'rgba(255, 159, 64, 0.8)', // Orange
  'rgba(201, 203, 207, 0.8)', // Gray
];

const formatPercent = (value) => `${(value * 100).toFixed(2)}%`;

// --- Reusable UI Components ---

const MetricCard = ({ title, value, color }) => (
  <div className="p-3 bg-gray-700 rounded-lg transition hover:bg-gray-650">
    <p className="text-sm font-medium text-gray-400">{title}</p>
    <p className={`text-xl font-bold ${color}`}>{value}</p>
  </div>
);

const SystemStatus = ({ health }) => (
  <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mb-4 shadow-sm">
    <div className="flex items-center justify-between">
      <div className="flex items-center space-x-2">
        <div className={`w-3 h-3 rounded-full ${health?.status === 'ok' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500'}`}></div>
        <span className="text-sm text-gray-300 font-medium">System Status</span>
      </div>
      <div className="text-xs text-gray-400 bg-gray-900 px-2 py-1 rounded-md border border-gray-600">
        {health?.models_loaded || 0} models loaded
      </div>
    </div>
  </div>
);

const AvailableModelsList = ({ models }) => {
  if (!models || models.length === 0) return null;

  return (
    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mt-4">
      <h4 className="text-sm font-medium text-gray-300 mb-3">Available AI Models</h4>
      <div className="flex flex-wrap gap-2">
        {models.slice(0, 12).map((ticker) => (
          <span key={ticker} className="px-2 py-1 bg-teal-900/50 text-teal-300 border border-teal-800 rounded text-xs font-mono">
            {ticker}
          </span>
        ))}
        {models.length > 12 && (
          <span className="px-2 py-1 bg-gray-700 text-gray-400 rounded text-xs">
            +{models.length - 12} more
          </span>
        )}
      </div>
    </div>
  );
};

const LoadingSkeleton = () => (
  <div className="p-6 bg-gray-800 rounded-xl shadow-lg border border-gray-700 space-y-4 animate-pulse">
    <div className="h-6 w-3/4 bg-gray-700 rounded"></div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-16 bg-gray-700 rounded"></div>
      ))}
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-6">
      <div className="h-64 bg-gray-700 rounded"></div>
      <div className="h-64 bg-gray-700 rounded"></div>
    </div>
  </div>
);

const OptimizationForm = ({ 
  tickers, setTickers, 
  riskFreeRate, setRiskFreeRate, 
  minWeight, setMinWeight,
  onSubmit, loading 
}) => (
  <div className="p-6 bg-gray-800 rounded-xl shadow-2xl border border-gray-700 h-fit">
    <h2 className="text-2xl font-semibold mb-4 text-white border-b border-gray-700 pb-2">
        Input Parameters
    </h2>
    <form onSubmit={onSubmit} className="space-y-5">
      {/* Tickers Input */}
      <div>
        <label htmlFor="tickers" className="block text-sm font-medium text-gray-300 mb-1">
          Stock Tickers
        </label>
        <input
          id="tickers"
          type="text"
          value={tickers}
          onChange={(e) => setTickers(e.target.value)}
          className="w-full px-4 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-2 focus:ring-teal-500 focus:border-transparent transition outline-none placeholder-gray-500"
          placeholder="AAPL, MSFT, GOOG, ..."
          required
        />
        <p className="text-xs text-gray-400 mt-1">Comma separated (e.g. AAPL, MSFT)</p>
      </div>
      
      {/* Risk Free Rate & Min Weight Group */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="riskRate" className="block text-sm font-medium text-gray-300 mb-1">
            Risk-Free Rate
          </label>
          <input
            id="riskRate"
            type="number"
            step="0.001"
            value={riskFreeRate}
            onChange={(e) => setRiskFreeRate(parseFloat(e.target.value))}
            className="w-full px-4 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-2 focus:ring-teal-500 outline-none"
            required
          />
          <p className="text-xs text-gray-400 mt-1">Annual (e.g. 0.03)</p>
        </div>

        <div>
          <label htmlFor="minWeight" className="block text-sm font-medium text-teal-300 mb-1">
            Min Weight
          </label>
          <input
            id="minWeight"
            type="number"
            step="0.01"
            min="0"
            max="0.5"
            value={minWeight}
            onChange={(e) => setMinWeight(parseFloat(e.target.value))}
            className="w-full px-4 py-2 border border-teal-700 rounded-lg bg-gray-700 text-white focus:ring-2 focus:ring-teal-500 outline-none"
          />
          <p className="text-xs text-gray-400 mt-1">Floor (e.g. 0.05)</p>
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 mt-2 text-lg font-semibold rounded-lg text-gray-900 transition duration-300 
                   bg-teal-500 hover:bg-teal-400 active:scale-[0.98]
                   disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(20,184,166,0.3)]"
      >
        {loading ? (
            <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5 text-gray-900" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                AI Optimizing...
            </span>
        ) : "Optimize Portfolio"}
      </button>
    </form>
  </div>
);

const ResultsSummary = ({ result }) => {
    const portfolioReturn = result.details.portfolio_return ?? 0;
    const portfolioVolatility = result.details.portfolio_volatility ?? 0;
    const tickersUsedCount = (result.details.tickers_used ?? []).length;
    const modelsUsed = result.details.models_used ?? 0;

    return (
        <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700 space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-gray-700">
                <h4 className="text-xl font-semibold text-teal-400 flex items-center gap-2">
                    <span className="text-2xl">🚀</span> Optimal Portfolio Metrics
                </h4>
                <span className="text-sm text-gray-400 bg-gray-700 px-2 py-1 rounded">
                    {modelsUsed} AI Models Active
                </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-white">
                <MetricCard title="Sharpe Ratio" value={result.sharpe.toFixed(4)} color="text-green-400" />
                <MetricCard title="Exp. Return (Ann.)" value={formatPercent(portfolioReturn)} color="text-blue-400" />
                <MetricCard title="Volatility (Risk)" value={formatPercent(portfolioVolatility)} color="text-yellow-400" />
                <MetricCard title="Assets Selected" value={tickersUsedCount} color="text-purple-400" />
            </div>
        </div>
    );
};

const AllocationTable = ({ weights, expectedReturns }) => (
    <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700">
        <h4 className="text-xl font-semibold mb-4 text-white border-b border-gray-700 pb-2">Detailed Allocation Strategy</h4>
        <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-gray-300">
            <thead className="text-xs text-gray-400 uppercase bg-gray-750 border-b border-gray-600">
            <tr>
                <th className="px-4 py-3">Stock</th>
                <th className="px-4 py-3 text-right">Weight</th>
                <th className="px-4 py-3 w-1/3">Allocation Visual</th>
                <th className="px-4 py-3 text-right">AI Predicted Return</th>
            </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
            {Object.entries(weights)
                .filter(([, weight]) => weight > 0.001)
                .sort(([,a], [,b]) => b - a)
                .map(([ticker, weight]) => (
                <tr key={ticker} className="hover:bg-gray-700/50 transition">
                    <td className="px-4 py-3 font-bold text-teal-300">{ticker}</td>
                    <td className="px-4 py-3 text-right font-mono text-white">{formatPercent(weight)}</td>
                    <td className="px-4 py-3">
                    <div className="w-full bg-gray-900 rounded-full h-2.5 overflow-hidden">
                        <div 
                        className="bg-gradient-to-r from-teal-600 to-teal-400 h-2.5 rounded-full" 
                        style={{ width: `${weight * 100}%` }}
                        ></div>
                    </div>
                    </td>
                    <td className={`px-4 py-3 text-right font-mono font-medium ${expectedReturns[ticker] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatPercent(expectedReturns[ticker])}
                    </td>
                </tr>
                ))}
            </tbody>
        </table>
        </div>
    </div>
);

// --- Main Application Component ---

const App = () => {
  // State
  const [tickers, setTickers] = useState("AAPL,MSFT,GOOG,AMZN,META,TSLA,NVDA,JPM,JNJ,V");
  const [riskFreeRate, setRiskFreeRate] = useState(0.03);
  const [minWeight, setMinWeight] = useState(0.05); // New State
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [availableModels, setAvailableModels] = useState({ loaded_models: [] });
  const [systemHealth, setSystemHealth] = useState(null);

  // Lifecycle
  useEffect(() => {
    const init = async () => {
      try {
        const [modelsRes, healthRes] = await Promise.all([
          axios.get(`${API_BASE}/api/available_models`),
          axios.get(`${API_BASE}/api/health`)
        ]);
        setAvailableModels(modelsRes.data);
        setSystemHealth(healthRes.data);
      } catch (err) {
        console.error("Initialization error:", err);
        setSystemHealth({ status: 'error', models_loaded: 0 });
      }
    };
    init();
  }, []);

  // Handlers
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    
    if (!tickers.trim()) {
        setError("Please enter at least one ticker.");
        return;
    }

    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/api/optimize_portfolio`, {
        tickers,
        risk_free_rate: riskFreeRate,
        min_weight: minWeight, // Sending new parameter
      });
      setResult(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  // Memoized Chart Data
  const pieChartData = useMemo(() => {
    if (!result || !result.weights) return null;

    const weights = result.weights;
    const labels = Object.keys(weights).filter(t => weights[t] > 0.001);
    const dataPoints = labels.map(l => (weights[l] * 100));
    
    const backgroundColors = labels.map((_, index) => CHART_COLORS[index % CHART_COLORS.length]);
    const borderColors = backgroundColors.map(color => color.replace('0.8', '1'));

    return {
      labels,
      datasets: [{
        label: 'Weight (%)',
        data: dataPoints,
        backgroundColor: backgroundColors,
        borderColor: borderColors,
        borderWidth: 1,
      }],
    };
  }, [result]);

  const pieChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'bottom',
            labels: { color: 'rgb(209, 213, 219)', font: { size: 12 }, padding: 20 }
        },
        tooltip: {
            callbacks: {
                label: (ctx) => ` ${(ctx.parsed).toFixed(2)}%`
            }
        }
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4 sm:p-8 font-sans selection:bg-teal-500 selection:text-white">
      <script src="https://cdn.tailwindcss.com"></script>
      
      <div className="max-w-7xl mx-auto">
        <header className="py-8 mb-8 text-center border-b border-gray-800">
          <h1 className="text-5xl font-extrabold text-white tracking-tight mb-2">
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-blue-500">AI</span> Portfolio Optimizer
          </h1>
          <p className="text-gray-400 text-lg">Next-Gen Asset Allocation using LSTM & Mean-Variance Optimization</p>
        </header>

        <main className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: Inputs (3 cols wide on large screens) */}
          <div className="lg:col-span-4 xl:col-span-3 space-y-6">
            <SystemStatus health={systemHealth} />
            <OptimizationForm 
                tickers={tickers} 
                setTickers={setTickers}
                riskFreeRate={riskFreeRate} 
                setRiskFreeRate={setRiskFreeRate}
                minWeight={minWeight}
                setMinWeight={setMinWeight}
                onSubmit={handleSubmit}
                loading={loading}
            />
            <AvailableModelsList models={availableModels.loaded_models} />
          </div>

          {/* Right Column: Results (9 cols wide on large screens) */}
          <div className="lg:col-span-8 xl:col-span-9 space-y-6">
            
            {/* Error State */}
            {error && (
              <div className="p-4 rounded-lg bg-red-900/50 border border-red-500/50 text-red-200 shadow-lg backdrop-blur-sm">
                <div className="flex items-center gap-3">
                    <span className="text-2xl">⚠️</span>
                    <div>
                        <h4 className="font-bold">Optimization Error</h4>
                        <p className="text-sm opacity-90">{error}</p>
                    </div>
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && <LoadingSkeleton />}

            {/* Results State */}
            {result && (
              <div className="space-y-6 animate-fade-in">
                <ResultsSummary result={result} />

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    {/* Chart Card */}
                    <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700 flex flex-col">
                        <h4 className="text-xl font-semibold mb-4 text-white border-b border-gray-700 pb-2">Allocation Visual</h4>
                        <div className="flex-grow min-h-[300px] relative">
                            {pieChartData && <Pie data={pieChartData} options={pieChartOptions} />}
                        </div>
                    </div>

                    {/* Returns List Card */}
                    <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700 flex flex-col">
                         <h4 className="text-xl font-semibold mb-4 text-white border-b border-gray-700 pb-2">AI Return Predictions</h4>
                         <div className="overflow-y-auto max-h-[300px] pr-2 space-y-2 custom-scrollbar">
                            {Object.entries(result.expected_returns)
                                .sort(([,a], [,b]) => b - a)
                                .map(([ticker, returnVal]) => (
                                    <div key={ticker} className="flex justify-between items-center p-3 bg-gray-700/50 rounded-lg border border-gray-700/50">
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-teal-300">{ticker}</span>
                                            {result.details.prediction_errors?.includes(ticker) && (
                                                <span className="text-[10px] uppercase tracking-wider text-red-200 bg-red-800/60 px-1.5 py-0.5 rounded">Hist. Data</span>
                                            )}
                                        </div>
                                        <span className={`font-mono font-bold ${returnVal > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {formatPercent(returnVal)}
                                        </span>
                                    </div>
                                ))
                            }
                         </div>
                         <div className="mt-auto pt-4 text-xs text-gray-500">
                            * Predictions based on technical indicators & market sentiment features processed by LSTM.
                         </div>
                    </div>
                </div>

                {/* Detailed Table */}
                <AllocationTable weights={result.weights} expectedReturns={result.expected_returns} />
                
                {/* Metadata Footer */}
                <div className="text-center text-xs text-gray-500 pt-8">
                    Calculation performed in {(result.details.execution_time || 0).toFixed(2)}s | 
                    Covariance Matrix: {result.details.covariance_shape?.[0]}x{result.details.covariance_shape?.[1]}
                </div>
              </div>
            )}

            {/* Empty State / Intro */}
            {!loading && !result && !error && (
                 <div className="h-full flex flex-col items-center justify-center p-12 text-center bg-gray-800/50 rounded-xl border-2 border-dashed border-gray-700">
                    <div className="max-w-lg space-y-6">
                        <div className="text-6xl">📈</div>
                        <h3 className="text-2xl font-bold text-white">Ready to Optimize</h3>
                        <p className="text-gray-400">
                            Enter your desired stock tickers and risk parameters on the left. 
                            Our AI will analyze historical data and generate an mathematically optimal portfolio allocation.
                        </p>
                    </div>
                 </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;