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
        """محاسبه ماتریس کوواریانس نمایی."""
        try:
            # استفاده از frequency=252 برای داده‌های روزانه
            S = risk_models.exp_cov(returns_df[tickers], frequency=252)
            
            if not np.all(np.isfinite(S.values)):
                raise ValueError("Covariance matrix contains non-finite values.")
            
            return S
        except Exception as e:
            logger.error(f"Covariance calculation error: {e}")
            raise

    def optimize(self, 
                 expected_returns: pd.Series, 
                 covariance_matrix: pd.DataFrame, 
                 risk_free_rate: float) -> Tuple[Dict[str, float], float, float, float]:
        """
        بهینه‌سازی برای حداکثر Sharpe Ratio.
        خروجی: (وزن‌ها، بازده پورتفو، نوسان پورتفو، شارپ)
        """
        # حذف بازده‌های منفی/صفر برای بهبود همگرایی ریاضی (اختیاری اما توصیه شده)
        positive_mu = expected_returns[expected_returns > 0]
        if positive_mu.empty:
            raise ValueError("No positive expected returns available for optimization.")
            
        valid_tickers = positive_mu.index.tolist()
        mu_opt = expected_returns.loc[valid_tickers]
        S_opt = covariance_matrix.loc[valid_tickers, valid_tickers]

        # حل مسئله بهینه‌سازی
        ef = EfficientFrontier(mu_opt, S_opt)
        ef.max_sharpe(risk_free_rate=risk_free_rate)
        cleaned_weights = ef.clean_weights()

        # بازسازی وزن‌ها برای تمام تیکرهای اولیه (تیکرهای حذف شده وزن 0 می‌گیرند)
        final_weights = {t: 0.0 for t in expected_returns.index}
        final_weights.update(cleaned_weights)

        # محاسبه عملکرد پورتفوی نهایی روی کل مجموعه
        ef_full = EfficientFrontier(expected_returns, covariance_matrix)
        ef_full.set_weights(final_weights)
        perf = ef_full.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)
        
        return final_weights, perf[0], perf[1], perf[2]