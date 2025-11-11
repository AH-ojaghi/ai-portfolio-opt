import os
import json
import traceback
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
# NEW IMPORT: Add CORS middleware to handle cross-origin requests (Fixes 405 error from frontend)
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
import pandas as pd
import numpy as np
import joblib

# Keras 3 loading API
from keras.saving import load_model

from pypfopt import EfficientFrontier, risk_models

# ---------- تنظیم لاگینگ (Logging Setup) ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ai-backend")

# ---------- مسیرها و پارامترها (Paths and Parameters) ----------
MODEL_DIR = os.environ.get("MODEL_ARTIFACTS_DIR", "/app/model_artifacts")
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
MARKET_DATA_FILE = os.path.join(DATA_DIR, "market_data.csv")

MODEL_FILE = os.path.join(MODEL_DIR, "lstm_model.keras")  # فایل پیشنهادی برای Keras3
SCALER_FILE = os.path.join(MODEL_DIR, "scaler.pkl")
FEATURES_FILE = os.path.join(MODEL_DIR, "feature_cols.json")

# اگر ستونی بیش از این نسبت missing داشته باشد حذف می‌شود
COL_MISSING_THRESHOLD = float(os.environ.get("COL_MISSING_THRESHOLD", "0.5"))

# مسیر debug در صورت بروز مشکل در داده‌ها
DEBUG_RETURNS_CSV = os.path.join(DATA_DIR, "debug_returns.csv")
DEBUG_PRICE_CSV = os.path.join(DATA_DIR, "debug_price_df.csv")

app = FastAPI(title="AI Portfolio Optimizer (robust)")

# --- FIX: Add CORS Middleware (Critical for Frontend Communication) ---
# Allow all origins, methods, and headers for development environment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (including POST and OPTIONS)
    allow_headers=["*"],  # Allows all headers
)
# -------------------------------------------------------------------

# آرتیفکت‌ها (جهانی) - Global artifacts
model = None
scaler = None
feature_info = None

# ---------- Pydantic models ----------
class OptimizeRequest(BaseModel):
    tickers: str
    risk_free_rate: float = 0.0


class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_returns: Dict[str, float]
    sharpe: float
    details: Dict[str, Any]


# ---------- بارگذاری آرتیفکت‌ها (ایمن) - Safe Artifact Loading ----------
def load_artifacts_safe():
    global model, scaler, feature_info
    try:
        if os.path.exists(MODEL_FILE):
            # Use safe_mode=False for custom objects/layers in Keras 3
            model = load_model(MODEL_FILE, safe_mode=False)
            logger.info("✅ Model loaded successfully.")
        else:
            logger.warning(f"Model file not found at {MODEL_FILE} — model remains None.")

        if os.path.exists(SCALER_FILE):
            scaler = joblib.load(SCALER_FILE)
            logger.info("✅ Scaler loaded successfully.")
        else:
            logger.warning(f"Scaler file not found at {SCALER_FILE} — scaler remains None.")

        if os.path.exists(FEATURES_FILE):
            with open(FEATURES_FILE, "r") as f:
                feature_info = json.load(f)
            logger.info("✅ Feature info loaded successfully.")
        else:
            logger.warning(f"feature_cols.json not found at {FEATURES_FILE} — feature_info remains None.")

    except Exception as e:
        logger.error("Error loading artifacts: %s", e)
        traceback.print_exc()


@app.on_event("startup")
def startup_event():
    os.makedirs(DATA_DIR, exist_ok=True)
    load_artifacts_safe()


