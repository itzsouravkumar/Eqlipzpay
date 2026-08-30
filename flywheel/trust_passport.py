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
from database import get_db_connection

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
        logger.info("[TrustPassport] Initialized with SQLite backend.")
        
    def _hash_entity(self, entity_id: str) -> str:
        """Hash entity ID to avoid storing raw data."""
        return hashlib.sha256(entity_id.encode()).hexdigest()
        
    def _get_or_create(self, entity_hash: str) -> Dict:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trust_passports WHERE entity_hash = ?", (entity_hash,))
        row = cursor.fetchone()
        
        if not row:
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO trust_passports (entity_hash, created_at, last_updated) VALUES (?, ?, ?)",
                (entity_hash, now, now)
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM trust_passports WHERE entity_hash = ?", (entity_hash,))
            row = cursor.fetchone()
            
        conn.close()
        return dict(row)
    
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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if outcome_type == "benign_tx":
            cursor.execute("UPDATE trust_passports SET benign_count = benign_count + 1, last_updated = ? WHERE entity_hash = ?", (datetime.now().isoformat(), entity_hash))
        elif outcome_type == "cleared_hold":
            cursor.execute("UPDATE trust_passports SET cleared_holds = cleared_holds + 1, last_updated = ? WHERE entity_hash = ?", (datetime.now().isoformat(), entity_hash))
        elif outcome_type == "dispute_lost":
            cursor.execute("UPDATE trust_passports SET disputes_lost = disputes_lost + 1, last_updated = ? WHERE entity_hash = ?", (datetime.now().isoformat(), entity_hash))
        else:
            logger.warning(f"[TrustPassport] Unknown outcome type: {outcome_type}")
            conn.close()
            return passport
            
        conn.commit()
        
        # Record event
        timestamp = datetime.now().isoformat()
        credential_id = f"cred_{hashlib.sha256((entity_hash + outcome_type + timestamp).encode()).hexdigest()[:16]}"
        
        cursor.execute(
            "INSERT INTO credential_log (entity_hash, event_type, timestamp, credential_id) VALUES (?, ?, ?, ?)",
            (entity_hash, outcome_type, timestamp, credential_id)
        )
        conn.commit()
        
        # Fetch updated
        cursor.execute("SELECT * FROM trust_passports WHERE entity_hash = ?", (entity_hash,))
        updated_passport = dict(cursor.fetchone())
        conn.close()
        
        logger.info(
            f"[TrustPassport] Updated passport for {entity_hash[:8]}... "
            f"Event: {outcome_type}"
        )
        
        return updated_passport

    def get_trust_factor(self, entity_id: str) -> float:
        """
        Calculate a trust modifier [0.0, 1.0] to bias the decision router.
        
        1.0 = Max trust (bias towards RELEASE)
        0.5 = Neutral
        0.0 = Distrusted (bias towards REFUSE/HOLD)
        """
        entity_hash = self._hash_entity(entity_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trust_passports WHERE entity_hash = ?", (entity_hash,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return 0.5  # Neutral default
            
        passport = dict(row)
        
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trust_passports")
        total_passports = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM credential_log")
        credentials_issued = cursor.fetchone()[0]
        conn.close()
        
        return {
            "total_passports": total_passports,
            "credentials_issued": credentials_issued,
        }
