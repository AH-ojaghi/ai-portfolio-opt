import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
import logging
import numpy as np

# --- تنظیمات لاگینگ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Environment variables ---
TICKERS = os.environ.get("UPDATE_TICKERS", "AAPL,MSFT,GOOG,AMZN,META,TSLA,NVDA,JPM,JNJ,V")
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
MODEL_DIR = os.environ.get("MODEL_ARTIFACTS_DIR", "/app/model_artifacts")
OUTFILE = os.path.join(DATA_DIR, "market_data.csv")
FEATURES_FILE = os.path.join(MODEL_DIR, "feature_cols.json")

def get_tickers_from_models():
    """خواندن تیکرها از فایل feature_cols.json مدل"""
    try:
        if os.path.exists(FEATURES_FILE):
            with open(FEATURES_FILE, 'r') as f:
                feature_info = json.load(f)
            tickers = feature_info.get('tickers', [])
            logger.info(f"📋 Loaded {len(tickers)} tickers from model: {tickers}")
            return tickers
    except Exception as e:
        logger.warning(f"⚠️ Error reading feature file: {e}")
    
    # Fallback به تیکرهای پیش‌فرض
    tickers = [t.strip().upper() for t in TICKERS.split(",") if t.strip()]
    logger.info(f"📋 Using fallback tickers: {tickers}")
    return tickers

def clean_price_data(df):
    """پاکسازی کامل داده‌های قیمت"""
    try:
        # حذف ستون‌های اضافی
        if isinstance(df.columns, pd.MultiIndex):
            if 'Close' in df.columns:
                df = df['Close'].copy()
            elif 'Adj Close' in df.columns:
                df = df['Adj Close'].copy()
        
        # اطمینان از DataFrame بودن
        if isinstance(df, pd.Series):
            df = df.to_frame()
        
        # تبدیل به عدد
        df = df.apply(pd.to_numeric, errors='coerce')
        
        # حذف ردیف‌های کاملاً خالی
        df = df.dropna(how='all')
        
        # جایگزینی مقادیر نامتناهی
        df = df.replace([np.inf, -np.inf], np.nan)
        
        # پر کردن مقادیر缺失 با روش‌های مختلف
        df_cleaned = df.ffill().bfill()
        
        # اگر هنوز مقادیر NaN وجود دارد، با میانگین پر کن
        if df_cleaned.isna().any().any():
            df_cleaned = df_cleaned.fillna(df_cleaned.mean())
        
        # حذف ستون‌هایی که هنوز مقادیر نامعتبر دارند
        valid_columns = []
        for col in df_cleaned.columns:
            if df_cleaned[col].notna().all() and np.isfinite(df_cleaned[col]).all():
                valid_columns.append(col)
            else:
                logger.warning(f"🗑️ Removing column {col} due to persistent invalid values")
        
        df_final = df_cleaned[valid_columns]
        
        logger.info(f"✅ Data cleaning: {len(df.columns)} -> {len(df_final.columns)} valid columns")
        return df_final
        
    except Exception as e:
        logger.error(f"❌ Error in data cleaning: {e}")
        raise

