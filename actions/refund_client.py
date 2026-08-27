"""
EqlipZ Pay — Refund Client
============================
Issues refunds on REFUSE decisions via Razorpay Refunds API.
Idempotent via payment_id + reason hash.

PRD §18: "Refunding a payment, for the clearly fraudulent path."
"""

import logging
import hashlib
import httpx
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("eqlipz.actions.refund")

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


class RefundClient:
    """
    Issues refunds for REFUSE decisions.
    
    Every refund is idempotent: the same payment_id + reason
    will not trigger a duplicate refund.
    """
    
    BASE_URL = "https://api.razorpay.com/v1"
    
    def __init__(self):
        self.key_id, self.key_secret = _load_razorpay_keys()
        self.dry_run = not (self.key_id and self.key_secret)
        self._idempotency_cache: Dict[str, Dict] = {}
        self._refund_log: list = []
        
        if self.dry_run:
            logger.warning("[Refund] No Razorpay credentials. DRY-RUN mode.")
    
    def _idempotency_key(self, payment_id: str, reason: str) -> str:
        raw = f"refund:{payment_id}:{reason}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]
    
    def create_refund(
        self,
        payment_id: str,
        amount: Optional[int] = None,
        reason: str = "fraud_detected",
        notes: Optional[Dict] = None,
    ) -> Dict:
        """
        Issue a refund for a payment.
        
        Args:
            payment_id: Razorpay payment ID.
            amount: Refund amount in paise (None = full refund).
            reason: Reason code for the refund.
            notes: Additional metadata.
        
        Returns:
            Refund result dict.
        """
        idem_key = self._idempotency_key(payment_id, reason)
        
        # Idempotency: don't issue duplicate refunds
        if idem_key in self._idempotency_cache:
            logger.info(f"[Refund] Idempotent hit for {payment_id}")
            return self._idempotency_cache[idem_key]
        
        if self.dry_run:
            result = {
                "refund_id": f"rfnd_dry_{payment_id[-8:]}",
                "payment_id": payment_id,
                "amount": amount,
                "reason": reason,
                "status": "processed (dry-run)",
                "dry_run": True,
                "timestamp": datetime.now().isoformat(),
            }
            logger.info(
                f"[Refund] DRY-RUN: Would refund {payment_id} "
                f"amount={amount} reason={reason}"
            )
        else:
            try:
                payload = {"speed": "normal"}
                if amount:
                    payload["amount"] = amount
                if notes:
                    payload["notes"] = notes
                
                resp = httpx.post(
                    f"{self.BASE_URL}/payments/{payment_id}/refund",
                    json=payload,
                    auth=(self.key_id, self.key_secret),
                    headers={"X-Razorpay-Idempotency-Key": idem_key},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                result = {
                    "refund_id": data.get("id", "unknown"),
                    "payment_id": payment_id,
                    "amount": data.get("amount", amount),
                    "reason": reason,
                    "status": data.get("status", "processed"),
                    "dry_run": False,
                    "timestamp": datetime.now().isoformat(),
                }
                logger.info(
                    f"[Refund] Created refund {result['refund_id']} "
                    f"for {payment_id}"
                )
            except Exception as e:
                logger.error(f"[Refund] Error for {payment_id}: {e}")
                result = {
                    "refund_id": None,
                    "payment_id": payment_id,
                    "error": str(e),
                    "status": "failed",
                    "dry_run": False,
                    "timestamp": datetime.now().isoformat(),
                }
        
        self._idempotency_cache[idem_key] = result
        self._refund_log.append(result)
        return result
    
    def get_refund_log(self, limit: int = 50) -> list:
        """Return recent refund operations."""
        return self._refund_log[-limit:]
    
    def get_stats(self) -> Dict:
        """Summary stats for the dashboard."""
        total = len(self._refund_log)
        successful = sum(
            1 for r in self._refund_log
            if "error" not in r
        )
        total_amount = sum(
            r.get("amount", 0) or 0
            for r in self._refund_log
            if "error" not in r
        )
        return {
            "total_refunds": total,
            "successful": successful,
            "failed": total - successful,
            "total_amount_refunded": total_amount,
        }
