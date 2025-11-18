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

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale);

// Define chart colors for consistency in the dark theme
const chartColors = [
    'rgba(75, 192, 192, 0.8)', // Teal
    'rgba(255, 99, 132, 0.8)', // Red
    'rgba(255, 205, 86, 0.8)', // Yellow
    'rgba(54, 162, 235, 0.8)', // Blue
    'rgba(153, 102, 255, 0.8)', // Purple
    'rgba(255, 159, 64, 0.8)', // Orange
    'rgba(201, 203, 207, 0.8)', // Gray
];

// Helper function to format percentages
const formatPercent = (value) => `${(value * 100).toFixed(2)}%`;

// Main Application Component
const App = () => {
  const [tickers, setTickers] = useState("AAPL,MSFT,GOOG,AMZN,META,TSLA,NVDA,JPM,JNJ,V");
  const [riskFreeRate, setRiskFreeRate] = useState(0.02);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);

  // Determine API base URL
  const apiBase = "http://localhost:8000";

  // Load available models on component mount
  useEffect(() => {
    fetchAvailableModels();
    checkSystemHealth();
  }, []);

  const fetchAvailableModels = async () => {
    try {
      const res = await axios.get(`${apiBase}/api/available_models`);
      setAvailableModels(res.data);
    } catch (err) {
      console.warn('Could not fetch available models:', err.message);
    }
  };

  const checkSystemHealth = async () => {
    try {
      const res = await axios.get(`${apiBase}/api/health`);
      setSystemHealth(res.data);
    } catch (err) {
      console.warn('Could not check system health:', err.message);
      setSystemHealth({ status: 'error', models_loaded: 0 });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    
    // Input validation
    if (!tickers.trim()) {
        setError("Please enter at least one ticker.");
        return;
    }

    setLoading(true);
    
    try {
      const res = await axios.post(`${apiBase}/api/optimize_portfolio`, {
        tickers,
        risk_free_rate: riskFreeRate,
      });
      setResult(res.data);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  // Memoize Pie Chart Data
  const pieChartData = useMemo(() => {
    if (!result || !result.weights) return null;

    const weights = result.weights;
    const labels = Object.keys(weights).filter(t => weights[t] > 0.0001);
    const dataPoints = labels.map(l => (weights[l] * 100));
    
    const backgroundColors = labels.map((_, index) => chartColors[index % chartColors.length]);
    const borderColors = backgroundColors.map(color => color.replace('0.8', '1'));

    return {
      labels,
      datasets: [{
        label: 'Optimal Weight (%)',
        data: dataPoints,
        backgroundColor: backgroundColors,
        borderColor: borderColors,
        borderWidth: 1,
      }],
    };
  }, [result]);

  const pieChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
        legend: {
            position: 'right',
            labels: {
                color: 'rgb(209, 213, 219)',
                font: { size: 14 }
            }
        },
        tooltip: {
            callbacks: {
                label: function(context) {
                    let label = context.label || '';
                    if (label) label += ': ';
                    if (context.parsed !== null) {
                        label += `${context.parsed.toFixed(2)}%`;
                    }
                    return label;
                }
            }
        }
    }
  };

  // Component to display main result metrics
  const ResultsSummary = () => {
    const portfolioReturn = result.details.portfolio_return ?? 0;
    const portfolioVolatility = result.details.portfolio_volatility ?? 0;
    const tickersUsedCount = (result.details.tickers_used ?? []).length;
    const modelsUsed = result.details.models_used ?? 0;

    return (
        <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700 space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-gray-700">
                <h4 className="text-xl font-semibold text-teal-400">Optimal Portfolio Metrics</h4>
                <span className="text-sm text-gray-400">
                    {modelsUsed} AI Models Used
                </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-white">
                <MetricCard title="Optimized Sharpe Ratio" value={result.sharpe.toFixed(4)} color="text-green-400" />
                <MetricCard title="Predicted Annual Return" value={formatPercent(portfolioReturn)} color="text-blue-400" />
                <MetricCard title="Portfolio Volatility" value={formatPercent(portfolioVolatility)} color="text-yellow-400" />
                <MetricCard title="Tickers Optimized" value={tickersUsedCount} color="text-purple-400" />
            </div>
        </div>
    );
  };
  
  // Reusable Metric Card
  const MetricCard = ({ title, value, color }) => (
    <div className="p-3 bg-gray-700 rounded-lg">
        <p className="text-sm font-medium text-gray-400">{title}</p>
        <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );

  // System Status Component
  const SystemStatus = () => (
    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${
            systemHealth?.status === 'ok' ? 'bg-green-500' : 'bg-red-500'
          }`}></div>
          <span className="text-sm text-gray-300">System Status</span>
        </div>
        <div className="text-xs text-gray-400">
          {systemHealth?.models_loaded || 0} models loaded
        </div>
      </div>
    </div>
  );

  // Available Models Component
  const AvailableModelsList = () => {
    if (!availableModels.loaded_models || availableModels.loaded_models.length === 0) {
      return null;
    }

    return (
      <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mt-4">
        <h4 className="text-sm font-medium text-gray-300 mb-2">Available AI Models</h4>
        <div className="flex flex-wrap gap-1">
          {availableModels.loaded_models.slice(0, 10).map((ticker) => (
            <span key={ticker} className="px-2 py-1 bg-teal-900 text-teal-300 rounded text-xs">
              {ticker}
            </span>
          ))}
          {availableModels.loaded_models.length > 10 && (
            <span className="px-2 py-1 bg-gray-700 text-gray-400 rounded text-xs">
              +{availableModels.loaded_models.length - 10} more
            </span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4 sm:p-8 font-inter">
      <script src="https://cdn.tailwindcss.com"></script>
      <style>
        {`
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
          .font-inter { font-family: 'Inter', sans-serif; }
          .shimmer {
              animation: shimmer 1.5s infinite linear;
              background: linear-gradient(to right, #4b5563 0%, #374151 50%, #4b5563 100%);
              background-size: 200% 100%;
          }
          @keyframes shimmer {
              0% { background-position: -200% 0; }
              100% { background-position: 200% 0; }
          }
        `}
      </style>
      <div className="max-w-6xl mx-auto">
        <header className="py-6 mb-8 text-center border-b border-gray-700">
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            <span className="text-teal-400">AI</span> Portfolio Optimizer
          </h1>
          <p className="text-gray-400 mt-2">Individual LSTM Models for Each Stock</p>
        </header>

        <main className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          
          {/* Optimization Form Column */}
          <div className="lg:col-span-1 space-y-4">
            <SystemStatus />
            
            <div className="p-6 bg-gray-800 rounded-xl shadow-2xl border border-gray-700 h-fit">
              <h2 className="text-2xl font-semibold mb-4 text-white border-b border-gray-700 pb-2">
                  Input Parameters
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="tickers" className="block text-sm font-medium text-gray-300 mb-1">
                    Stock Tickers (comma separated)
                  </label>
                  <input
                    id="tickers"
                    type="text"
                    value={tickers}
                    onChange={(e) => setTickers(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-teal-500 focus:border-teal-500 transition duration-150"
                    placeholder="AAPL, MSFT, GOOG, ..."
                    required
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Use any combination of available stocks
                  </p>
                </div>
                
                <div>
                  <label htmlFor="riskRate" className="block text-sm font-medium text-gray-300 mb-1">
                    Risk-Free Rate (Annual)
                  </label>
                  <input
                    id="riskRate"
                    type="number"
                    step="0.001"
                    value={riskFreeRate}
                    onChange={(e) => setRiskFreeRate(parseFloat(e.target.value))}
                    className="w-full px-4 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-teal-500 focus:border-teal-500 transition duration-150"
                    required
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Typically 0.02 (2%) for US Treasury bonds
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 mt-4 text-lg font-semibold rounded-lg text-gray-900 transition duration-300 
                             bg-teal-500 hover:bg-teal-400 disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed"
                >
                  {loading ? (
                      <span className="flex items-center justify-center">
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-900" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          AI Optimizing...
                      </span>
                  ) : (
                      "Optimize Portfolio"
                  )}
                </button>
              </form>

              <AvailableModelsList />
            </div>
          </div>

          {/* Results Column */}
          <div className="lg:col-span-3 space-y-8">
            {/* Error Display */}
            {error && (
              <div className="p-4 rounded-lg bg-red-800 text-red-200 border border-red-700 shadow-md">
                <h4 className="font-bold">Optimization Error</h4>
                <p className="text-sm">{error}</p>
                {error.includes("models") && (
                    <p className="mt-2 text-xs">
                        *Note: This may indicate that AI models for some tickers are not available.
                        Try using stocks from the available models list.
                    </p>
                )}
              </div>
            )}

            {/* Loading Skeleton */}
            {loading && (
                <div className="p-6 bg-gray-800 rounded-xl shadow-lg border border-gray-700 space-y-4">
                    <div className="h-6 w-3/4 shimmer rounded"></div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="h-10 shimmer rounded"></div>
                        <div className="h-10 shimmer rounded"></div>
                        <div className="h-10 shimmer rounded"></div>
                        <div className="h-10 shimmer rounded"></div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-6">
                        <div className="h-64 shimmer rounded"></div>
                        <div className="h-64 shimmer rounded"></div>
                    </div>
                </div>
            )}

            {/* Success Results */}
            {result && (
              <>
                <ResultsSummary />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* Weights (Pie Chart) */}
                    <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700">
                        <h4 className="text-xl font-semibold mb-4 text-white">Optimal Asset Allocation</h4>
                        <div className="flex justify-center h-64">
                             {pieChartData && <Pie data={pieChartData} options={pieChartOptions} />}
                        </div>
                        <div className="mt-4 text-sm text-gray-400">
                            <p>AI-powered allocation based on individual LSTM predictions</p>
                        </div>
                    </div>

                    {/* Predicted Returns and Details */}
                    <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700">
                        <h4 className="text-xl font-semibold mb-4 text-white">LSTM Predicted Returns (Annualized)</h4>
                        <div className="max-h-64 overflow-y-auto">
                          <ul className="space-y-2 text-gray-300">
                              {Object.entries(result.expected_returns)
                                .sort(([,a], [,b]) => b - a)
                                .map(([ticker, returnVal]) => (
                                  <li key={ticker} className="flex justify-between items-center p-2 bg-gray-700 rounded-lg">
                                      <div className="flex items-center space-x-2">
                                        <span className="font-medium text-lg text-teal-300">{ticker}</span>
                                        {result.details.prediction_errors?.includes(ticker) && (
                                          <span className="text-xs text-red-400 bg-red-900 px-1 rounded">Fallback</span>
                                        )}
                                      </div>
                                      <span className={`text-lg font-mono ${returnVal > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                          {formatPercent(returnVal)}
                                      </span>
                                  </li>
                              ))}
                          </ul>
                        </div>

                        {/* Details/Notes Section */}
                        <div className="mt-6 pt-4 border-t border-gray-700 text-sm text-gray-400">
                            <p className="font-semibold text-white">Optimization Details:</p>
                            <p>{result.details.note}</p>
                            {result.details.prediction_errors && result.details.prediction_errors.length > 0 && (
                                <p className="mt-2 text-yellow-400">
                                    ⚠️ {result.details.prediction_errors.length} stocks used historical data (AI model unavailable)
                                </p>
                            )}
                            <p className="mt-2">
                                Data Points: {result.details.returns_data_points || 'N/A'} | 
                                Covariance Matrix: {result.details.covariance_shape?.[0]}x{result.details.covariance_shape?.[1]}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Weights Table */}
                <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700">
                  <h4 className="text-xl font-semibold mb-4 text-white">Detailed Weights</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left text-gray-300">
                      <thead className="text-xs text-gray-400 uppercase bg-gray-700">
                        <tr>
                          <th className="px-4 py-3">Stock</th>
                          <th className="px-4 py-3">Weight</th>
                          <th className="px-4 py-3">Allocation</th>
                          <th className="px-4 py-3">Expected Return</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(result.weights)
                          .filter(([, weight]) => weight > 0.001)
                          .sort(([,a], [,b]) => b - a)
                          .map(([ticker, weight]) => (
                            <tr key={ticker} className="border-b border-gray-700 hover:bg-gray-750">
                              <td className="px-4 py-3 font-medium text-teal-300">{ticker}</td>
                              <td className="px-4 py-3">{formatPercent(weight)}</td>
                              <td className="px-4 py-3">
                                <div className="w-full bg-gray-700 rounded-full h-2">
                                  <div 
                                    className="bg-teal-500 h-2 rounded-full" 
                                    style={{ width: `${weight * 100}%` }}
                                  ></div>
                                </div>
                              </td>
                              <td className={`px-4 py-3 font-mono ${
                                result.expected_returns[ticker] > 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {formatPercent(result.expected_returns[ticker])}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
            
            {/* Empty State */}
            {!loading && !result && !error && (
                <div className="p-8 text-center bg-gray-800 rounded-xl shadow-lg border border-gray-700">
                    <div className="max-w-2xl mx-auto">
                      <h3 className="text-2xl font-bold text-white mb-4">AI Portfolio Optimization</h3>
                      <p className="text-gray-400 text-lg mb-4">
                        Enter stock tickers to get AI-driven portfolio allocation using individual LSTM models for each stock.
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-500">
                        <div>
                          <h4 className="font-semibold text-teal-400 mb-2">🤖 AI Models</h4>
                          <p>Individual LSTM model for each stock</p>
                        </div>
                        <div>
                          <h4 className="font-semibold text-teal-400 mb-2">📊 Modern Portfolio</h4>
                          <p>Mean-variance optimization</p>
                        </div>
                        <div>
                          <h4 className="font-semibold text-teal-400 mb-2">🔄 Real-time Data</h4>
                          <p>Automated data updates</p>
                        </div>
                      </div>
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