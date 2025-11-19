# app/model_predictor.py
import os
import json
import joblib
import numpy as np
import pandas as pd
import logging
# تغییر مهم: اضافه شدن Tuple به لیست زیر
from typing import Dict, List, Any, Optional, Tuple 
from keras.saving import load_model
from app.core.config import settings

logger = logging.getLogger("ai-backend")

class ModelPredictor:
    """
    مدیریت بارگذاری مدل‌های LSTM، اسکالرها و انجام پیش‌بینی.
    """
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.feature_info: Dict[str, Any] = {}
        self.available_tickers: List[str] = []
        self.window_size: int = settings.WINDOW_SIZE_DEFAULT

    def load_artifacts(self):
        """بارگذاری تمام مدل‌ها و اسکالرهای موجود در دایرکتوری."""
        try:
            if settings.FEATURES_FILE.exists():
                with open(settings.FEATURES_FILE, "r") as f:
                    self.feature_info = json.load(f)
                self.available_tickers = self.feature_info.get('tickers', [])
                self.window_size = int(self.feature_info.get("window_size", settings.WINDOW_SIZE_DEFAULT))
                logger.info(f"✅ Feature info loaded. Window size: {self.window_size}")
            else:
                logger.warning("Feature file not found.")

            for ticker in self.available_tickers:
                self._load_single_ticker(ticker)

            logger.info(f"🎯 Loaded {len(self.models)} models and {len(self.scalers)} scalers.")
            
        except Exception as e:
            logger.error(f"💥 Critical error loading artifacts: {e}")

    def _load_single_ticker(self, ticker: str):
        """بارگذاری مدل و اسکالر برای یک تیکر خاص."""
        model_path = settings.MODELS_DIR / f"{ticker}_model.keras"
        scaler_path = settings.SCALERS_DIR / f"{ticker}_scaler.pkl"

        # Load Model
        if model_path.exists():
            try:
                self.models[ticker] = load_model(str(model_path), safe_mode=False)
            except Exception as e:
                logger.error(f"❌ Failed to load model for {ticker}: {e}")

        # Load Scaler
        if scaler_path.exists():
            try:
                self.scalers[ticker] = joblib.load(str(scaler_path))
            except Exception as e:
                logger.error(f"❌ Failed to load scaler for {ticker}: {e}")

    def get_valid_tickers(self, requested: List[str]) -> List[str]:
        """برگرداندن لیست تیکرهایی که هم مدل و هم اسکالر دارند."""
        return [t for t in requested if t in self.models and t in self.scalers]

    def prepare_sequence(self, ticker: str, features_df: pd.DataFrame) -> np.ndarray:
        """آماده‌سازی توالی داده برای ورودی به LSTM."""
        common_features = self.feature_info.get('common_features', [])
        if not common_features:
             raise RuntimeError("Common features configuration missing.")

        # استخراج نام ستون‌های مخصوص تیکر
        ticker_cols = [f"{feat}__{ticker}" for feat in common_features]
        missing = [c for c in ticker_cols if c not in features_df.columns]
        if missing:
            raise ValueError(f"Missing columns for {ticker}: {missing}")

        # انتخاب داده‌ها
        X_ticker = features_df[ticker_cols].values
        if len(X_ticker) < self.window_size:
            raise ValueError(f"Insufficient data for {ticker}. Need {self.window_size}, got {len(X_ticker)}")

        X_recent = X_ticker[-self.window_size:]
        
        # مقیاس‌دهی
        scaler = self.scalers[ticker]
        X_scaled = scaler.transform(X_recent)
        
        # Reshape (1, window, features)
        return X_scaled.reshape(1, self.window_size, -1)

    def predict_returns(self, tickers: List[str], features_df: pd.DataFrame) -> Tuple[Dict[str, float], List[str]]:
        """
        اجرای پیش‌بینی برای لیست تیکرها.
        خروجی: (دیکشنری پیش‌بینی‌ها، لیست خطاهای رخ داده)
        """
        predictions = {}
        errors = []

        for ticker in tickers:
            try:
                seq = self.prepare_sequence(ticker, features_df)
                model = self.models[ticker]
                pred = model.predict(seq, verbose=0)
                predictions[ticker] = float(pred.ravel()[0])
            except Exception as e:
                logger.warning(f"Prediction failed for {ticker}: {e}")
                errors.append(ticker)
                
        return predictions, errors