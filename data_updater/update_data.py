import os
import logging
import json
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import time 

# --- پیکربندی لاگینگ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("MarketDataUpdater")

# --- تنظیمات عمومی ---
# تاخیر بین هر دانلود برای جلوگیری از Rate Limit را به 3 ثانیه افزایش دادیم.
DOWNLOAD_DELAY_SECONDS = 10

class MarketDataUpdater:
    """
    کلاس مدیریت به‌روزرسانی داده‌های بازار با قابلیت اصلاح فرمت و مدیریت خطا.
    """
    
    def __init__(self):
        self.base_dir = Path("/app")
        self.data_dir = Path(os.environ.get("DATA_DIR", self.base_dir / "data"))
        self.model_dir = Path(os.environ.get("MODEL_ARTIFACTS_DIR", self.base_dir / "model_artifacts"))
        
        self.models_subdir = self.model_dir / "models"
        self.features_file = self.model_dir / "feature_cols.json"
        self.output_file = self.data_dir / "market_data.csv"
        
        # نگاشت نمادهای قدیمی به جدید
        self.ticker_mapping = {
            "FB": "META",
            "TWTR": "TWTR" # مثال
        }
        
        # لیست پیش‌فرض
        self.fallback_tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM", "JNJ", "V"]
        self.history_years = 3
        self.update_threshold_hours = 6

    def _ensure_directories(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_target_tickers(self) -> List[str]:
        """شناسایی و اصلاح نام نمادها."""
        tickers = set()

        # 1. اسکن فایل‌های مدل
        if self.models_subdir.exists():
            model_files = list(self.models_subdir.glob("*_model.keras"))
            for p in model_files:
                ticker_name = p.name.replace("_model.keras", "")
                # اصلاح نام‌های قدیمی
                if ticker_name in self.ticker_mapping:
                    logger.info(f"🔄 Mapping old ticker {ticker_name} to {self.ticker_mapping[ticker_name]}")
                    ticker_name = self.ticker_mapping[ticker_name]
                tickers.add(ticker_name)

        # 2. خواندن از کانفیگ
        if not tickers and self.features_file.exists():
            try:
                with open(self.features_file, 'r') as f:
                    data = json.load(f)
                    raw_tickers = data.get('tickers', [])
                    # اعمال مپینگ
                    corrected_tickers = [self.ticker_mapping.get(t, t) for t in raw_tickers]
                    tickers.update(corrected_tickers)
            except Exception as e:
                logger.warning(f"⚠️ Failed to read feature file: {e}")

        # 3. Fallback
        if not tickers:
            tickers.update(self.fallback_tickers)

        return sorted(list(tickers))

    def is_update_needed(self) -> bool:
        if not self.output_file.exists():
            return True
        try:
            file_mod_time = datetime.fromtimestamp(self.output_file.stat().st_mtime)
            hours_since_mod = (datetime.now() - file_mod_time).total_seconds() / 3600
            
            # خواندن سریع برای اطمینان از سلامت فایل
            df = pd.read_csv(self.output_file, nrows=2)
            if df.shape[0] < 1: return True # فایل خالی

            if hours_since_mod < self.update_threshold_hours:
                logger.info(f"✅ Data is fresh (updated {hours_since_mod:.1f}h ago).")
                return False
            return True
        except Exception:
            return True

    def fetch_data(self, tickers: List[str]) -> Optional[pd.DataFrame]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.history_years * 365)
        
        logger.info(f"📥 Downloading data for {len(tickers)} tickers individually with a {DOWNLOAD_DELAY_SECONDS}s delay.")

        price_data = pd.DataFrame()
        failed_downloads = []

        for i, ticker in enumerate(tickers):
            # اگر در تلاش‌های قبلی دچار Rate Limit شده‌اید، بهتر است کمی بیشتر صبر کنید.
            if i > 0 and failed_downloads:
                 time.sleep(DOWNLOAD_DELAY_SECONDS * 1.5) 
                 
            try:
                logger.info(f"[{i+1}/{len(tickers)}] Fetching {ticker}...")
                
                # استفاده از yf.Ticker برای کنترل دقیق‌تر Rate Limit
                ticker_data = yf.Ticker(ticker)
                
                # دریافت تاریخچه با تنظیم auto_adjust=True برای دریافت قیمت‌های تعدیل‌شده
                # حذف آرگومان 'progress' برای جلوگیری از TypeError در نسخه‌های قدیمی‌تر yfinance
                df_history = ticker_data.history(
                    start=start_date, 
                    end=end_date,
                    auto_adjust=True, # این ستون 'Adj Close' را مستقیماً به 'Close' تبدیل می‌کند
                )
                
                if df_history.empty:
                    logger.warning(f"⚠️ No history found for {ticker}.")
                    failed_downloads.append(ticker)
                    continue
                
                # استخراج فقط ستون Close (که اکنون تعدیل شده است) و تغییر نام به نماد سهم
                if 'Close' in df_history.columns:
                    price_data[ticker] = df_history['Close']
                    logger.info(f"   Successfully fetched {df_history.shape[0]} rows.")
                else:
                     logger.warning(f"⚠️ 'Close' column not found in history for {ticker}.")
                     failed_downloads.append(ticker)

                # مکث بین درخواست‌ها برای احترام به Rate Limit
                if i < len(tickers) - 1:
                    time.sleep(DOWNLOAD_DELAY_SECONDS)

            except Exception as e:
                logger.error(f"❌ Error fetching {ticker}: {type(e).__name__} - {e}")
                failed_downloads.append(ticker)
                time.sleep(DOWNLOAD_DELAY_SECONDS * 2) # تاخیر بیشتر بعد از خطا

        if not price_data.empty:
            logger.info(f"✅ Download completed. Combined prices shape: {price_data.shape}")
        
        if failed_downloads:
            logger.warning(f"⚠️ Failed to download: {', '.join(failed_downloads)}")
            
        return price_data if not price_data.empty else None

    def clean_and_save(self, df: pd.DataFrame):
        if df is None or df.empty:
            logger.error("❌ Cannot save data: DataFrame is empty after fetching.")
            return

        logger.info("🧹 Cleaning and Formatting...")
        
        # 1. حذف ردیف‌های کاملاً خالی
        df.dropna(how='all', axis=0, inplace=True)

        # 2. پر کردن مقادیر گم شده (FFILL -> BFILL -> 0)
        df.ffill(inplace=True)
        df.bfill(inplace=True)
        # فقط ستون‌های عددی را با 0 پر می‌کنیم (اگر هنوز NaN باقی مانده باشد)
        df.fillna(0, inplace=True) 

        # 3. ریست ایندکس برای تبدیل Date به ستون (چون از yf.Ticker استفاده کردیم، Date ایندکس است)
        df_final = df.reset_index()
        
        # 4. اطمینان از نام درست ستون تاریخ
        if 'Date' not in df_final.columns and df_final.index.name == 'Date':
             df_final = df_final.reset_index()
        
        # 5. فرمت‌دهی تاریخ (بسیار مهم برای حذف ساعت و دقیقه)
        if 'Date' in df_final.columns:
            # مطمئن شدن که Date به عنوان datetime شناخته می‌شود
            df_final['Date'] = pd.to_datetime(df_final['Date']).dt.strftime('%Y-%m-%d')

        # 6. حذف ستون‌های اضافی و اطمینان از تمیز بودن هدر
        df_final.columns.name = None 
        
        try:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            df_final.to_csv(self.output_file, index=False)
            
            # اعتبارسنجی سریع فایل ذخیره شده
            check = pd.read_csv(self.output_file)
            logger.info(f"💾 Saved {self.output_file}. Rows: {check.shape[0]}, Columns: {list(check.columns)}")
            
            # چک کردن هدر تکراری (این چک اکنون کمتر مورد نیاز است اما حفظ می‌شود)
            if check.iloc[0,0] == 'Date' or check.iloc[0,1] == check.columns[1]:
                logger.warning("⚠️ Warning: Possible double header detected! Attempting deep clean...")
                check = pd.read_csv(self.output_file, skiprows=1)
                check.to_csv(self.output_file, index=False)
                logger.info("✅ Double header fixed.")

        except Exception as e:
            logger.error(f"❌ Save error: {e}")

    def run(self):
        self._ensure_directories()
        if self.is_update_needed():
            tickers = self.get_target_tickers()
            df = self.fetch_data(tickers)
            self.clean_and_save(df)
        else:
            logger.info("⏭️ Update skipped.")

if __name__ == "__main__":
    MarketDataUpdater().run()