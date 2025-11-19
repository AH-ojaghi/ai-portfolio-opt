# app/api.py
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd
import logging
import os
import math
import numpy as np

from app.core.config import settings
from app.data_handler import DataHandler
from app.model_predictor import ModelPredictor
from app.portfolio_optimizer import PortfolioOptimizer

# تنظیم لاگینگ
logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT)
logger = logging.getLogger("ai-backend")

# نمونه‌سازی از کلاس‌های Core
data_handler = DataHandler()
predictor = ModelPredictor()
optimizer = PortfolioOptimizer()

# Pydantic Models
class OptimizeRequest(BaseModel):
    tickers: str
    risk_free_rate: float = 0.0
    # فیلد جدید: حداقل وزن برای هر سهم (پیش‌فرض 0 یعنی محدودیتی نیست)
    min_weight: float = Field(0.0, ge=0.0, le=0.5, description="Minimum weight per asset (0.0 to 0.5)")

class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_returns: Dict[str, float]
    sharpe: float
    details: Dict[str, Any]

def sanitize_response(data: Any) -> Any:
    """تبدیل مقادیر NaN و Infinity به None یا صفر برای جلوگیری از خطای JSON."""
    if isinstance(data, dict):
        return {k: sanitize_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_response(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return 0.0 
        return data
    elif isinstance(data, np.generic):
        val = data.item()
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
             return 0.0
        return val
    return data

# Lifecycle Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.MODELS_DIR, exist_ok=True)
    os.makedirs(settings.SCALERS_DIR, exist_ok=True)
    logger.info("🚀 System Startup: Loading Artifacts...")
    predictor.load_artifacts()
    yield
    logger.info("🛑 System Shutdown")

app = FastAPI(title="AI Portfolio Optimizer (Modular)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---

@app.post("/api/optimize_portfolio", response_model=OptimizeResponse)
def optimize_portfolio_endpoint(req: OptimizeRequest):
    details = {"note": "Optimization initiated."}
    
    # 1. Parse Tickers
    requested_tickers = [t.strip().upper() for t in req.tickers.split(",") if t.strip()]
    if len(requested_tickers) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 tickers.")

    # 2. Load & Clean Data
    try:
        price_df = data_handler.read_and_clean_market_data()
    except Exception as e:
        logger.error(f"Data Error: {e}")
        return _create_fallback_response(requested_tickers, details, str(e), "Data load failed")

    # 3. Filter Valid Models
    available_tickers = [t for t in requested_tickers if t in price_df.columns]
    valid_models = predictor.get_valid_tickers(available_tickers)
    
    if len(valid_models) < 2:
        details["note"] = "Insufficient valid models/data."
        details["valid_models"] = valid_models
        return _create_fallback_response(requested_tickers, details, "Not enough valid models")

    # 4. Prepare Returns & Features
    price_subset = price_df[valid_models]
    log_returns = np.log(price_subset).diff().replace([np.inf, -np.inf], np.nan)
    returns_clean = log_returns.dropna(how='any')

    if returns_clean.shape[0] < settings.WINDOW_SIZE_DEFAULT + 2:
         return _create_fallback_response(valid_models, details, "Insufficient history length")

    # مهندسی ویژگی
    try:
        rets_win = returns_clean.copy()
        for col in rets_win.columns:
            rets_win[col] = data_handler.winsorize_series(rets_win[col])
        
        prices_aligned = price_subset.loc[returns_clean.index]
        features_df = data_handler.create_advanced_features(prices_aligned, rets_win)
    except Exception as e:
        return _create_fallback_response(valid_models, details, str(e), "Feature generation failed")

    # 5. Predict Returns
    preds, errors = predictor.predict_returns(valid_models, features_df)
    details["prediction_errors"] = errors
    
    final_preds = {}
    for t in valid_models:
        if t in preds and not (math.isnan(preds[t]) or math.isinf(preds[t])):
            final_preds[t] = preds[t] * 252 
        else:
            hist_mean = returns_clean[t].mean() * 252
            final_preds[t] = hist_mean if not math.isnan(hist_mean) else 0.0
            details.setdefault("fallback_to_mean", []).append(t)

    mu = pd.Series(final_preds)

    # 6. Optimize (Passed min_weight here)
    try:
        S = optimizer.calculate_covariance(returns_clean, valid_models)
        # تغییر: ارسال پارامتر min_weight به تابع optimize
        weights, ret, vol, sharpe = optimizer.optimize(mu, S, req.risk_free_rate, req.min_weight)
        
        details["note"] = "Success"
        details["portfolio_volatility"] = vol
        details["portfolio_return"] = ret
        
        response_data = {
            "weights": weights,
            "expected_returns": mu.to_dict(),
            "sharpe": sharpe,
            "details": details
        }
        return OptimizeResponse(**sanitize_response(response_data))

    except Exception as e:
        logger.error(f"Optimization Failed: {e}")
        return _create_fallback_response(valid_models, details, str(e), "Optimization math failed")


def _create_fallback_response(tickers: List[str], details: dict, error_msg: str = "", note: str = ""):
    n = len(tickers)
    weights = {t: 1.0/n for t in tickers} if n > 0 else {}
    details["error"] = error_msg
    details["note"] = note
    
    response_data = {
        "weights": weights,
        "expected_returns": {t: 0.0 for t in tickers},
        "sharpe": 0.0,
        "details": details
    }
    return OptimizeResponse(**sanitize_response(response_data))