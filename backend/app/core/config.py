# app/core/config.py
import os
from pathlib import Path
import logging

class Settings:
    def __init__(self):
        # Base Paths
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent
        self.DATA_DIR = Path(os.environ.get("DATA_DIR", self.BASE_DIR / "app" / "data"))
        self.MODEL_ARTIFACTS_DIR = Path(os.environ.get("MODEL_ARTIFACTS_DIR", self.BASE_DIR / "model_artifacts"))
        
        # Specific File Paths
        self.MARKET_DATA_FILE = self.DATA_DIR / "market_data.csv"
        self.MODELS_DIR = self.MODEL_ARTIFACTS_DIR / "models"
        self.SCALERS_DIR = self.MODEL_ARTIFACTS_DIR / "scalers"
        self.FEATURES_FILE = self.MODEL_ARTIFACTS_DIR / "feature_cols.json"
        
        # App Parameters
        self.COL_MISSING_THRESHOLD = float(os.environ.get("COL_MISSING_THRESHOLD", "0.5"))
        self.WINDOW_SIZE_DEFAULT = 30
        
        # Logging
        self.LOG_LEVEL = logging.INFO
        self.LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

settings = Settings()