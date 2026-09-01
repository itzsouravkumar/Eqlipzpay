"""
EqlipZ Pay — Dataset Download & Preprocessing Pipeline
=======================================================
Downloads IEEE-CIS Fraud Detection and ULB Credit Card Fraud datasets
from Kaggle, preprocesses them into a unified format, and saves
train/calibration/test splits for the conformal risk engine.

Datasets:
  - IEEE-CIS: Real e-commerce fraud data (primary, ~590k transactions)
  - ULB: Real European card fraud data (validation, ~284k transactions)

Usage:
  python data/download_datasets.py
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eqlipz.data")

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"


def ensure_dirs():
    """Create data directories if they don't exist."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def download_ieee_cis() -> Path:
    """Download IEEE-CIS Fraud Detection dataset from Kaggle or use local."""
    local_path = BASE_DIR / "ieee-fraud-detection"
    if local_path.exists() and (local_path / "train_transaction.csv").exists():
        logger.info(f"Using local IEEE-CIS dataset at: {local_path}")
        return local_path
        
    try:
        import kagglehub
        logger.info("Downloading IEEE-CIS Fraud Detection dataset...")
        path = kagglehub.competition_download("ieee-fraud-detection")
        logger.info(f"IEEE-CIS downloaded to: {path}")
        return Path(path)
    except Exception as e:
        logger.error(f"Failed to download IEEE-CIS: {e}")
        logger.info("Make sure you have:")
        logger.info("  1. A Kaggle account with API token at ~/.kaggle/kaggle.json")
        logger.info("  2. Accepted competition rules at https://www.kaggle.com/competitions/ieee-fraud-detection")
        raise


def download_ulb() -> Path:
    """Download ULB Credit Card Fraud dataset from Kaggle."""
    try:
        import kagglehub
        logger.info("Downloading ULB Credit Card Fraud dataset...")
        path = kagglehub.dataset_download("mlg-ulb/creditcardfraud")
        logger.info(f"ULB downloaded to: {path}")
        return Path(path)
    except Exception as e:
        logger.error(f"Failed to download ULB: {e}")
        logger.info("Make sure you have a Kaggle API token at ~/.kaggle/kaggle.json")
        raise


def download_sparkov() -> Path:
    """Download Sparkov Synthetic dataset from Kaggle."""
    try:
        import kagglehub
        logger.info("Downloading Sparkov dataset...")
        path = kagglehub.dataset_download("kartik2112/fraud-detection")
        logger.info(f"Sparkov downloaded to: {path}")
        return Path(path)
    except Exception as e:
        logger.error(f"Failed to download Sparkov: {e}")
        raise


def download_paysim() -> Path:
    """Download PaySim dataset from Kaggle."""
    try:
        import kagglehub
        logger.info("Downloading PaySim dataset...")
        path = kagglehub.dataset_download("ealaxi/paysim1")
        logger.info(f"PaySim downloaded to: {path}")
        return Path(path)
    except Exception as e:
        logger.error(f"Failed to download PaySim: {e}")
        raise


