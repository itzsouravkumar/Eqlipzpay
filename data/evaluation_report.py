"""
EqlipZ Pay — Evaluation Report Generator
==========================================
Produces the precise evaluation table requested in PRD §23.5.

Evaluates the trained ConformalRiskEngine on a hold-out test set
and writes the metrics to `evaluation_results.json` for the dashboard.
"""

import os
import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score

logger = logging.getLogger("eqlipz.data.evaluate")
logging.basicConfig(level=logging.INFO)


def generate_evaluation_report():
    """Generates the evaluation metrics JSON for the dashboard."""
    
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "processed" / "ulb"
    models_dir = base_dir / "data" / "models"
    
    metrics_path = models_dir / "evaluation_results.json"
    
    # Load test set
    test_path = data_dir / "test.parquet"
    if not test_path.exists():
        logger.error(f"Test data not found at {test_path}")
        return
        
    df_test = pd.read_parquet(test_path)
    X_test = df_test.drop(columns=["isFraud"], errors="ignore")
    y_test = df_test["isFraud"]
    
    # Load standard model (for base metrics)
    model_path = models_dir / "fraud_model_raw.joblib"
    if not model_path.exists():
        logger.error(f"Base model not found at {model_path}")
        return
        
    model = joblib.load(model_path)
    
    # Load conformal wrapper (for coverage)
    conformal_path = models_dir / "fraud_model_mapie.joblib"
    if conformal_path.exists():
        conformal_model = joblib.load(conformal_path)
        has_conformal = True
    else:
        logger.warning("Conformal classifier not found, coverage will not be calculated.")
        has_conformal = False
        
    # Generate point predictions
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    # Base metrics
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    aucpr = average_precision_score(y_test, y_prob)
    
    # Cost metrics approximation (from PRD definition)
    # False Positive cost = missed legitimate transactions (opportunity cost)
    fp = sum((y_pred == 1) & (y_test == 0))
    # Approximation: Assume average transaction size of $100 and 2% fee margin
    fp_cost_estimate_usd = fp * 100 * 0.02
    
    # Conformal metrics
    coverage = 0.0
    if has_conformal:
        try:
            # mapie prediction_set
            _, y_pss = conformal_model.predict_set(X_test)
            
            # y_pss is a boolean array of shape (n_samples, n_classes, n_alphas)
            # Check if true class is in prediction set
            n_samples = len(y_test)
            covered = 0
            
            for i in range(n_samples):
                true_class = int(y_test.iloc[i])
                # Access the prediction set for the true class and the only alpha (index 0)
                if y_pss[i, true_class, 0]:
                    covered += 1
                    
            coverage = covered / n_samples
        except Exception as e:
            logger.error(f"Error calculating conformal coverage: {e}")
    
    # Format table for PRD §23.5 requirements
    report = {
        "dataset": "ULB Credit Card Fraud (Sept 2013)",
        "transactions_evaluated": len(y_test),
        "metrics": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "aucpr": round(aucpr, 3),
            "false_positive_cost_est": f"${fp_cost_estimate_usd:,.2f}",
            "conformal_coverage": f"{coverage * 100:.1f}%" if has_conformal else "N/A"
        },
        "model_type": "LightGBM + Mapie (SplitConformalClassifier)",
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    with open(metrics_path, "w") as f:
        json.dump(report, f, indent=4)
        
    logger.info(f"Evaluation report generated and saved to {metrics_path}")
    
    # Print the report
    print("\n" + "="*50)
    print("EqlipZ Pay - Evaluation Report (PRD §23.5)")
    print("="*50)
    print(f"Dataset:      {report['dataset']}")
    print(f"Transactions: {report['transactions_evaluated']:,}")
    print("-"*50)
    print(f"Precision:    {report['metrics']['precision']:.3f}")
    print(f"Recall:       {report['metrics']['recall']:.3f}")
    print(f"F1 Score:     {report['metrics']['f1_score']:.3f}")
    print(f"AUCPR:        {report['metrics']['aucpr']:.3f}")
    print(f"FP Cost Est:  {report['metrics']['false_positive_cost_est']}")
    print(f"Coverage:     {report['metrics']['conformal_coverage']}")
    print("="*50 + "\n")

if __name__ == "__main__":
    generate_evaluation_report()
