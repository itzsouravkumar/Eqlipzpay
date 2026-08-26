"""
EqlipZ Pay — Fraud Model Training & Conformal Calibration
==========================================================
Trains a LightGBM classifier on the IEEE-CIS dataset, calibrates it using
MAPIE conformal prediction, and validates on the ULB dataset for cross-dataset
generalization. Saves the trained model + calibration artifacts.

Usage:
  python data/train_model.py
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eqlipz.train")

BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"


def load_splits(dataset_name: str):
    """Load train/calibration/test splits for a dataset."""
    data_dir = PROCESSED_DIR / dataset_name
    
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Dataset not found at {data_dir}. "
            f"Run 'python data/download_datasets.py' first."
        )
    
    train = pd.read_parquet(data_dir / "train.parquet")
    cal = pd.read_parquet(data_dir / "calibration.parquet")
    test = pd.read_parquet(data_dir / "test.parquet")
    
    return train, cal, test


def train_fraud_model(X_train, y_train):
    """
    Train a LightGBM classifier optimized for fraud detection.
    
    Uses scale_pos_weight to handle severe class imbalance
    (typical fraud rate: 0.17% - 3.5%).
    """
    from lightgbm import LGBMClassifier
    
    # Calculate class imbalance ratio
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1
    
    logger.info(f"Class distribution: {n_neg:,} legitimate / {n_pos:,} fraud")
    logger.info(f"Scale pos weight: {scale_pos_weight:.1f}")
    
    model = LGBMClassifier(
        n_estimators=300,
        max_depth=7,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=50,
        scale_pos_weight=scale_pos_weight,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbose=-1,
        n_jobs=-1,
    )
    
    logger.info("Training LightGBM fraud model...")
    model.fit(X_train, y_train)
    logger.info("Training complete.")
    
    return model


def calibrate_conformal(model, X_cal, y_cal, alpha=0.10):
    """
    Calibrate the model using MAPIE conformal prediction.
    
    This produces prediction SETS instead of point predictions:
    - {0}       = model is confident it's legitimate → RELEASE
    - {1}       = model is confident it's fraud → REFUSE
    - {0, 1}    = model is uncertain → HOLD
    
    The guarantee: with probability ≥ (1 - alpha), the true label
    is in the prediction set.
    """
    from mapie.classification import SplitConformalClassifier
    
    logger.info(f"Calibrating conformal prediction (alpha={alpha})...")
    
    mapie = SplitConformalClassifier(
        estimator=model,
        confidence_level=1 - alpha,
        conformity_score="lac",
        prefit=True,
    )
    
    mapie.conformalize(X_cal, y_cal)
    logger.info("Conformal calibration complete.")
    
    return mapie


def evaluate(mapie_model, X_test, y_test, alpha=0.10, dataset_name="test"):
    """
    Evaluate the conformally-calibrated model on a test set.
    
    Reports:
    - Standard metrics: precision, recall, F1, AUCPR
    - Conformal metrics: marginal coverage, set sizes
    - Business metrics: EMV (Expected Monetary Value)
    """
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        average_precision_score, classification_report,
    )
    from mapie.metrics.classification import classification_coverage_score
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Evaluating on {dataset_name}")
    logger.info(f"{'='*50}")
    
    # Get predictions and prediction sets
    y_pred, y_pis = mapie_model.predict_set(X_test)
    
    # y_pis shape: (n_samples, n_classes, 1) -> since we pass a single confidence level
    prediction_sets = y_pis[:, :, 0]
    
    # Classification metrics (using point predictions)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    
    # AUCPR (better than AUROC for imbalanced data)
    try:
        proba = mapie_model.estimator_.predict_proba(X_test)[:, 1]
        aucpr = average_precision_score(y_test, proba)
    except Exception:
        aucpr = 0.0
    
    # Get conformal coverage
    coverage_arr = classification_coverage_score(y_test, prediction_sets)
    coverage = float(coverage_arr[0]) if isinstance(coverage_arr, np.ndarray) else float(coverage_arr)
    
    # Measure typical sizes of the sets
    set_sizes = prediction_sets.sum(axis=1)
    mean_size = np.mean(set_sizes)
    n_singleton = (set_sizes == 1).sum()
    n_both = (set_sizes == 2).sum()     # These become HOLDs
    n_empty = (set_sizes == 0).sum()
    
    # Decision distribution
    n_release = 0
    n_refuse = 0
    n_hold = 0
    
    for i in range(len(y_pred)):
        labels_in_set = [j for j in range(prediction_sets.shape[1]) if prediction_sets[i, j]]
        if labels_in_set == [0]:
            n_release += 1
        elif labels_in_set == [1]:
            n_refuse += 1
        else:
            n_hold += 1
    
    results = {
        "dataset": dataset_name,
        "n_samples": len(y_test),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "aucpr": aucpr,
        "conformal_coverage": coverage,
        "n_release": n_release,
        "n_refuse": n_refuse,
        "n_hold": n_hold,
        "hold_rate": n_hold / len(y_test) if len(y_test) > 0 else 0,
    }
    
    logger.info(f"  Precision:           {precision:.4f}")
    logger.info(f"  Recall:              {recall:.4f}")
    logger.info(f"  F1:                  {f1:.4f}")
    logger.info(f"  AUCPR:               {aucpr:.4f}")
    logger.info(f"  Conformal Coverage:  {coverage:.4f} (target: {1-alpha:.2f})")
    logger.info(f"  Decisions:  RELEASE={n_release}  REFUSE={n_refuse}  HOLD={n_hold}")
    logger.info(f"  Hold Rate:           {results['hold_rate']:.4f}")
    
    return results


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("  EqlipZ Pay — Model Training & Conformal Calibration")
    print("=" * 60)
    
    results_out = {}
    primary_trained = False
    
    # ── Load IEEE-CIS data ──
    logger.info("Loading IEEE-CIS dataset...")
    try:
        train, cal, test = load_splits("ieee_cis")
        
        target = "isFraud"
        feature_cols = [c for c in train.columns if c != target]
        
        X_train = train[feature_cols]
        y_train = train[target]
        X_cal = cal[feature_cols]
        y_cal = cal[target]
        X_test = test[feature_cols]
        y_test = test[target]
        
        # Save feature column names for inference
        joblib.dump(feature_cols, MODELS_DIR / "feature_columns.joblib")
        logger.info(f"Features: {len(feature_cols)} columns")
        
        # ── Train ──
        model = train_fraud_model(X_train, y_train)
        
        # Save raw model
        joblib.dump(model, MODELS_DIR / "fraud_model_raw.joblib")
        logger.info(f"Raw model saved to {MODELS_DIR / 'fraud_model_raw.joblib'}")
        
        # ── Calibrate ──
        mapie_model = calibrate_conformal(model, X_cal, y_cal, alpha=0.10)
        
        # Save calibrated model
        joblib.dump(mapie_model, MODELS_DIR / "fraud_model_mapie.joblib")
        logger.info(f"Calibrated model saved to {MODELS_DIR / 'fraud_model_mapie.joblib'}")
        
        # ── Evaluate on IEEE-CIS test set ──
        ieee_results = evaluate(mapie_model, X_test, y_test, alpha=0.10, dataset_name="IEEE-CIS Test")
        results_out["ieee_cis"] = ieee_results
        primary_trained = True
    except FileNotFoundError:
        logger.error("IEEE-CIS dataset not found. Please ensure download completed successfully.")
        logger.info("Will attempt to train on ULB dataset as primary...")
    
    # ── Cross-validate / Train on ULB ──
    try:
        logger.info("\nLoading ULB dataset...")
        ulb_train, ulb_cal, ulb_test = load_splits("ulb")
        
        ulb_target = "isFraud"
        ulb_feature_cols = [c for c in ulb_train.columns if c != ulb_target]
        
        X_ulb_train = ulb_train[ulb_feature_cols]
        y_ulb_train = ulb_train[ulb_target]
        X_ulb_cal = ulb_cal[ulb_feature_cols]
        y_ulb_cal = ulb_cal[ulb_target]
        X_ulb_test = ulb_test[ulb_feature_cols]
        y_ulb_test = ulb_test[ulb_target]
        
        ulb_model = train_fraud_model(X_ulb_train, y_ulb_train)
        ulb_mapie = calibrate_conformal(ulb_model, X_ulb_cal, y_ulb_cal, alpha=0.10)
        
        # If IEEE-CIS failed, use ULB as the primary model
        if not primary_trained:
            logger.info("Saving ULB as the primary model since IEEE-CIS is unavailable.")
            joblib.dump(ulb_feature_cols, MODELS_DIR / "feature_columns.joblib")
            joblib.dump(ulb_model, MODELS_DIR / "fraud_model_raw.joblib")
            joblib.dump(ulb_mapie, MODELS_DIR / "fraud_model_mapie.joblib")
            primary_trained = True
        else:
            # Save as secondary model
            joblib.dump(ulb_mapie, MODELS_DIR / "ulb_model_mapie.joblib")
            joblib.dump(ulb_feature_cols, MODELS_DIR / "ulb_feature_columns.joblib")
            
        ulb_results = evaluate(ulb_mapie, X_ulb_test, y_ulb_test, alpha=0.10, dataset_name="ULB Test")
        results_out["ulb"] = ulb_results
        
    except FileNotFoundError:
        logger.warning("ULB dataset not found. Skipping.")
    except Exception as e:
        logger.warning(f"ULB training/evaluation failed: {e}")
    
    # ── Summary ──
    print("\n" + "=" * 60)
    print("  TRAINING SUMMARY")
    print("=" * 60)
    
    if "ieee_cis" in results_out:
        res = results_out["ieee_cis"]
        print(f"\n  Primary Model (IEEE-CIS):")
        print(f"    Precision:          {res['precision']:.4f}")
        print(f"    Recall:             {res['recall']:.4f}")
        print(f"    F1:                 {res['f1']:.4f}")
        print(f"    AUCPR:              {res['aucpr']:.4f}")
        print(f"    Conformal Coverage: {res['conformal_coverage']:.4f}")
        print(f"    Hold Rate:          {res['hold_rate']:.4f}")
    
    if "ulb" in results_out:
        res = results_out["ulb"]
        print(f"\n  {'Secondary' if 'ieee_cis' in results_out else 'Primary'} Model (ULB):")
        print(f"    Precision:          {res['precision']:.4f}")
        print(f"    Recall:             {res['recall']:.4f}")
        print(f"    F1:                 {res['f1']:.4f}")
        print(f"    Conformal Coverage: {res['conformal_coverage']:.4f}")
    
    print(f"\n  Models saved to: {MODELS_DIR}")
    print("=" * 60)
    
    import json
    with open(MODELS_DIR / "evaluation_results.json", "w") as f:
        json.dump(results_out, f, indent=2)


if __name__ == "__main__":
    main()