def preprocess_ieee_cis(dataset_path: Path) -> pd.DataFrame:
    """
    Preprocess the IEEE-CIS dataset.
    
    Selects the most impactful features from the 871 available columns,
    handles missing values, and encodes categoricals.
    """
    logger.info("Preprocessing IEEE-CIS dataset...")
    
    # Load transaction data
    train_tx_path = dataset_path / "train_transaction.csv"
    train_id_path = dataset_path / "train_identity.csv"
    
    if not train_tx_path.exists():
        # Sometimes kagglehub nests files differently
        for f in dataset_path.rglob("train_transaction.csv"):
            train_tx_path = f
            break
    if not train_id_path.exists():
        for f in dataset_path.rglob("train_identity.csv"):
            train_id_path = f
            break
    
    logger.info(f"Loading transactions from {train_tx_path}")
    df_tx = pd.read_csv(train_tx_path)
    
    logger.info(f"Loading identity data from {train_id_path}")
    df_id = pd.read_csv(train_id_path)
    
    # Merge transaction + identity on TransactionID
    df = df_tx.merge(df_id, on="TransactionID", how="left")
    logger.info(f"Merged shape: {df.shape}")
    
    # Select key features that are most predictive for fraud detection
    # Based on Kaggle competition findings and feature importance
    numeric_features = [
        "TransactionAmt",
        "card1", "card2", "card3", "card5",
        "addr1", "addr2",
        "dist1", "dist2",
        "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
        "C10", "C11", "C12", "C13", "C14",
        "D1", "D2", "D3", "D4", "D5", "D10", "D11", "D15",
        "V1", "V2", "V3", "V4", "V5",
        "V12", "V13", "V14", "V15",
        "V44", "V45", "V46", "V47", "V48", "V49", "V50", "V51",
        "V54", "V56", "V75", "V76", "V77", "V78",
        "V82", "V83", "V87",
        "V258", "V261", "V263", "V264", "V265",
        "V267", "V268", "V270", "V271",
        "V283", "V285", "V294", "V306", "V307", "V308", "V310",
        "V312", "V313", "V314", "V315", "V317", "V318", "V320",
    ]
    
    categorical_features = [
        "ProductCD",
        "card4", "card6",
        "P_emaildomain", "R_emaildomain",
        "DeviceType",
    ]
    
    target = "isFraud"
    
    # Keep only selected features + target
    all_features = [f for f in numeric_features + categorical_features if f in df.columns]
    df_selected = df[all_features + [target]].copy()
    
    # Handle missing values for numerics — fill with median
    for col in numeric_features:
        if col in df_selected.columns:
            df_selected[col] = df_selected[col].fillna(df_selected[col].median())
    
    # Encode categoricals with label encoding
    for col in categorical_features:
        if col in df_selected.columns:
            df_selected[col] = df_selected[col].fillna("MISSING")
            df_selected[col] = df_selected[col].astype("category").cat.codes
    
    # Engineered features
    df_selected["log_amount"] = np.log1p(df_selected["TransactionAmt"])
    df_selected["amount_to_mean_ratio"] = (
        df_selected["TransactionAmt"] / df_selected["TransactionAmt"].mean()
    )
    
    logger.info(f"IEEE-CIS preprocessed: {df_selected.shape[0]} rows, {df_selected.shape[1]} cols")
    logger.info(f"Fraud rate: {df_selected[target].mean():.4f} ({df_selected[target].sum()} frauds)")
    
    return df_selected


def preprocess_ulb(dataset_path: Path) -> pd.DataFrame:
    """
    Preprocess the ULB Credit Card Fraud dataset.
    
    Features V1-V28 are PCA-transformed (already numeric), plus Time and Amount.
    """
    logger.info("Preprocessing ULB dataset...")
    
    csv_path = dataset_path / "creditcard.csv"
    if not csv_path.exists():
        for f in dataset_path.rglob("creditcard.csv"):
            csv_path = f
            break
    
    df = pd.read_csv(csv_path)
    logger.info(f"ULB shape: {df.shape}")
    
    # Rename target to match IEEE-CIS convention
    df = df.rename(columns={"Class": "isFraud"})
    
    # Add engineered features
    df["log_amount"] = np.log1p(df["Amount"])
    df["amount_to_mean_ratio"] = df["Amount"] / df["Amount"].mean()
    
    # Normalise Time to hour-of-day (cycles every 24h)
    df["hour_of_day"] = (df["Time"] % 86400) / 3600
    
    logger.info(f"ULB preprocessed: {df.shape[0]} rows, {df.shape[1]} cols")
    logger.info(f"Fraud rate: {df['isFraud'].mean():.4f} ({df['isFraud'].sum()} frauds)")
    
    return df


def preprocess_sparkov(dataset_path: Path) -> pd.DataFrame:
    """Preprocess the Sparkov dataset."""
    logger.info("Preprocessing Sparkov dataset...")
    
    csv_path = dataset_path / "fraudTest.csv" # or fraudTrain.csv
    if not csv_path.exists():
        for f in dataset_path.rglob("*.csv"):
            if "fraudTrain" in f.name or "fraudTest" in f.name:
                csv_path = f
                break
                
    df = pd.read_csv(csv_path)
    logger.info(f"Sparkov shape: {df.shape}")
    
    # Rename target
    df = df.rename(columns={"is_fraud": "isFraud"})
    
    # Simple feature selection for harmonization
    features_to_keep = ["amt", "city_pop", "isFraud"]
    
    df_selected = df[[c for c in features_to_keep if c in df.columns]].copy()
    
    if "amt" in df_selected.columns:
        df_selected["log_amount"] = np.log1p(df_selected["amt"])
        df_selected["TransactionAmt"] = df_selected["amt"]
        
    # Fill NA
    df_selected.fillna(0, inplace=True)
    return df_selected


