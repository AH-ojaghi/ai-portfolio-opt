# app/api.py
from contextlib import asynccontextmanager
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import logging
import os

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

class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_returns: Dict[str, float]
    sharpe: float
    details: Dict[str, Any]

# Lifecycle Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ایجاد دایرکتوری‌ها و لود مدل‌ها
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.MODELS_DIR, exist_ok=True)
    os.makedirs(settings.SCALERS_DIR, exist_ok=True)
    
    logger.info("🚀 System Startup: Loading Artifacts...")
    predictor.load_artifacts()
    yield
    # Shutdown logic if needed
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
    # فیلتر کردن داده‌ها برای مدل‌های موجود
    price_subset = price_df[valid_models]
    log_returns = import_numpy_log(price_subset)
    returns_clean = log_returns.dropna(how='any')

    if returns_clean.shape[0] < settings.WINDOW_SIZE_DEFAULT + 2:
         return _create_fallback_response(valid_models, details, "Insufficient history length")

    # مهندسی ویژگی
    try:
        # Winsorize
        rets_win = returns_clean.copy()
        for col in rets_win.columns:
            rets_win[col] = data_handler.winsorize_series(rets_win[col])
        
        # هم‌ترازی قیمت و بازده
        prices_aligned = price_subset.loc[returns_clean.index]
        features_df = data_handler.create_advanced_features(prices_aligned, rets_win)
    except Exception as e:
        return _create_fallback_response(valid_models, details, str(e), "Feature generation failed")

    # 5. Predict Returns
    preds, errors = predictor.predict_returns(valid_models, features_df)
    details["prediction_errors"] = errors
    
    # پر کردن مدل‌های ناموفق با میانگین تاریخی
    final_preds = {}
    for t in valid_models:
        if t in preds:
            final_preds[t] = preds[t] * 252 # سالانه‌سازی
        else:
            hist_mean = returns_clean[t].mean() * 252
            final_preds[t] = hist_mean
            details.setdefault("fallback_to_mean", []).append(t)

    mu = pd.Series(final_preds)

    # 6. Optimize
    try:
        S = optimizer.calculate_covariance(returns_clean, valid_models)
        weights, ret, vol, sharpe = optimizer.optimize(mu, S, req.risk_free_rate)
        
        details["note"] = "Success"
        details["portfolio_volatility"] = vol
        details["portfolio_return"] = ret
        
        return OptimizeResponse(
            weights=weights,
            expected_returns=mu.to_dict(),
            sharpe=sharpe,
            details=details
        )

    except Exception as e:
        logger.error(f"Optimization Failed: {e}")
        return _create_fallback_response(valid_models, details, str(e), "Optimization math failed")


def _create_fallback_response(tickers: List[str], details: dict, error_msg: str = "", note: str = ""):
    """ایجاد پاسخ پیش‌فرض (وزن‌های برابر) در صورت بروز خطا."""
    n = len(tickers)
    weights = {t: 1.0/n for t in tickers} if n > 0 else {}
    details["error"] = error_msg
    details["note"] = note
    return OptimizeResponse(
        weights=weights,
        expected_returns={t: 0.0 for t in tickers},
        sharpe=0.0,
        details=details
    )

def import_numpy_log(df):
    import numpy as np
    return np.log(df).diff().replace([np.inf, -np.inf], np.nan)

# --- Other Endpoints ---
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "models_loaded": len(predictor.models),
        "system_ready": len(predictor.models) >= 2
    }

@app.get("/api/available_models")
def get_models():
    return {
        "available_tickers": predictor.available_tickers,
        "loaded": list(predictor.models.keys())
    }