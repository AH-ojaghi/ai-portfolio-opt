import os
import pandas as pd
import yfinance as yf
from datetime import datetime

# --- Environment variables ---
TICKERS = os.environ.get("UPDATE_TICKERS", "AAPL,MSFT,GOOG,AMZN,FB")
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
OUTFILE = os.path.join(DATA_DIR, "market_data.csv")

# --- Setup ---
tickers = [t.strip().upper() for t in TICKERS.split(",") if t.strip()]
print(f"[{datetime.now().isoformat()}] Starting data updater for: {tickers}")
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_and_save():
    """Fetch daily market data for tickers and save to CSV"""
    end = datetime.now()
    start = end.replace(year=end.year - 2)
    print(f"Fetching {len(tickers)} tickers from {start.date()} to {end.date()}")

    all_dfs = []

    for t in tickers:
        try:
            df = yf.download(
                t,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=False,  # will be ignored in latest yfinance, but kept for backward compatibility
            )

            if df.empty:
                print(f"No data for {t}")
                continue

            # ✅ Use 'Adj Close' if available, otherwise 'Close'
            if "Adj Close" in df.columns:
                df = df[["Adj Close"]].rename(columns={"Adj Close": t})
            elif "Close" in df.columns:
                df = df[["Close"]].rename(columns={"Close": t})
            else:
                print(f"⚠️ {t}: No valid price column found ({list(df.columns)})")
                continue

            all_dfs.append(df)

        except Exception as e:
            print(f"Error fetching {t}: {e}")

    if not all_dfs:
        print("No data downloaded.")
        return

    # ✅ Merge and clean
    merged = pd.concat(all_dfs, axis=1).sort_index()
    merged = merged.ffill().dropna(how="all")

    # ✅ Add 'Date' column
    merged.reset_index(inplace=True)
    merged.rename(columns={"index": "Date"}, inplace=True)
    merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d")

    # ✅ Save
    merged.to_csv(OUTFILE, index=False)
    print(f"[{datetime.now().isoformat()}] Saved market data to {OUTFILE} (shape {merged.shape})")


if __name__ == "__main__":
    try:
        fetch_and_save()
    except Exception as e:
        print("❌ Initial fetch error:", e)
