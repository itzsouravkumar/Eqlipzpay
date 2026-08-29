"""
EqlipZ Pay — Disputes Client
==============================
Interfaces with Razorpay Disputes API to:
  - Accept a dispute (merchant concedes)
  - Contest a dispute (with evidence)
  - Feed resolved outcomes into the calibration loop

PRD §18: "Contesting or accepting a dispute, which also feeds the calibration loop."
"""

import logging
import hashlib
import httpx
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import os

logger = logging.getLogger("eqlipz.actions.disputes")

ENV_PATH = Path(__file__).resolve().parent.parent / "config" / "razorpay_keys.env"


def _load_razorpay_keys() -> tuple:
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id and ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip("'\"")
                if k.strip() == "RAZORPAY_KEY_ID":
                    key_id = v
                elif k.strip() == "RAZORPAY_KEY_SECRET":
                    key_secret = v
    return key_id, key_secret


class DisputesClient:
    """
    Razorpay Disputes API client.
    
    Every resolved dispute (won, lost, accepted) is recorded and
    made available to the CalibrationJob for threshold recalculation.
    """
    
    BASE_URL = "https://api.razorpay.com/v1"
    
    def __init__(self):
        self.key_id, self.key_secret = _load_razorpay_keys()
        self.dry_run = not (self.key_id and self.key_secret)
        
        # In-memory ledger of dispute outcomes for the calibration loop
        self._outcomes: List[Dict] = []
        
        self.client = httpx.Client(
            auth=(self.key_id, self.key_secret) if not self.dry_run else None,
            timeout=10.0,
        )
        
        if self.dry_run:
            logger.warning(
                "[Disputes] No Razorpay credentials. DRY-RUN mode."
            )
    
    def accept_dispute(self, dispute_id: str) -> Dict:
        """
        Accept a dispute — the merchant concedes.
        
        This records the outcome as 'lost' for calibration:
        the system's RELEASE decision was wrong (it was actually fraud).
        """
        if self.dry_run:
            result = {
                "dispute_id": dispute_id,
                "action": "accepted",
                "status": "accepted (dry-run)",
                "dry_run": True,
            }
            logger.info(f"[Disputes] DRY-RUN: Would accept dispute {dispute_id}")
        else:
            try:
                resp = self.client.post(
                    f"{self.BASE_URL}/disputes/{dispute_id}/accept",
                )
                resp.raise_for_status()
                data = resp.json()
                result = {
                    "dispute_id": dispute_id,
                    "action": "accepted",
                    "status": data.get("status", "accepted"),
                    "dry_run": False,
                }
                logger.info(f"[Disputes] Accepted dispute {dispute_id}")
            except Exception as e:
                logger.error(f"[Disputes] Accept error for {dispute_id}: {e}")
                result = {
                    "dispute_id": dispute_id,
                    "error": str(e),
                    "status": "failed",
                    "dry_run": False,
                }
        
        # Record outcome for calibration
        self._record_outcome(dispute_id, "accepted", "FRAUD_CONFIRMED")
        return result
    
    def contest_dispute(
        self,
        dispute_id: str,
        evidence: Optional[Dict] = None,
    ) -> Dict:
        """
        Contest a dispute with evidence.
        
        The outcome (won/lost) arrives later via a webhook or polling.
        """
        if self.dry_run:
            result = {
                "dispute_id": dispute_id,
                "action": "contested",
                "status": "contested (dry-run)",
                "evidence_hash": hashlib.sha256(
                    str(evidence).encode()
                ).hexdigest()[:16] if evidence else None,
                "dry_run": True,
            }
            logger.info(f"[Disputes] DRY-RUN: Would contest dispute {dispute_id}")
        else:
            try:
                payload = {}
                if evidence:
                    payload["documents"] = evidence
                
                resp = self.client.patch(
                    f"{self.BASE_URL}/disputes/{dispute_id}/contest",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                result = {
                    "dispute_id": dispute_id,
                    "action": "contested",
                    "status": data.get("status", "under_review"),
                    "dry_run": False,
                }
                logger.info(f"[Disputes] Contested dispute {dispute_id}")
            except Exception as e:
                logger.error(f"[Disputes] Contest error for {dispute_id}: {e}")
                result = {
                    "dispute_id": dispute_id,
                    "error": str(e),
                    "status": "failed",
                    "dry_run": False,
                }
        
        return result
    
    def on_dispute_resolved(
        self,
        dispute_id: str,
        result: str,
        payment_id: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Dict:
        """
        Ingest a resolved dispute outcome.
        
        This is the key calibration input:
        - 'won' → our REFUSE/HOLD was correct (true positive)
        - 'lost' → our RELEASE was wrong (false negative) 
        - 'accepted' → merchant conceded (also false negative)
        
        Args:
            dispute_id: Razorpay dispute ID.
            result: One of 'won', 'lost', 'accepted'.
            payment_id: Associated payment ID.
            amount: Dispute amount.
        """
        # Map dispute outcome to ground-truth label
        if result in ("won",):
            ground_truth = "FRAUD_CONFIRMED"
        elif result in ("lost", "accepted"):
            ground_truth = "FRAUD_CONFIRMED"  # We failed to catch it
        else:
            ground_truth = "BENIGN_CONFIRMED"
        
        outcome = self._record_outcome(
            dispute_id, result, ground_truth,
            payment_id=payment_id, amount=amount,
        )
        
        logger.info(
            f"[Disputes] Outcome recorded: {dispute_id} → "
            f"{result} (ground_truth={ground_truth})"
        )
        return outcome
    
    def _record_outcome(
        self,
        dispute_id: str,
        result: str,
        ground_truth: str,
        payment_id: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> Dict:
        """Record a dispute outcome in the in-memory ledger."""
        outcome = {
            "dispute_id": dispute_id,
            "result": result,
            "ground_truth": ground_truth,
            "payment_id": payment_id,
            "amount": amount or 0.0,
            "timestamp": datetime.now().isoformat(),
        }
        self._outcomes.append(outcome)
        return outcome
    
    def get_outcomes(self, limit: int = 100) -> List[Dict]:
        """Return recent dispute outcomes for calibration."""
        return self._outcomes[-limit:]
    
    def get_stats(self) -> Dict:
        """Summary statistics for the dashboard."""
        total = len(self._outcomes)
        won = sum(1 for o in self._outcomes if o["result"] == "won")
        lost = sum(1 for o in self._outcomes if o["result"] == "lost")
        accepted = sum(1 for o in self._outcomes if o["result"] == "accepted")
        
        return {
            "total_disputes": total,
            "won": won,
            "lost": lost,
            "accepted": accepted,
            "win_rate": won / total if total > 0 else 0.0,
        }