# ---------- توابع کمکی پاکسازی و آماده‌سازی (Utility Functions) ----------
def read_and_clean_market_data():
    """
    خواندن CSV بازار و پاکسازی:
    - حذف ردیف‌هایی که تاریخ ندارند یا header تکراری‌اند
    - تبدیل به عدد و حذف ستون‌های خیلی ناقص
    - بازگرداندن DataFrame با index تاریخ و مقادیر عددی
    """
    if not os.path.exists(MARKET_DATA_FILE):
        raise FileNotFoundError(f"Market data file not found at {MARKET_DATA_FILE}")

    # خواندن اولیه به عنوان رشته تا از هر نوع بی‌نظمی جلوگیری شود
    df_raw = pd.read_csv(MARKET_DATA_FILE, dtype=str, keep_default_na=False, na_values=[""])

    if "Date" not in df_raw.columns:
        raise ValueError("CSV does not contain 'Date' column")

    # حذف ردیف‌هایی که Date خالی یا نامعتبر است (مثلاً header تکراری)
    def try_parse_date(x):
        try:
            return pd.to_datetime(x)
        except Exception:
            return pd.NaT

    df_raw["Date_parsed"] = df_raw["Date"].apply(try_parse_date)
    df_valid = df_raw[df_raw["Date_parsed"].notna()].copy()
    if df_valid.empty:
        raise ValueError("No valid date rows found in market_data.csv after cleaning")

    # استفاده از Date_parsed به عنوان index
    df_valid["Date"] = pd.to_datetime(df_valid["Date_parsed"])
    df_valid.drop(columns=["Date_parsed"], inplace=True)
    df_valid.set_index("Date", inplace=True)

    # تبدیل مقادیر به عددی (هر چیز نامعتبر -> NaN)
    df_num = df_valid.apply(pd.to_numeric, errors="coerce")

    # حذف ستون‌هایی که بیش از آستانه missing دارند
    col_missing = df_num.isna().mean()
    cols_to_drop = col_missing[col_missing > COL_MISSING_THRESHOLD].index.tolist()
    if cols_to_drop:
        logger.warning("Dropping columns with >%s missing: %s", COL_MISSING_THRESHOLD, cols_to_drop)
        df_num.drop(columns=cols_to_drop, inplace=True)

    # حذف ردیف‌هایی که کاملاً NaN هستند
    df_num = df_num.dropna(axis=0, how="all")

    if df_num.empty:
        raise ValueError("After cleaning, market_data.csv contains no numeric price data")

    return df_num


def prepare_sequence(series: pd.Series, window: int):
    """
    آماده‌سازی توالی برای LSTM:
    - حذف NaN
    - تبدیل به آرایه و اعمال اسکالر
    - padding در صورت نیاز
    - خروجی شکل (1, window, 1)
    """
    if scaler is None:
        raise RuntimeError("Scaler not loaded")

    s = series.dropna().astype(float)
    if s.empty:
        raise ValueError("Series is empty after dropna")

    arr = s.values.reshape(-1, 1)
    try:
        scaled = scaler.transform(arr)
    except Exception as e:
        # خطای تبدیل اسکالر را بسته‌بندی می‌کنیم تا debug آسان‌تر شود
        raise RuntimeError(f"Scaler.transform failed: {e}")

    # Handle short sequences by padding (using the first available value)
    if len(scaled) < window:
        pad_amount = window - len(scaled)
        # Pad with the earliest available scaled value
        pad = np.repeat(scaled[0:1, :], pad_amount, axis=0) 
        scaled = np.vstack([pad, scaled])
    
    # Take only the last 'window' observations
    seq = scaled[-window:].reshape(1, -1, 1)
    return seq


