"""
EqlipZ Pay — Calibration Feedback Loop
=========================================
Ingests dispute outcomes and hold resolutions to recalibrate
the conformal engine's thresholds on a rolling 24-hour window.

PRD §17: "Recomputes thresholds from dispute outcomes."
PRD §20.6: "Feed every resolved dispute back into the calibration set within 24 hours."
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("eqlipz.flywheel.calibration")


class CalibrationJob:
    """
    Rolling recalibration engine.
    
    Collects ground-truth labels from:
    - Dispute outcomes (won → our REFUSE was correct; lost → our RELEASE was wrong)
    - Hold resolutions (manual verdicts by risk analysts)
    - Auto-released holds (48h timeout → treated as BENIGN)
    
    When enough new labels accumulate, triggers a recalibration
    of the conformal engine's alpha threshold.
    """
    
    # Minimum number of new outcomes before triggering recalibration
    MIN_RECALIBRATION_BATCH = 10
    
    def __init__(
        self,
        target_coverage: float = 0.90,
        recalibration_window_hours: int = 24,
    ):
        self.target_coverage = target_coverage
        self.recalibration_window = timedelta(hours=recalibration_window_hours)
        
        # Ground-truth label store: list of {timestamp, prediction, ground_truth, amount}
        self._labels: List[Dict] = []
        
        # Recalibration history
        self._calibration_log: List[Dict] = []
        
        # Current thresholds (will be updated by recalibrate())
        self.current_alpha = 1.0 - target_coverage  # 0.10 for 90% coverage
        
        # Reference to the conformal engine (set externally)
        self._conformal_engine = None
        
        logger.info(
            f"[Calibration] Initialized. Target coverage={target_coverage}, "
            f"window={recalibration_window_hours}h"
        )
    
    def set_conformal_engine(self, engine):
        """Attach the conformal engine for live recalibration."""
        self._conformal_engine = engine
        logger.info("[Calibration] Conformal engine attached for live recalibration.")
    
    def ingest_outcome(
        self,
        payment_id: str,
        our_prediction: str,
        ground_truth: str,
        amount: float = 0.0,
        source: str = "dispute",
    ):
        """
        Ingest a single ground-truth outcome.
        
        Args:
            payment_id: The payment this outcome relates to.
            our_prediction: What we predicted (RELEASE, HOLD, REFUSE).
            ground_truth: The actual outcome (FRAUD_CONFIRMED, BENIGN_CONFIRMED).
            amount: Transaction amount (for EMV calculation).
            source: Where this label came from (dispute, hold_resolution, auto_release).
        """
        label = {
            "payment_id": payment_id,
            "prediction": our_prediction,
            "ground_truth": ground_truth,
            "amount": amount,
            "source": source,
            "timestamp": datetime.now(),
        }
        self._labels.append(label)
        
        logger.info(
            f"[Calibration] Label ingested: {payment_id} "
            f"predicted={our_prediction} truth={ground_truth} "
            f"source={source}"
        )
        
        # Check if we have enough new labels to trigger recalibration
        recent = self._get_recent_labels()
        if len(recent) >= self.MIN_RECALIBRATION_BATCH:
            self.recalibrate()
    
    def _get_recent_labels(self) -> List[Dict]:
        """Get labels within the recalibration window."""
        cutoff = datetime.now() - self.recalibration_window
        return [l for l in self._labels if l["timestamp"] >= cutoff]
    
    def recalibrate(self) -> Dict:
        """
        Recalibrate the conformal thresholds.
        
        Computes the empirical error rate from recent outcomes and
        adjusts alpha to maintain the target coverage.
        
        Returns:
            Calibration result with old/new alpha and metrics.
        """
        recent = self._get_recent_labels()
        
        if len(recent) < 3:
            logger.info(
                "[Calibration] Not enough labels for recalibration "
                f"({len(recent)} < 3)"
            )
            return {"status": "skipped", "reason": "insufficient_labels"}
        
        # Count prediction accuracy
        correct = 0
        total = len(recent)
        false_negatives = 0  # RELEASED but was actually fraud
        false_positives = 0  # REFUSED but was actually benign
        true_positives = 0   # REFUSED and was actually fraud
        fn_cost = 0.0
        fp_cost = 0.0
        
        for label in recent:
            pred = label["prediction"]
            truth = label["ground_truth"]
            amt = label["amount"]
            
            if truth == "FRAUD_CONFIRMED":
                if pred in ("REFUSE", "HOLD"):
                    correct += 1
                    true_positives += 1
                else:
                    false_negatives += 1
                    fn_cost += amt  # Lost to fraud
            elif truth == "BENIGN_CONFIRMED":
                if pred in ("RELEASE",):
                    correct += 1
                elif pred in ("REFUSE",):
                    false_positives += 1
                    fp_cost += amt * 0.02  # Opportunity cost ~2%
                else:
                    correct += 1  # HOLD that resolved as benign is OK
        
        empirical_coverage = correct / total if total > 0 else 0.0
        old_alpha = self.current_alpha
        
        # Adjust alpha to nudge coverage toward target
        coverage_gap = self.target_coverage - empirical_coverage
        
        if abs(coverage_gap) > 0.02:  # Only adjust if drift is significant
            # If coverage too low → decrease alpha (widen prediction sets)
            # If coverage too high → increase alpha (tighten prediction sets)
            adjustment = coverage_gap * 0.1  # Gradual adjustment
            new_alpha = max(0.01, min(0.20, self.current_alpha - adjustment))
            self.current_alpha = new_alpha
            
            # Push new alpha to the conformal engine
            if self._conformal_engine:
                self._conformal_engine.alpha = new_alpha
                logger.info(
                    f"[Calibration] Pushed new alpha={new_alpha:.4f} "
                    f"to conformal engine"
                )
        else:
            new_alpha = old_alpha
        
        result = {
            "status": "recalibrated",
            "timestamp": datetime.now().isoformat(),
            "labels_used": total,
            "empirical_coverage": round(empirical_coverage, 4),
            "target_coverage": self.target_coverage,
            "old_alpha": round(old_alpha, 4),
            "new_alpha": round(new_alpha, 4),
            "alpha_changed": old_alpha != new_alpha,
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "true_positives": true_positives,
            "fn_cost": round(fn_cost, 2),
            "fp_cost": round(fp_cost, 2),
        }
        
        self._calibration_log.append(result)
        
        logger.info(
            f"[Calibration] Recalibrated: coverage={empirical_coverage:.4f} "
            f"alpha {old_alpha:.4f} → {new_alpha:.4f} "
            f"(FN={false_negatives}, FP={false_positives})"
        )
        
        return result
    
    def get_drift_metrics(self) -> Dict:
        """
        Returns whether current coverage is drifting from target.
        Used by the dashboard to show a drift indicator.
        """
        recent = self._get_recent_labels()
        
        if len(recent) < 5:
            return {
                "status": "insufficient_data",
                "labels_in_window": len(recent),
                "drift_detected": False,
            }
        
        correct = 0
        for label in recent:
            pred = label["prediction"]
            truth = label["ground_truth"]
            if truth == "FRAUD_CONFIRMED" and pred in ("REFUSE", "HOLD"):
                correct += 1
            elif truth == "BENIGN_CONFIRMED" and pred in ("RELEASE",):
                correct += 1
        
        empirical = correct / len(recent)
        drift = abs(empirical - self.target_coverage)
        
        return {
            "status": "ok" if drift < 0.05 else "drifting",
            "labels_in_window": len(recent),
            "empirical_coverage": round(empirical, 4),
            "target_coverage": self.target_coverage,
            "drift": round(drift, 4),
            "drift_detected": drift >= 0.05,
            "current_alpha": round(self.current_alpha, 4),
        }
    
    def get_calibration_log(self, limit: int = 20) -> List[Dict]:
        """Return recent calibration events."""
        return self._calibration_log[-limit:]
    
    def get_stats(self) -> Dict:
        """Summary stats for the dashboard."""
        recent = self._get_recent_labels()
        return {
            "total_labels": len(self._labels),
            "labels_in_window": len(recent),
            "calibrations_performed": len(self._calibration_log),
            "current_alpha": round(self.current_alpha, 4),
            "target_coverage": self.target_coverage,
            "window_hours": self.recalibration_window.total_seconds() / 3600,
        }