def fetch_and_save():
    """Fetch daily market data for tickers and save to CSV"""
    tickers = get_tickers_from_models()
    
    if not tickers:
        logger.error("❌ No tickers available for data update")
        return False

    end = datetime.now()
    start = end - timedelta(days=1095)  # 3 سال داده برای اطمینان
    
    logger.info(f"📥 Fetching {len(tickers)} tickers from {start.date()} to {end.date()}")

    all_dfs = []
    successful_tickers = []
    failed_tickers = []

    for t in tickers:
        try:
            logger.info(f"🔍 Downloading data for {t}...")
            
            df = yf.download(
                t,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,  # استفاده از قیمت‌های تعدیل شده
                threads=True,
            )

            if df.empty:
                logger.warning(f"⚠️ No data for {t}")
                failed_tickers.append(t)
                continue

            # بررسی ساختار داده
            logger.debug(f"📊 {t} columns: {list(df.columns)}")
            
            # استخراج قیمت بسته‌شدن
            if 'Close' in df.columns:
                price_series = df['Close'].rename(t)
                all_dfs.append(price_series)
                successful_tickers.append(t)
                logger.info(f"✅ {t}: {len(price_series)} days of data (first: {price_series.index[0].date()}, last: {price_series.index[-1].date()})")
            else:
                logger.warning(f"⚠️ {t}: No Close column found in {list(df.columns)}")
                failed_tickers.append(t)

        except Exception as e:
            logger.error(f"❌ Error fetching {t}: {e}")
            failed_tickers.append(t)

    if not all_dfs:
        logger.error("❌ No data downloaded from any ticker")
        return False

    try:
        # ادغام تمام داده‌ها
        logger.info("🔄 Merging data from all tickers...")
        merged = pd.concat(all_dfs, axis=1)
        
        # پاکسازی داده‌ها
        logger.info("🧹 Cleaning merged data...")
        cleaned_data = clean_price_data(merged)
        
        if cleaned_data.empty:
            logger.error("❌ No valid data after cleaning")
            return False
        
        # اضافه کردن ستون تاریخ
        cleaned_data.reset_index(inplace=True)
        cleaned_data.rename(columns={"index": "Date"}, inplace=True)
        cleaned_data["Date"] = cleaned_data["Date"].dt.strftime("%Y-%m-%d")
        
        # بررسی نهایی داده‌ها
        logger.info("🔍 Final data validation...")
        for col in cleaned_data.columns:
            if col != 'Date':
                series = cleaned_data[col]
                if series.isna().any() or not np.isfinite(series).all():
                    logger.error(f"❌ Column {col} still has invalid values")
                    return False
        
        # ذخیره فایل
        cleaned_data.to_csv(OUTFILE, index=False)
        
        # گزارش نهایی
        logger.info(f"💾 Successfully saved market data to {OUTFILE}")
        logger.info(f"   📈 Shape: {cleaned_data.shape}")
        logger.info(f"   📅 Date range: {cleaned_data['Date'].min()} to {cleaned_data['Date'].max()}")
        logger.info(f"   ✅ Successful: {len(successful_tickers)} tickers")
        logger.info(f"   ❌ Failed: {len(failed_tickers)} tickers")
        
        if failed_tickers:
            logger.warning(f"   Failed tickers: {failed_tickers}")
        
        # نمایش نمونه‌ای از داده‌ها
        logger.info("📋 Sample of saved data:")
        logger.info(f"   Columns: {list(cleaned_data.columns)}")
        logger.info(f"   First 3 rows dates: {cleaned_data['Date'].head(3).tolist()}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error processing and saving data: {e}")
        return False

def check_existing_data():
    """بررسی داده‌های موجود و به‌روزرسانی در صورت نیاز"""
    if os.path.exists(OUTFILE):
        try:
            existing = pd.read_csv(OUTFILE)
            if 'Date' in existing.columns:
                last_date = pd.to_datetime(existing['Date']).max()
                hours_since_update = (datetime.now() - last_date).total_seconds() / 3600
                logger.info(f"📅 Last data update: {last_date.date()} ({hours_since_update:.1f} hours ago)")
                
                if hours_since_update < 6:  # هر 6 ساعت یکبار آپدیت
                    logger.info("✅ Data is up to date, skipping update")
                    return False
                else:
                    logger.info("🔄 Data is outdated, proceeding with update")
                    return True
        except Exception as e:
            logger.warning(f"⚠️ Error reading existing data: {e}")
    
    logger.info("🆕 No existing data found, creating new dataset")
    return True

def validate_market_data():
    """اعتبارسنجی داده‌های ذخیره شده"""
    if not os.path.exists(OUTFILE):
        logger.error("❌ Market data file does not exist")
        return False
    
    try:
        df = pd.read_csv(OUTFILE)
        
        # بررسی ساختار پایه
        if 'Date' not in df.columns:
            logger.error("❌ Missing 'Date' column")
            return False
        
        if len(df.columns) < 2:
            logger.error("❌ No price data columns found")
            return False
        
        # بررسی تاریخ‌ها
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        if df['Date'].isna().any():
            logger.error("❌ Invalid dates found")
            return False
        
        # بررسی داده‌های قیمت
        price_columns = [col for col in df.columns if col != 'Date']
        for col in price_columns:
            series = df[col]
            if series.isna().any():
                logger.error(f"❌ NaN values found in {col}")
                return False
            if not np.isfinite(series).all():
                logger.error(f"❌ Non-finite values found in {col}")
                return False
            if (series <= 0).any():
                logger.error(f"❌ Non-positive values found in {col}")
                return False
        
        logger.info(f"✅ Market data validation passed: {len(price_columns)} tickers, {len(df)} rows")
        return True
        
    except Exception as e:
        logger.error(f"❌ Market data validation failed: {e}")
        return False

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting data update check...")
        
        if check_existing_data():
            logger.info("🔄 Data update required, starting fetch...")
            success = fetch_and_save()
            if success:
                logger.info("✅ Data update completed successfully")
                # اعتبارسنجی داده‌های ذخیره شده
                if validate_market_data():
                    logger.info("🎉 Data is ready for use!")
                else:
                    logger.error("💥 Data validation failed!")
            else:
                logger.error("💥 Data update failed")
        else:
            logger.info("⏭️ No update needed at this time")
            
    except Exception as e:
        logger.error(f"💥 Data updater error: {e}")