# ---------- تابع اصلی بهینه‌سازی (Main Optimization Function) ----------
@app.post("/api/optimize_portfolio", response_model=OptimizeResponse)
def optimize_portfolio(req: OptimizeRequest):
    """
    ورودی:
      - tickers: رشته‌ای کاما-جدا (مثال: "AAPL,MSFT,GOOG")
      - risk_free_rate: نرخ بدون ریسک برای شارپ
    خروجی:
      - وزن‌ها، بازده‌های مورد انتظار سالیانه، sharpe، و details شامل پیام خطا/fallback
    """

    # بررسی ورودی ابتدایی
    tickers = [t.strip().upper() for t in req.tickers.split(",") if t.strip()]
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 tickers.")

    details: Dict[str, Any] = {"note": "Optimization successful."}
    
    # 1. خواندن و پاکسازی داده‌ها (Read and Clean Data)
    try:
        price_df = read_and_clean_market_data()
        logger.info("Price DF shape after cleaning: %s", price_df.shape)
    except Exception as e:
        logger.error("Error reading/cleaning market data: %s", e)
        traceback.print_exc()
        # Fallback to uniform weights
        n = len(tickers)
        equal_weights = {t: 1/n for t in tickers}
        details["note"] = "Market data missing/invalid. Returned uniform weights."
        details["error"] = str(e)
        return OptimizeResponse(weights=equal_weights, expected_returns={t: 0.0 for t in tickers}, sharpe=0.0, details=details)

    # 2. بررسی تیکرهای موجود (Check Tickers)
    available_tickers = [t for t in tickers if t in price_df.columns]
    missing = [t for t in tickers if t not in price_df.columns]
    
    if len(available_tickers) < 2:
        logger.warning("Insufficient available tickers after cleaning: %s", available_tickers)
        n = len(tickers)
        equal_weights = {t: 1/n for t in tickers}
        details["note"] = "Insufficient valid tickers available in market data after cleaning."
        details["missing_tickers"] = missing
        return OptimizeResponse(weights=equal_weights, expected_returns={t: 0.0 for t in tickers}, sharpe=0.0, details=details)

    # Filter DF and clean returns
    price_df = price_df[available_tickers].dropna(axis=0, how="all")
    returns = price_df.pct_change().replace([np.inf, -np.inf], np.nan)
    returns_clean = returns.dropna(how="any")
    
    # Check data sufficiency for covariance
    if returns_clean.shape[0] < 2:
        logger.warning("Insufficient valid returns after cleaning: %s", returns_clean.shape[0])
        n = len(available_tickers)
        equal_weights = {t: 1/n for t in available_tickers}
        details["note"] = "Insufficient valid returns after cleaning for covariance calculation."
        details["rows_after_clean"] = int(returns_clean.shape[0])
        return OptimizeResponse(weights=equal_weights, expected_returns={t: 0.0 for t in available_tickers}, sharpe=0.0, details=details)

    # 3. بررسی مدل (Check Model Artifacts)
    if model is None or scaler is None or feature_info is None:
        logger.warning("Model or scaler or feature_info not loaded. Using historical mean return as fallback.")
        details["note"] = "Model/scaler/feature_info not loaded; used historical returns and uniform weights."
        
        # Fallback to historical mean returns
        mu_hist = returns_clean.mean() * 252
        S = risk_models.sample_cov(returns_clean) * 252
        
        ef = EfficientFrontier(mu_hist, S)
        ef.max_sharpe(risk_free_rate=req.risk_free_rate)
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False, risk_free_rate=req.risk_free_rate)
        sharpe = float(perf[2])

        return OptimizeResponse(
            weights={k: float(v) for k, v in cleaned.items()},
            expected_returns=mu_hist.to_dict(),
            sharpe=sharpe,
            details={"note": details["note"], "covariance_shape": S.shape}
        )
    
    # 4. پیش‌بینی بازده‌ها با LSTM (Predict Returns)
    predicted_returns: Dict[str, float] = {}
    prediction_errors: List[str] = []
    window = int(feature_info.get("window", 30))
    
    try:
        for t in available_tickers:
            try:
                series = price_df[t].dropna()
                if series.empty:
                    raise RuntimeError(f"No price series available for ticker {t}.")
                
                # Check for sufficient history
                if len(series) < window:
                    raise RuntimeError(f"Insufficient history ({len(series)}/{window}) for ticker {t}.")

                seq = prepare_sequence(series, window)
                pred = model.predict(seq, verbose=0)
                val = float(pred.ravel()[0])
                predicted_returns[t] = val
            except Exception as e:
                logger.warning(f"Prediction failed for {t}: {e}. Setting return to 0.0.")
                prediction_errors.append(t)
                predicted_returns[t] = 0.0

        logger.info("Predicted returns (daily): %s", predicted_returns)
        details["prediction_errors"] = prediction_errors

        # annualize predicted daily returns
        mu = pd.Series({t: predicted_returns[t] * 252 for t in available_tickers})

    except Exception as e:
        # Catch any structural error during the prediction loop
        logger.error("Prediction loop failed: %s", e)
        traceback.print_exc()
        n = len(available_tickers)
        equal_weights = {t: 1/n for t in available_tickers}
        details["note"] = "Prediction failed (structural error); returned uniform weights."
        details["prediction_error"] = str(e)
        return OptimizeResponse(weights=equal_weights, expected_returns={t: 0.0 for t in available_tickers}, sharpe=0.0, details=details)

    # 5. محاسبه ماتریس کوواریانس (Calculate Covariance Matrix)
    try:
        S = risk_models.sample_cov(returns_clean[available_tickers]) * 252
    except Exception as e:
        logger.error("Covariance calculation failed: %s", e)
        traceback.print_exc()
        n = len(available_tickers)
        equal_weights = {t: 1/n for t in available_tickers}
        details["note"] = "Covariance calculation failed; returned uniform weights."
        details["cov_error"] = str(e)
        return OptimizeResponse(weights=equal_weights, expected_returns=mu.to_dict(), sharpe=0.0, details=details)

    # اطمینان از مقادیر متناهی در S
    if not np.all(np.isfinite(S.values)):
        bad = int((~np.isfinite(S.values)).sum())
        logger.error("Covariance contains non-finite values: %s", bad)
        details["note"] = "Covariance contains non-finite values; returned uniform weights."
        details["non_finite_cov_count"] = bad
        n = len(available_tickers)
        equal_weights = {t: 1/n for t in available_tickers}
        return OptimizeResponse(weights=equal_weights, expected_returns=mu.to_dict(), sharpe=0.0, details=details)
    
    # 6. اجرای بهینه‌سازی (Run Optimization)
    try:
        # Remove tickers with zero return for optimization stability if necessary
        optimizable_tickers = mu[mu > 0].index.tolist()
        if not optimizable_tickers:
             logger.warning("All predicted returns non-positive or zero. Returning uniform weights on all available tickers.")
             n = len(available_tickers)
             equal_weights = {t: 1/n for t in available_tickers}
             details["note"] = "All predicted returns non-positive/zero; returned uniform weights on all available tickers."
             details["predicted_returns_summary"] = predicted_returns
             return OptimizeResponse(weights=equal_weights, expected_returns=mu.to_dict(), sharpe=0.0, details=details)

        # Filter mu and S to only include tickers with positive returns for Max Sharpe calculation
        mu_opt = mu.loc[optimizable_tickers]
        S_opt = S.loc[optimizable_tickers, optimizable_tickers]

        ef = EfficientFrontier(mu_opt, S_opt)
        ef.max_sharpe(risk_free_rate=req.risk_free_rate)
        cleaned = ef.clean_weights()
        
        # Get portfolio performance using the cleaned weights
        # We need to re-run performance calculation on the full mu/S if we want annual return/volatility metrics
        
        # Create a full weight dictionary (zero for non-optimized assets)
        full_weights = {t: cleaned.get(t, 0.0) for t in available_tickers}
        
        # Calculate full portfolio performance using all available assets' mu and S
        
        # Reinitialize EF with full mu and S for performance calculation
        ef_full = EfficientFrontier(mu, S)
        # Set the optimized weights (including zeros for dropped assets)
        ef_full.set_weights(full_weights) 
        
        # Performance calculation
        ann_return, ann_volatility, sharpe = ef_full.portfolio_performance(
            verbose=False, 
            risk_free_rate=req.risk_free_rate
        )
        
        logger.info("Optimization success. Sharpe: %s", sharpe)

        return OptimizeResponse(
            weights={k: float(v) for k, v in full_weights.items()},
            expected_returns=mu.to_dict(),
            sharpe=float(sharpe),
            details={
                "note": details["note"],
                "covariance_shape": S.shape, 
                "returns_data_points": int(returns_clean.shape[0]),
                "tickers_used": available_tickers, # Added for frontend
                "portfolio_return": float(ann_return), # Added for frontend
                "portfolio_volatility": float(ann_volatility) # Added for frontend
            }
        )
    except Exception as e:
        logger.error("Optimization numeric failure: %s", e)
        traceback.print_exc()
        # fallback uniform weights
        n = len(available_tickers)
        equal_weights = {t: 1/n for t in available_tickers}
        details["note"] = "Optimization numeric failure; returned uniform weights."
        details["optimization_error"] = str(e)
        details["covariance_shape"] = S.shape
        details["returns_data_points"] = int(returns_clean.shape[0])
        details["tickers_used"] = available_tickers
        return OptimizeResponse(weights=equal_weights, expected_returns=mu.to_dict(), sharpe=0.0, details=details)


# ---------- health endpoint ----------
@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}