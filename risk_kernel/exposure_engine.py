import logging
from typing import Dict, Any
from database import get_db_connection

logger = logging.getLogger("eqlipz.exposure")

class ExposureEngine:
    """
    Risk-Adaptive Exposure Engine (PRD Section 6)
    Calculates the financial exposure score E*
    """
    
    def __init__(self):
        # Default Loss Given Default
        # In a real system, this varies by product category, merchant recoverability, etc.
        self.default_lgd = 0.60 

    def calculate_exposure(
        self,
        fraud_prob: float,
        amount: float,
        merchant_id: str = "default_merchant",
        intent_risk: float = 1.0,
        trust_adjustment: float = 1.0,
        lgd: float = None
    ) -> float:
        """
        E* = P(Fraud) * LGD * Amount * NetworkRisk * IntentRisk * TrustAdjustment
        
        Note: TrustAdjustment is typically a multiplier < 1.0 for trusted entities,
        and > 1.0 for untrusted entities.
        """
        if lgd is None:
            lgd = self.default_lgd

        # Fetch dynamic variables from DB
        network_risk = self._fetch_network_risk()
        merchant_liquidity_penalty = self._fetch_merchant_liquidity_penalty(merchant_id)
            
        e_star = fraud_prob * lgd * amount * network_risk * intent_risk * trust_adjustment * merchant_liquidity_penalty
        
        logger.info(
            f"[Exposure] E* Calculated: {e_star:.2f} "
            f"(P(F)={fraud_prob:.3f}, Amt={amount}, NetRisk={network_risk:.2f}, MerchPenalty={merchant_liquidity_penalty:.2f})"
        )
        
        return e_star

    def _fetch_network_risk(self) -> float:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT anomaly_score FROM network_velocity ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            conn.close()
            if row and row["anomaly_score"] > 1.0:
                return row["anomaly_score"]
        except Exception:
            pass
        return 1.0

    def _fetch_merchant_liquidity_penalty(self, merchant_id: str) -> float:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT available_balance, risk_tier FROM merchant_liquidity WHERE merchant_id=?", (merchant_id,))
            row = c.fetchone()
            conn.close()
            if row:
                if row["available_balance"] < 1000 and row["risk_tier"] == "HIGH":
                    return 1.5 # 50% penalty if low liquidity
                if row["available_balance"] > 100000:
                    return 0.9 # Small discount for high liquidity
        except Exception:
            pass
        return 1.0

exposure_engine = ExposureEngine()
