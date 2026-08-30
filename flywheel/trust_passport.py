"""
EqlipZ Pay — Contextual Trust Graph
====================================
Upgrades the Trust Passport to support contextual risk (e.g., trusted for $50 food, untrusted for $2000 electronics).
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import math
from database import get_db_connection
from schemas import TrustCredential, ContextualTrust

logger = logging.getLogger("eqlipz.flywheel.trust")


class ContextualTrustGraph:
    """
    Manages trust passports for entities (vendors/agents).
    """
    
    def __init__(self):
        logger.info("[TrustGraph] Initialized with SQLite backend.")
        
    def _hash_entity(self, entity_id: str) -> str:
        """Hash entity ID to avoid storing raw data."""
        return hashlib.sha256(entity_id.encode()).hexdigest()
        
    def _get_or_create(self, entity_id: str) -> Dict:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trust_passports WHERE entity_id = ?", (entity_id,))
        row = cursor.fetchone()
        
        if not row:
            now = datetime.now().isoformat()
            default_contexts = json.dumps([
                {"domain": "general", "trust_score": 50, "transaction_count": 0}
            ])
            initial_hash = self._hash_entity(f"{entity_id}_v1_{now}")
            
            cursor.execute(
                """
                INSERT INTO trust_passports 
                (entity_id, risk_band, contexts, success_count, dispute_count, fraud_count, credential_hash, version, created_at, last_updated) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (entity_id, "B-MODERATE", default_contexts, 0, 0, 0, initial_hash, "1", now, now)
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM trust_passports WHERE entity_id = ?", (entity_id,))
            row = cursor.fetchone()
            
        conn.close()
        
        passport = dict(row)
        passport['contexts'] = json.loads(passport['contexts'])
        return passport

    def get_trust_credential(self, entity_id: str) -> TrustCredential:
        passport = self._get_or_create(entity_id)
        
        contexts = [ContextualTrust(**c) for c in passport['contexts']]
        
        return TrustCredential(
            credential_id=passport['credential_hash'],
            entity_id=entity_id,
            risk_band=passport['risk_band'],
            contexts=contexts,
            issued_at=datetime.fromisoformat(passport['created_at']),
            expires_at=datetime.now() + timedelta(days=30),
            cryptographic_hash=passport['credential_hash']
        )
        
    def update_trust(
        self,
        entity_id: str,
        domain: str,
        outcome_type: str,
    ) -> TrustCredential:
        """
        outcome_type: 'success', 'dispute', 'fraud'
        """
        passport = self._get_or_create(entity_id)
        
        # Update counts
        if outcome_type == 'success':
            passport['success_count'] += 1
        elif outcome_type == 'dispute':
            passport['dispute_count'] += 1
        elif outcome_type == 'fraud':
            passport['fraud_count'] += 1
            
        # Update contexts
        domain_found = False
        for ctx in passport['contexts']:
            if ctx['domain'] == domain:
                domain_found = True
                ctx['transaction_count'] += 1
                if outcome_type == 'success':
                    ctx['trust_score'] = min(100, ctx['trust_score'] + 5)
                elif outcome_type == 'dispute':
                    ctx['trust_score'] = max(0, ctx['trust_score'] - 20)
                elif outcome_type == 'fraud':
                    ctx['trust_score'] = max(0, ctx['trust_score'] - 50)
                break
                
        if not domain_found:
            new_score = 55 if outcome_type == 'success' else 30
            passport['contexts'].append({
                "domain": domain,
                "trust_score": new_score,
                "transaction_count": 1
            })
            
        # Re-evaluate risk band
        overall_score = sum(c['trust_score'] * c['transaction_count'] for c in passport['contexts']) / max(1, sum(c['transaction_count'] for c in passport['contexts']))
        
        if passport['fraud_count'] > 0:
            risk_band = "D-BLOCK"
        elif overall_score >= 80 and passport['success_count'] > 10 and passport['dispute_count'] == 0:
            risk_band = "A-TRUSTED"
        elif overall_score >= 50:
            risk_band = "B-MODERATE"
        else:
            risk_band = "C-HIGH-RISK"
            
        passport['risk_band'] = risk_band
        passport['version'] = str(int(passport['version']) + 1)
        passport['last_updated'] = datetime.now().isoformat()
        passport['credential_hash'] = self._hash_entity(f"{entity_id}_{passport['version']}_{passport['last_updated']}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            UPDATE trust_passports 
            SET risk_band = ?, contexts = ?, success_count = ?, dispute_count = ?, fraud_count = ?, credential_hash = ?, version = ?, last_updated = ?
            WHERE entity_id = ?
            """,
            (
                passport['risk_band'],
                json.dumps(passport['contexts']),
                passport['success_count'],
                passport['dispute_count'],
                passport['fraud_count'],
                passport['credential_hash'],
                passport['version'],
                passport['last_updated'],
                entity_id
            )
        )
        conn.commit()
        conn.close()
        
        logger.info(f"[TrustGraph] Updated {entity_id} to {risk_band}")
        
        return self.get_trust_credential(entity_id)

    def get_trust_adjustment(self, entity_id: str, domain: str = "general") -> float:
        """
        Calculates a TrustAdjustment multiplier for the ExposureEngine.
        1.0 = Neutral
        < 1.0 = Reduces risk (Trusted)
        > 1.0 = Increases risk (Untrusted)
        """
        passport = self._get_or_create(entity_id)
        
        score = 50
        for ctx in passport['contexts']:
            if ctx['domain'] == domain:
                score = ctx['trust_score']
                break
                
        # Map [0, 100] to [2.0, 0.5] roughly
        # If score is 50, adj is 1.0
        # If score is 100, adj is 0.5 (halves exposure)
        # If score is 0, adj is 2.0 (doubles exposure)
        adj = 2.0 - (score / 100.0) * 1.5
        
        return max(0.5, min(2.0, adj))

    def get_stats(self) -> Dict:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trust_passports")
        total = cursor.fetchone()[0]
        conn.close()
        return {"total_passports": total}
