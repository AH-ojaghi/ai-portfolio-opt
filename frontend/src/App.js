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
  const [tickers, setTickers] = useState("AAPL,MSFT,GOOG,AMZN,META");
  const [riskFreeRate, setRiskFreeRate] = useState(0.02); // Use a standard rate
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Determine API base URL (assuming backend runs on 8000)
  const apiBase = "http://localhost:8000";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    
    // Simple input validation
    if (!tickers.trim()) {
        setError("Please enter at least one ticker.");
        return;
    }

    setLoading(true);
    
    try {
      // API call to the backend optimization endpoint
      const res = await axios.post(`${apiBase}/api/optimize_portfolio`, {
        tickers,
        risk_free_rate: riskFreeRate,
      });
      setResult(res.data);
    } catch (err) {
      // Handle API errors gracefully
      const detail = err.response?.data?.detail || err.message;
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  // Memoize Pie Chart Data for efficiency and to respect the dark theme
  const pieChartData = useMemo(() => {
    if (!result || !result.weights) return null;

    const weights = result.weights;
    const labels = Object.keys(weights).filter(t => weights[t] > 0.0001); // Filter negligible weights
    const dataPoints = labels.map(l => (weights[l] * 100));
    
    // Assign colors dynamically
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
                color: 'rgb(209, 213, 219)', // Tailwind gray-300 for dark theme
                font: {
                    size: 14,
                }
            }
        },
        tooltip: {
            callbacks: {
                label: function(context) {
                    let label = context.label || '';
                    if (label) {
                        label += ': ';
                    }
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
    // FIX: Use nullish coalescing (??) to safely access metrics which might be missing 
    // in fallback responses, defaulting to 0 or an empty array.
    
    // Fix 1 & 2: Safe access for Annual Return and Volatility, defaulting to 0.
    // FIX 3: Removed incorrect division by 252, as backend returns annualized values.
    const portfolioReturn = result.details.portfolio_return ?? 0;
    const portfolioVolatility = result.details.portfolio_volatility ?? 0;
    
    // Fix 4: Safe access for array length, defaulting to 0 if tickers_used is undefined.
    const tickersUsedCount = (result.details.tickers_used ?? []).length; 

    return (
        <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700 space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-gray-700">
                <h4 className="text-xl font-semibold text-teal-400">Optimal Portfolio Metrics</h4>
            </div>
            <div className="grid grid-cols-2 gap-4 text-white">
                <MetricCard title="Optimized Sharpe Ratio" value={result.sharpe.toFixed(4)} color="text-green-400" />
                {/* Fixed: Use portfolioReturn directly (it's already annualized) */}
                <MetricCard title="Predicted Annual Return" value={formatPercent(portfolioReturn)} color="text-blue-400" /> 
                {/* Fixed: Use portfolioVolatility directly (it's already annualized) */}
                <MetricCard title="Portfolio Volatility (Annual)" value={formatPercent(portfolioVolatility)} color="text-yellow-400" /> 
                {/* Fixed: Use safely calculated count */}
                <MetricCard title="Tickers Used" value={tickersUsedCount} color="text-purple-400" /> 
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
      <div className="max-w-4xl mx-auto">
        <header className="py-6 mb-8 text-center border-b border-gray-700">
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            <span className="text-teal-400">AI</span> Portfolio Optimizer
          </h1>
          <p className="text-gray-400 mt-2">LSTM-driven Mean-Variance Analysis</p>
        </header>

        <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Optimization Form Column */}
          <div className="lg:col-span-1 p-6 bg-gray-800 rounded-xl shadow-2xl border border-gray-700 h-fit">
            <h2 className="text-2xl font-semibold mb-4 text-white border-b border-gray-700 pb-2">
                Input Parameters
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="tickers" className="block text-sm font-medium text-gray-300 mb-1">
                  Tickers (e.g., AAPL, MSFT, GOOG)
                </label>
                <input
                  id="tickers"
                  type="text"
                  value={tickers}
                  onChange={(e) => setTickers(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-600 rounded-lg bg-gray-700 text-white focus:ring-teal-500 focus:border-teal-500 transition duration-150"
                  placeholder="Comma separated list"
                  required
                />
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
                        Optimizing...
                    </span>
                ) : (
                    "Optimize Portfolio"
                )}
              </button>
            </form>
          </div>

          {/* Results Column */}
          <div className="lg:col-span-2 space-y-8">
            {/* Error Display */}
            {error && (
              <div className="p-4 rounded-lg bg-red-800 text-red-200 border border-red-700 shadow-md">
                <h4 className="font-bold">Optimization Error</h4>
                <p className="text-sm">{error}</p>
                {/* Check for specific backend messages */}
                {error.includes("prediction_errors") && (
                    <p className="mt-2 text-xs">
                        *Note: A prediction error (or return 0.0) usually means the LSTM model encountered an issue 
                        or couldn't find enough historical data via yfinance for one or more tickers.
                    </p>
                )}
              </div>
            )}

            {/* Loading Skeleton */}
            {loading && (
                <div className="p-6 bg-gray-800 rounded-xl shadow-lg border border-gray-700 space-y-4">
                    <div className="h-6 w-3/4 shimmer rounded"></div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="h-10 shimmer rounded"></div>
                        <div className="h-10 shimmer rounded"></div>
                        <div className="h-10 shimmer rounded"></div>
                        <div className="h-10 shimmer rounded"></div>
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
                        <h4 className="text-xl font-semibold mb-4 text-white">Optimal Asset Allocation (Weights)</h4>
                        <div className="flex justify-center h-64">
                             {pieChartData && <Pie data={pieChartData} options={pieChartOptions} />}
                        </div>
                    </div>

                    {/* Predicted Returns and Details */}
                    <div className="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700">
                        <h4 className="text-xl font-semibold mb-4 text-white">LSTM Predicted Returns (Annualized)</h4>
                        <ul className="space-y-2 text-gray-300">
                            {Object.entries(result.expected_returns).map(([t, r]) => (
                                <li key={t} className="flex justify-between items-center p-2 bg-gray-700 rounded-lg">
                                    <span className="font-medium text-lg text-teal-300">{t}</span>
                                    {/* Returns are stored annualized in the backend, but returned daily in the prediction (mu is annualized later) */}
                                    <span className={`text-lg font-mono ${r > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {formatPercent(r)}
                                    </span>
                                </li>
                            ))}
                        </ul>

                        {/* Details/Notes Section */}
                        <div className="mt-6 pt-4 border-t border-gray-700 text-sm text-gray-400">
                            <p className="font-semibold text-white">Model Note:</p>
                            <p>{result.details.note}</p>
                            {result.details.prediction_errors && result.details.prediction_errors.length > 0 && (
                                <p className="mt-1 text-red-400">
                                    Prediction Errors: {result.details.prediction_errors.join(', ')} (Returns defaulted to 0.0)
                                </p>
                            )}
                        </div>
                    </div>
                </div>
              </>
            )}
            
            {!loading && !result && !error && (
                <div className="p-8 text-center bg-gray-800 rounded-xl shadow-lg border border-gray-700">
                    <p className="text-gray-400 text-lg">
                        Enter your desired stock **Tickers** and click **Optimize Portfolio** to get the LSTM-driven Markowitz allocation.
                    </p>
                    <p className="text-sm text-gray-500 mt-2">
                        Requires a running backend server on `http://localhost:8000`.
                    </p>
                </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;