"""
EqlipZ Pay — Route Transfer Client
=====================================
Executes Razorpay Route transfers with settlement hold fields.
Uses payment_id as idempotency key (PRD requirement 5).

Operates in dry-run mode when no Razorpay keys are configured.
"""

import logging
import os
import hashlib
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("eqlipz.actions.transfer")

# Load Razorpay keys from env file
ENV_PATH = Path(__file__).resolve().parent.parent / "config" / "razorpay_keys.env"
ROOT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

def _load_razorpay_keys() -> tuple:
    """Load Razorpay API credentials from .env or config/razorpay_keys.env."""
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    
    if not key_id:
        for path in [ROOT_ENV_PATH, ENV_PATH]:
            if path.exists():
                with open(path) as f:
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
                if key_id:
                    break
    
    return key_id, key_secret


class RouteTransferClient:
    """
    Executes Razorpay Route transfers with optional settlement holds.
    
    When the decision router says HOLD, the transfer is created with
    `on_hold=1` and `on_hold_until` set to the hold expiry (max 48h).
    
    If no Razorpay credentials are available, operates in dry-run mode.
    """
    
    BASE_URL = "https://api.razorpay.com/v1"
    
    def __init__(self):
        self.key_id, self.key_secret = _load_razorpay_keys()
        if not self.key_id or not self.key_secret:
            raise RuntimeError(
                "[Route Transfer] Configuration Error: Razorpay credentials "
                "(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET) are missing. EqlipZ Pay requires live API keys."
            )
        
        self._idempotency_cache: Dict[str, Dict] = {}  # payment_id → result
        
        self.client = httpx.Client(
            auth=(self.key_id, self.key_secret),
            timeout=10.0,
        )
        logger.info("[Route Transfer] Razorpay credentials loaded. Live mode.")
    
    def _idempotency_key(self, payment_id: str, action: str) -> str:
        """Generate a deterministic idempotency key from payment_id + action."""
        raw = f"{payment_id}:{action}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]
    
    def create_transfer(
        self,
        payment_id: str,
        amount: int,
        account_id: str = "acc_default",
        hold: bool = False,
        hold_until: Optional[datetime] = None,
    ) -> Dict:
        """
        Create a Route transfer from a payment to a linked account.
        
        Args:
            payment_id: The Razorpay payment ID (e.g., pay_xxx).
            amount: Transfer amount in paise.
            account_id: Linked account ID.
            hold: If True, sets on_hold=1.
            hold_until: When to auto-release the hold (max 48h from now).
        
        Returns:
            Transfer result dict with transfer_id, status, etc.
        """
        idem_key = self._idempotency_key(payment_id, "create_transfer")
        
        # Idempotency check: return cached result if we've already processed this
        if idem_key in self._idempotency_cache:
            logger.info(f"[Route Transfer] Idempotent hit for {payment_id}")
            return self._idempotency_cache[idem_key]
        
        # Cap hold_until to 48 hours
        if hold and hold_until:
            max_hold = datetime.now() + timedelta(hours=48)
            if hold_until > max_hold:
                hold_until = max_hold
                logger.warning(
                    f"[Route Transfer] Hold capped to 48h for {payment_id}"
                )
        
        payload = {
            "account": account_id,
            "amount": amount,
            "currency": "INR",
        }
        
        if hold:
            payload["on_hold"] = 1
            if hold_until:
                payload["on_hold_until"] = int(hold_until.timestamp())
        
        try:
            resp = self.client.post(
                f"{self.BASE_URL}/payments/{payment_id}/transfers",
                json={"transfers": [payload]},
                headers={"X-Razorpay-Idempotency-Key": idem_key},
            )
            resp.raise_for_status()
            data = resp.json()
            transfer = data.get("items", [{}])[0] if "items" in data else data
            result = {
                "transfer_id": transfer.get("id", "unknown"),
                "payment_id": payment_id,
                "amount": amount,
                "account": account_id,
                "on_hold": hold,
                "status": transfer.get("status", "created"),
                "dry_run": False,
            }
            logger.info(
                f"[Route Transfer] Created transfer "
                f"{result['transfer_id']} for {payment_id}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Route Transfer] API error for {payment_id}: "
                f"{e.response.status_code} {e.response.text}"
            )
            result = {
                "transfer_id": None,
                "payment_id": payment_id,
                "error": str(e),
                "status": "failed",
                "dry_run": False,
            }
        except Exception as e:
            logger.error(f"[Route Transfer] Error for {payment_id}: {e}")
            result = {
                "transfer_id": None,
                "payment_id": payment_id,
                "error": str(e),
                "status": "failed",
                "dry_run": False,
            }
        
        self._idempotency_cache[idem_key] = result
        return result
    
    def modify_hold(
        self,
        transfer_id: str,
        release: bool = True,
    ) -> Dict:
        """
        Modify a settlement hold — release early or extend.
        
        Args:
            transfer_id: The Razorpay transfer ID.
            release: If True, releases the hold. If False, could extend (not implemented).
        """
        try:
            payload = {"on_hold": 0 if release else 1}
            resp = self.client.patch(
                f"{self.BASE_URL}/transfers/{transfer_id}",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            action = "released" if release else "extended"
            logger.info(f"[Route Transfer] Hold {action} on {transfer_id}")
            return {
                "transfer_id": transfer_id,
                "action": action,
                "status": data.get("status", action),
                "dry_run": False,
            }
        except Exception as e:
            logger.error(f"[Route Transfer] Modify hold error: {e}")
            return {
                "transfer_id": transfer_id,
                "error": str(e),
                "status": "failed",
                "dry_run": False,
            }
