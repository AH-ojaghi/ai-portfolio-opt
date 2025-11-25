import numpy as np
import pandas as pd
import yfinance as yf
import riskfolio as rp
from pydantic import BaseModel
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class OptimizationRequest(BaseModel):
    tickers: List[str]
    start_date: str = "2018-01-01"

def fetch_data(tickers: List[str], start_date: str):
    # Download data
    data = yf.download(tickers, start=start_date, progress=False)
    # Handle different yfinance return structures
    if 'Adj Close' in data:
        prices = data['Adj Close']
    elif 'Close' in data:
        prices = data['Close']
    else:
        prices = data
    
    prices = prices.dropna()
    returns = prices.pct_change().dropna()
    return prices, returns

def run_hrp_optimization(tickers: List[str]):
    try:
        # 1. Fetch Data
        prices, returns = fetch_data(tickers, "2018-01-01")
        
        if returns.empty or len(returns.columns) < 2:
            raise ValueError("Insufficient data or assets found.")

        # 2. HRP Model (From Notebook Cell 5 & 10)
        # We use HCPortfolio for HRP
        port = rp.HCPortfolio(returns=returns)
        
        # Optimization
        # model='HRP', rm='MV' (Variance), linkage='ward'
        weights = port.optimization(
            model='HRP', 
            rm='MV', 
            rf=0.04, 
            linkage='ward', 
            max_k=10, 
            leaf_order=True
        )
        
        # 3. Backtest for Performance Metrics (From Notebook Cell 8)
        # Weights is a dataframe, we need a series
        w_series = weights.iloc[:, 0]
        
        portfolio_returns = returns.dot(w_series)
        cum_returns = (1 + portfolio_returns).cumprod()
        
        total_return = cum_returns.iloc[-1] - 1
        annual_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1
        annual_vol = portfolio_returns.std() * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0
        max_dd = (cum_returns / cum_returns.cummax() - 1).min()

        # 4. Format Output
        # Weights > 1%
        clean_weights = w_series[w_series >= 0.01].sort_values(ascending=False).to_dict()
        
        # Chart Data
        chart_data = []
        # Downsample for chart performance (every 5th day)
        for date, value in cum_returns.iloc[::5].items():
            chart_data.append({"date": date.strftime("%Y-%m-%d"), "value": round((value - 1) * 100, 2)})

        return {
            "status": "success",
            "weights": clean_weights,
            "metrics": {
                "annual_return": round(annual_return * 100, 2),
                "volatility": round(annual_vol * 100, 2),
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(max_dd * 100, 2)
            },
            "history": chart_data
        }

    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return {"status": "error", "message": str(e)}
