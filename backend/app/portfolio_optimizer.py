# app/portfolio_optimizer.py
import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Tuple
from pypfopt import EfficientFrontier, risk_models

logger = logging.getLogger("ai-backend")

class PortfolioOptimizer:
    """
    اجرای بهینه‌سازی میانگین-واریانس (Mean-Variance Optimization).
    """

    def calculate_covariance(self, returns_df: pd.DataFrame, tickers: list) -> pd.DataFrame:
        """محاسبه ماتریس کوواریانس نمایی با کنترل خطا."""
        try:
            data = returns_df[tickers].astype(float)
            S = risk_models.exp_cov(data, frequency=252)
            
            if not np.all(np.isfinite(S.values)):
                logger.warning("⚠️ Covariance matrix contains non-finite values. Attempting cleanup...")
                S = S.fillna(0) 
                S.replace([np.inf, -np.inf], 0, inplace=True)
            
            for i in range(len(S)):
                if S.iloc[i, i] <= 1e-6:
                    S.iloc[i, i] = 1e-4

            if not np.all(np.isfinite(S.values)):
                raise ValueError("Covariance matrix contains non-finite values even after fix.")
            
            return S
        except Exception as e:
            logger.error(f"Covariance calculation error: {e}")
            raise

    def optimize(self, 
                 expected_returns: pd.Series, 
                 covariance_matrix: pd.DataFrame, 
                 risk_free_rate: float,
                 min_weight: float = 0.0) -> Tuple[Dict[str, float], float, float, float]:
        """
        بهینه‌سازی با اعمال محدودیت حداقل وزن (min_weight).
        """
        num_assets = len(expected_returns)
        
        # --- اصلاح هوشمند حداقل وزن ---
        # اگر تعداد سهم‌ها زیاد باشد و min_weight هم زیاد باشد، جمع وزن‌ها بیشتر از ۱ می‌شود.
        # مثال: 5 سهم با حداقل 0.25 = 1.25 (غیرممکن)
        # در این حالت، min_weight را کاهش می‌دهیم تا مسئله قابل حل باشد.
        max_possible_min_weight = 0.99 / num_assets if num_assets > 0 else 0
        if min_weight > max_possible_min_weight:
            logger.warning(f"⚠️ Requested min_weight {min_weight} is too high for {num_assets} assets. Adjusted to {max_possible_min_weight:.4f}")
            min_weight = max_possible_min_weight

        # تعیین محدوده وزن‌ها: (حداقل, حداکثر)
        # حداکثر ۱.۰ است.
        current_bounds = (min_weight, 1.0)

        # اگر همه بازده‌ها منفی هستند
        if (expected_returns <= 0).all():
             logger.warning("All expected returns are negative/zero. Returning equal weights.")
             n = len(expected_returns)
             return {t: 1.0/n for t in expected_returns.index}, 0.0, 0.0, 0.0

        valid_tickers = expected_returns.index.tolist()
        mu_opt = expected_returns
        S_opt = covariance_matrix.loc[valid_tickers, valid_tickers]

        # ساخت EfficientFrontier با محدودیت وزن
        ef = EfficientFrontier(mu_opt, S_opt, weight_bounds=current_bounds)
        
        try:
            ef.max_sharpe(risk_free_rate=risk_free_rate)
            weights = ef.clean_weights()
            method_used = "max_sharpe"
        except Exception as e:
            logger.warning(f"⚠️ Max Sharpe optimization failed: {e}. Falling back to Min Volatility.")
            
            # تلاش مجدد با روش کمترین ریسک (مجددا باید کلاس ساخته شود تا وضعیت ریست شود)
            ef = EfficientFrontier(mu_opt, S_opt, weight_bounds=current_bounds)
            ef.min_volatility()
            weights = ef.clean_weights()
            method_used = "min_volatility"

        # بازسازی وزن‌ها و محاسبه عملکرد
        # نکته: در اینجا چون همه تیکرها معتبر بودند و محدودیت وزن داشتیم، 
        # وزن صفر تقریبا نخواهیم داشت مگر اینکه min_weight=0 باشد.
        
        ef_full = EfficientFrontier(expected_returns, covariance_matrix)
        ef_full.set_weights(weights)
        perf = ef_full.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)
        
        logger.info(f"✅ Optimization success using {method_used} with min_weight={min_weight}. Return: {perf[0]:.2f}")
        
        return weights, perf[0], perf[1], perf[2]