"""
EqlipZ Pay — Trust Passport Service
=====================================
A portable, hashed trust credential system for merchants and vendors.

PRD §17: "The trust credentials map to sub-merchants... issued when holds are cleared safely."
PRD §20.7: "Portable Trust Credentials (Trust Passport)."
"""

import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import math

logger = logging.getLogger("eqlipz.flywheel.trust")


class TrustPassportService:
    """
    Manages trust passports for entities (vendors/agents).
    
    A trust passport builds up over time based on:
    - Successful transactions without disputes (benign history)
    - Holds that cleared safely (adds strong trust signal)
    - Conceded/lost disputes (removes trust signal)
    
    Never stores raw personal data; uses SHA-256 hashes for entity identifiers.
    """
    
    def __init__(self):
        # In-memory ledger mapping entity_hash -> passport data
        self._ledgers: Dict[str, Dict] = {}
        
        # Log of issued credentials
        self._credential_log: List[Dict] = []
        
        logger.info("[TrustPassport] Initialized.")
        
    def _hash_entity(self, entity_id: str) -> str:
        """Hash entity ID to avoid storing raw data."""
        return hashlib.sha256(entity_id.encode()).hexdigest()
        
    def _get_or_create(self, entity_hash: str) -> Dict:
        if entity_hash not in self._ledgers:
            self._ledgers[entity_hash] = {
                "entity_hash": entity_hash,
                "benign_count": 0,
                "cleared_holds": 0,
                "disputes_lost": 0,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }
        return self._ledgers[entity_hash]
    
    def issue_credential(
        self,
        entity_id: str,
        outcome_type: str,
    ) -> Dict:
        """
        Issue a credential/update passport based on an outcome.
        
        Args:
            entity_id: The raw vendor/agent ID.
            outcome_type: 'benign_tx', 'cleared_hold', 'dispute_lost'
        """
        entity_hash = self._hash_entity(entity_id)
        passport = self._get_or_create(entity_hash)
        
        if outcome_type == "benign_tx":
            passport["benign_count"] += 1
        elif outcome_type == "cleared_hold":
            passport["cleared_holds"] += 1
        elif outcome_type == "dispute_lost":
            passport["disputes_lost"] += 1
        else:
            logger.warning(f"[TrustPassport] Unknown outcome type: {outcome_type}")
            return passport
            
        passport["last_updated"] = datetime.now().isoformat()
        self._ledgers[entity_hash] = passport
        
        # Record event
        event = {
            "entity_hash": entity_hash,
            "event_type": outcome_type,
            "timestamp": passport["last_updated"],
            "credential_id": f"cred_{hashlib.sha256((entity_hash + outcome_type + passport['last_updated']).encode()).hexdigest()[:16]}"
        }
        self._credential_log.append(event)
        
        logger.info(
            f"[TrustPassport] Updated passport for {entity_hash[:8]}... "
            f"Event: {outcome_type}"
        )
        
        return passport

    def get_trust_factor(self, entity_id: str) -> float:
        """
        Calculate a trust modifier [0.0, 1.0] to bias the decision router.
        
        1.0 = Max trust (bias towards RELEASE)
        0.5 = Neutral
        0.0 = Distrusted (bias towards REFUSE/HOLD)
        """
        entity_hash = self._hash_entity(entity_id)
        if entity_hash not in self._ledgers:
            return 0.5  # Neutral default
            
        passport = self._ledgers[entity_hash]
        
        # Base formula:
        # Cleared holds are worth 5x normal benign transactions.
        # Disputes heavily penalize the score.
        
        positive_signal = passport["benign_count"] + (passport["cleared_holds"] * 5)
        negative_signal = passport["disputes_lost"] * 20
        
        # Sigmoid-like scaling
        net_score = positive_signal - negative_signal
        
        # Maps -inf to 0.0, 0 to 0.5, +inf to 1.0
        trust_factor = 1.0 / (1.0 + math.exp(-net_score * 0.1))
        
        return float(trust_factor)
        
    def check_trust(self, entity_id: str) -> Dict:
        """Return full trust passport and current factor."""
        entity_hash = self._hash_entity(entity_id)
        passport = self._get_or_create(entity_hash)
        
        return {
            "passport": passport,
            "trust_factor": round(self.get_trust_factor(entity_id), 4)
        }
        
    def get_stats(self) -> Dict:
        """Summary stats for dashboard."""
        return {
            "total_passports": len(self._ledgers),
            "credentials_issued": len(self._credential_log),
        }