def preprocess_paysim(dataset_path: Path) -> pd.DataFrame:
    """Preprocess the PaySim dataset."""
    logger.info("Preprocessing PaySim dataset...")
    
    csv_path = dataset_path / "PS_20174392719_1491204439457_log.csv"
    if not csv_path.exists():
        for f in dataset_path.rglob("*.csv"):
            csv_path = f
            break
            
    df = pd.read_csv(csv_path)
    logger.info(f"PaySim shape: {df.shape}")
    
    # Rename target
    df = df.rename(columns={"isFraud": "isFraud"})
    
    # Simple feature selection
    features_to_keep = ["amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest", "isFraud"]
    df_selected = df[[c for c in features_to_keep if c in df.columns]].copy()
    
    if "amount" in df_selected.columns:
        df_selected["log_amount"] = np.log1p(df_selected["amount"])
        df_selected["TransactionAmt"] = df_selected["amount"]
        
    df_selected.fillna(0, inplace=True)
    return df_selected


def split_and_save(df: pd.DataFrame, name: str, 
                   train_frac: float = 0.6, 
                   cal_frac: float = 0.2):
    """
    Split data into train/calibration/test and save to disk.
    
    The calibration set is critical — it's what the conformal prediction
    engine uses to produce its accuracy guarantees. It must never overlap
    with training data.
    """
    logger.info(f"Splitting {name}: {train_frac:.0%} train / {cal_frac:.0%} cal / {1-train_frac-cal_frac:.0%} test")
    
    # Stratified split to preserve fraud ratio
    from sklearn.model_selection import train_test_split
    
    target = "isFraud"
    
    # First split: train+cal vs test
    df_trainval, df_test = train_test_split(
        df, test_size=1 - train_frac - cal_frac,
        stratify=df[target], random_state=42
    )
    
    # Second split: train vs cal
    cal_relative = cal_frac / (train_frac + cal_frac)
    df_train, df_cal = train_test_split(
        df_trainval, test_size=cal_relative,
        stratify=df_trainval[target], random_state=42
    )
    
    # Save
    out_dir = PROCESSED_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    
    df_train.to_parquet(out_dir / "train.parquet", index=False)
    df_cal.to_parquet(out_dir / "calibration.parquet", index=False)
    df_test.to_parquet(out_dir / "test.parquet", index=False)
    
    logger.info(f"  Train:       {len(df_train):>8,} rows  (fraud: {df_train[target].sum():>6,})")
    logger.info(f"  Calibration: {len(df_cal):>8,} rows  (fraud: {df_cal[target].sum():>6,})")
    logger.info(f"  Test:        {len(df_test):>8,} rows  (fraud: {df_test[target].sum():>6,})")
    logger.info(f"  Saved to: {out_dir}")


def main():
    ensure_dirs()
    
    print("=" * 60)
    print("  EqlipZ Pay — Dataset Download & Preprocessing")
    print("=" * 60)
    
    # Download and preprocess IEEE-CIS
    try:
        ieee_path = download_ieee_cis()
        df_ieee = preprocess_ieee_cis(ieee_path)
        split_and_save(df_ieee, "ieee_cis")
    except Exception as e:
        logger.error(f"IEEE-CIS pipeline failed: {e}")
        logger.info("Continuing with ULB only...")
    
    # Download and preprocess ULB
    try:
        ulb_path = download_ulb()
        df_ulb = preprocess_ulb(ulb_path)
        split_and_save(df_ulb, "ulb")
    except Exception as e:
        logger.error(f"ULB pipeline failed: {e}")
        
    # Download and preprocess Sparkov
    try:
        sparkov_path = download_sparkov()
        df_sparkov = preprocess_sparkov(sparkov_path)
        split_and_save(df_sparkov, "sparkov")
    except Exception as e:
        logger.error(f"Sparkov pipeline failed: {e}")
        
    # Download and preprocess PaySim
    try:
        paysim_path = download_paysim()
        df_paysim = preprocess_paysim(paysim_path)
        split_and_save(df_paysim, "paysim")
    except Exception as e:
        logger.error(f"PaySim pipeline failed: {e}")
    
    print("\n" + "=" * 60)
    print("  Dataset pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
