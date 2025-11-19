# app/data_handler.py
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Tuple
from app.core.config import settings

logger = logging.getLogger("ai-backend")

class DataHandler:
    """
    مسئول بارگذاری داده‌های بازار، پاکسازی و ایجاد ویژگی‌های تکنیکال.
    """

    def read_and_clean_market_data(self) -> pd.DataFrame:
        """
        خواندن داده‌های CSV و انجام پاکسازی‌های اولیه.
        """
        if not settings.MARKET_DATA_FILE.exists():
            raise FileNotFoundError(f"Market data file not found at {settings.MARKET_DATA_FILE}")

        try:
            df = pd.read_csv(settings.MARKET_DATA_FILE)
            
            if "Date" not in df.columns:
                raise ValueError("CSV does not contain 'Date' column")

            df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
            df = df[df["Date"].notna()]
            df.set_index("Date", inplace=True)
            
            # تبدیل به عددی
            price_columns = [col for col in df.columns if col != 'Date']
            df[price_columns] = df[price_columns].apply(pd.to_numeric, errors='coerce')

            # پاکسازی مقادیر نامعتبر
            df.replace([np.inf, -np.inf], np.nan, inplace=True)
            df[df <= 0] = np.nan

            # حذف داده‌های کاملاً خالی و پر کردن شکاف‌ها
            df = df.dropna(axis=1, how='all').dropna(axis=0, how='all')
            df = df.ffill().bfill()

            if df.empty:
                raise ValueError("No valid data remains after cleaning")
            
            # بررسی نهایی NaN
            if df.isna().any().any():
                df = df.dropna(axis=1, how='any')
                
            logger.info(f"✅ Loaded market data: {df.shape}")
            return df

        except Exception as e:
            logger.error(f"Error processing market data: {e}")
            raise

    @staticmethod
    def winsorize_series(series: pd.Series, limits: Tuple[float, float] = (0.05, 0.05)) -> pd.Series:
        """حذف داده‌های پرت (Outliers) با روش Winsorization."""
        lower = series.quantile(limits[0])
        upper = series.quantile(1 - limits[1])
        return series.clip(lower, upper)

    def create_advanced_features(self, prices_df: pd.DataFrame, rets_df: pd.DataFrame, windows: List[int] = [5, 10, 20]) -> pd.DataFrame:
        """
        ایجاد ویژگی‌های پیشرفته تکنیکال (MA, RSI, Momentum, Rank).
        """
        features = {}
        rets_local = rets_df.copy()
        prices_local = prices_df.copy()

        # 1. ویژگی‌های بازده (Return Features)
        for w in windows:
            features[f'ret_ma_{w}'] = rets_local.rolling(w, min_periods=1).mean()
            features[f'ret_std_{w}'] = rets_local.rolling(w, min_periods=1).std()
            features[f'ret_skew_{w}'] = rets_local.rolling(w, min_periods=w).skew().fillna(0)
            features[f'ret_kurt_{w}'] = rets_local.rolling(w, min_periods=w).kurt().fillna(0)

        # 2. ویژگی‌های قیمت (Price Features)
        for w in windows:
            if w > 5:
                rolling_mean = prices_local.rolling(w, min_periods=1).mean()
                features[f'price_ma_ratio_{w}'] = prices_local / rolling_mean.replace(0, 1e-10)

        # 3. مومنتوم (Momentum)
        for w in [10, 20]:
            shifted = prices_local.shift(w).replace(0, 1e-10)
            features[f'momentum_{w}'] = prices_local / shifted - 1

        # 4. شاخص قدرت نسبی (RSI)
        delta = rets_local.diff()
        for w in [14]:
            gain = (delta.where(delta > 0, 0)).rolling(window=w).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=w).mean()
            rs = gain / loss.replace(0, 1e-10)
            features[f'rsi_{w}'] = 100 - (100 / (1 + rs))

        # 5. رتبه‌بندی مومنتوم (Momentum Rank) - بخش حیاتی که گم شده بود
        # محاسبه میانگین بازده ۲۰ روزه و رتبه‌بندی سهم‌ها نسبت به هم در هر روز
        mom20 = rets_local.rolling(20, min_periods=1).mean()
        features["rank_mom20"] = mom20.rank(axis=1, pct=True)

        # ترکیب ویژگی‌ها و نام‌گذاری صحیح ستون‌ها
        feature_dfs = []
        for name, feature_data in features.items():
            if isinstance(feature_data, pd.DataFrame):
                feature_data.columns = [f"{name}__{col}" for col in feature_data.columns]
                feature_dfs.append(feature_data)
            elif isinstance(feature_data, pd.Series):
                 feature_data = feature_data.to_frame()
                 feature_data.columns = [f"{name}__{col}" for col in feature_data.columns]
                 feature_dfs.append(feature_data)

        all_features = pd.concat(feature_dfs, axis=1)
        
        # پر کردن مقادیر خالی ناشی از Rolling
        all_features = all_features.ffill().bfill().fillna(0)

        # حذف ستون‌های با واریانس صفر (اطلاعات بی‌استفاده)
        nonzero_variance = all_features.columns[all_features.std() > 1e-6]
        return all_features[nonzero_variance]