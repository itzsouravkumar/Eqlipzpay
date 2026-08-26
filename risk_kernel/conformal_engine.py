"""
EqlipZ Pay — Conformal Risk Engine
====================================
The mathematical heart of EqlipZ Pay: wraps a trained fraud model with
MAPIE conformal prediction to produce prediction SETS with statistical
coverage guarantees, instead of single-point scores.

Prediction set semantics:
  {BENIGN}          → High confidence legitimate → RELEASE
  {FRAUD}           → High confidence fraudulent → REFUSE  
  {BENIGN, FRAUD}   → Model is uncertain        → HOLD (up to 48h)

Coverage guarantee:
  P(true label ∈ prediction set) ≥ 1 - α

  With α = 0.10, this means at least 90% of the time, the true label
  is inside the set the engine produces. This is a distribution-free
  guarantee that holds regardless of the model's internal accuracy.
"""

import logging
import uuid
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from schemas import RiskDecision, ActionType

logger = logging.getLogger("eqlipz.conformal")

MODELS_DIR = Path(__file__).resolve().parent.parent / "data" / "models"


class ConformalRiskEngine:
    """
    Conformal Risk Engine — produces calibrated prediction sets for fraud detection.
    
    This engine wraps a pre-trained LightGBM model with MAPIE conformal calibration.
    On every transaction, it outputs a prediction SET rather than a single label,
    enabling the three-way decision logic (RELEASE / REFUSE / HOLD).
    """
    
    def __init__(self, alpha: float = 0.10):
        self.alpha = alpha
        self.mapie_model = None
        self.feature_columns = None
        self.is_loaded = False
        
        # Runtime statistics
        self._stats = {
            "total_scored": 0,
            "release_count": 0,
            "refuse_count": 0,
            "hold_count": 0,
            "coverage_hits": 0,  # Tracked when ground truth is known
            "coverage_total": 0,
        }
        
        # Try to load model on init
        self._try_load()
    
    def _try_load(self):
        """Attempt to load pre-trained model and calibration artifacts."""
        model_path = MODELS_DIR / "fraud_model_mapie.joblib"
        features_path = MODELS_DIR / "feature_columns.joblib"
        
        if model_path.exists() and features_path.exists():
            try:
                self.mapie_model = joblib.load(model_path)
                self.feature_columns = joblib.load(features_path)
                self.is_loaded = True
                logger.info(f"Conformal engine loaded: {len(self.feature_columns)} features, α={self.alpha}")
            except Exception as e:
                logger.error(f"Failed to load conformal model: {e}")
                self.is_loaded = False
        else:
            logger.warning(
                "Conformal model not found. Run 'python data/train_model.py' first. "
                "Using heuristic fallback mode."
            )
            self.is_loaded = False
    
    def _heuristic_score(self, features: Dict) -> Tuple[List[str], float]:
        """
        Heuristic fallback when the trained model is not available.
        
        Uses simple rules based on transaction amount, velocity, and
        known fraud patterns. This is NOT the production path — it exists
        only so the API is functional before the model is trained.
        """
        amount = features.get("amount", features.get("TransactionAmt", 0))
        tx_count_1h = features.get("transaction_count_1h", 0)
        is_international = features.get("is_international", False)
        
        risk_score = 0.0
        
        # High amount signal
        if amount > 50000:
            risk_score += 0.3
        elif amount > 20000:
            risk_score += 0.15
        
        # Velocity signal
        if tx_count_1h and tx_count_1h > 5:
            risk_score += 0.25
        elif tx_count_1h and tx_count_1h > 2:
            risk_score += 0.1
        
        # International signal
        if is_international:
            risk_score += 0.15
        
        # Add some noise to prevent deterministic behavior
        risk_score = min(1.0, max(0.0, risk_score + np.random.uniform(-0.05, 0.05)))
        
        if risk_score < 0.3:
            return ["BENIGN"], 1.0 - risk_score
        elif risk_score > 0.7:
            return ["FRAUD"], risk_score
        else:
            return ["BENIGN", "FRAUD"], 0.5
    
    def _prepare_features(self, features: Dict) -> Optional[pd.DataFrame]:
        """
        Transform raw transaction features into the format expected by
        the trained model.
        """
        if not self.is_loaded:
            return None
        
        # Create a DataFrame with the expected columns
        row = {}
        for col in self.feature_columns:
            if col in features:
                row[col] = features[col]
            elif col == "TransactionAmt" and "amount" in features:
                row[col] = features["amount"]
            elif col == "log_amount":
                amt = features.get("amount", features.get("TransactionAmt", 0))
                row[col] = np.log1p(amt)
            elif col == "amount_to_mean_ratio":
                amt = features.get("amount", features.get("TransactionAmt", 0))
                row[col] = amt / 150.0  # Approximate mean from training
            else:
                row[col] = 0  # Default for missing features
        
        df = pd.DataFrame([row])
        return df[self.feature_columns]
    
    def score(self, features: Dict) -> RiskDecision:
        """
        Score a transaction and produce a conformal prediction set.
        
        Args:
            features: Dict of transaction features (amount, card info, etc.)
        
        Returns:
            RiskDecision with prediction_set, confidence, and action.
        """
        transaction_id = features.get("payment_id", str(uuid.uuid4())[:12])
        
        if self.is_loaded:
            # ── Real model path ──
            X = self._prepare_features(features)
            if X is not None:
                try:
                    y_pred, y_pis = self.mapie_model.predict_set(X)
                    
                    # Extract prediction set from MAPIE output
                    # y_pis shape: (n_samples, n_classes, 1)
                    prediction_set_mask = y_pis[0, :, 0]  # First sample, first alpha
                    
                    prediction_set = []
                    if prediction_set_mask[0]:  # Class 0 = BENIGN
                        prediction_set.append("BENIGN")
                    if prediction_set_mask[1]:  # Class 1 = FRAUD
                        prediction_set.append("FRAUD")
                    
                    # Handle edge case: empty prediction set → treat as uncertain
                    if not prediction_set:
                        prediction_set = ["BENIGN", "FRAUD"]
                    
                    # Get fraud probability for the risk score
                    fraud_prob = self.mapie_model.estimator_.predict_proba(X)[0, 1]
                    confidence = max(fraud_prob, 1 - fraud_prob)
                    
                except Exception as e:
                    logger.error(f"Model prediction failed: {e}")
                    prediction_set, confidence = self._heuristic_score(features)
            else:
                prediction_set, confidence = self._heuristic_score(features)
        else:
            # ── Heuristic fallback ──
            prediction_set, confidence = self._heuristic_score(features)
        
        # Map prediction set to action
        if prediction_set == ["BENIGN"]:
            action = ActionType.RELEASE
            self._stats["release_count"] += 1
        elif prediction_set == ["FRAUD"]:
            action = ActionType.REFUSE
            self._stats["refuse_count"] += 1
        else:
            action = ActionType.HOLD
            self._stats["hold_count"] += 1
        
        self._stats["total_scored"] += 1
        
        # Build reason codes
        reason_codes = []
        if "FRAUD" in prediction_set:
            fraud_prob_val = 1.0 - confidence if prediction_set == ["BENIGN"] else confidence
            if fraud_prob_val > 0.8:
                reason_codes.append("high_fraud_probability")
            if features.get("amount", 0) > 50000:
                reason_codes.append("high_value_transaction")
            if features.get("is_international", False):
                reason_codes.append("international_transaction")
        if len(prediction_set) > 1:
            reason_codes.append("model_uncertainty")
        
        decision = RiskDecision(
            transaction_id=transaction_id,
            prediction_set=prediction_set,
            confidence=round(confidence, 4),
            action=action,
            reason_codes=reason_codes,
        )
        
        logger.info(
            f"[Conformal Engine] {transaction_id} "
            f"set: {{{', '.join(prediction_set)}}} | "
            f"conf: {confidence:.2f} → {action.value}"
        )
        
        return decision
    
    def update_coverage(self, predicted_set: List[str], true_label: int):
        """
        Update coverage tracking when ground truth becomes available
        (e.g., from dispute outcomes).
        """
        true_label_str = "FRAUD" if true_label == 1 else "BENIGN"
        self._stats["coverage_total"] += 1
        if true_label_str in predicted_set:
            self._stats["coverage_hits"] += 1
    
    def get_coverage_stats(self) -> Dict:
        """Return current coverage and decision statistics."""
        total = self._stats["coverage_total"]
        coverage = (
            self._stats["coverage_hits"] / total if total > 0
            else 1.0 - self.alpha  # Theoretical guarantee before observations
        )
        
        scored = self._stats["total_scored"]
        return {
            "total_scored": scored,
            "release_count": self._stats["release_count"],
            "refuse_count": self._stats["refuse_count"],
            "hold_count": self._stats["hold_count"],
            "empirical_coverage": round(coverage, 4),
            "target_coverage": round(1.0 - self.alpha, 4),
            "coverage_observations": total,
            "model_loaded": self.is_loaded,
            "hold_rate": (
                round(self._stats["hold_count"] / scored, 4) if scored > 0 else 0.0
            ),
        }
