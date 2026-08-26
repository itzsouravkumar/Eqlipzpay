"""
EqlipZ Pay — Decision Router
==============================
The three-way decision combiner: takes outputs from the Conformal Risk
Engine and the Semantic Entailment Engine, and produces a single action:
RELEASE, REFUSE, or HOLD.

Decision logic:

  For HUMAN transactions (webhook path):
    - Only the conformal engine is consulted.
    - {BENIGN} → RELEASE
    - {FRAUD}  → REFUSE
    - {BENIGN, FRAUD} → HOLD

  For AGENT transactions (MCP/AP2/UCP path):
    - Both engines are consulted.
    - Conformal {BENIGN} AND semantic ALIGNED    → RELEASE
    - Conformal {FRAUD}  OR  semantic MISMATCH   → REFUSE
    - Anything else (uncertainty in either)      → HOLD

Every decision is logged to an immutable audit trail for:
  1. The calibration feedback loop (Day 4)
  2. The web control plane dashboard
  3. Dispute evidence generation
"""

import uuid
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from schemas import (
    ActionType, TransactionSource, IntentAlignment,
    RiskDecision, AuditLogEntry,
)

logger = logging.getLogger("eqlipz.router")


class DecisionRouter:
    """
    Decision Router — the final decision point in the EqlipZ Pay pipeline.
    
    Combines conformal risk scores with semantic intent alignment to produce
    a single action (RELEASE, REFUSE, HOLD), along with a full audit trail.
    """
    
    def __init__(self, hold_max_hours: int = 48, agent_hold_bias: float = 0.1):
        self.hold_max_hours = hold_max_hours
        self.agent_hold_bias = agent_hold_bias
        
        # Immutable audit trail — every decision is recorded here
        self._audit_log: List[AuditLogEntry] = []
        
        # Decision counters
        self._stats = {
            "total_routed": 0,
            "release": 0,
            "refuse": 0,
            "hold": 0,
            "agent_transactions": 0,
            "human_transactions": 0,
            "fraud_prevented_amount": 0.0,
            "held_amount": 0.0,
        }
    
    def route(
        self,
        risk_decision: RiskDecision,
        intent_result: Optional[Dict] = None,
        source: TransactionSource = TransactionSource.HUMAN,
        amount: float = 0.0,
        payment_id: str = "",
    ) -> Dict:
        """
        Route a transaction to its final decision.
        
        Args:
            risk_decision: Output from the Conformal Risk Engine
            intent_result: Output from the Semantic Entailment Engine (agent only)
            source: Who initiated the transaction (HUMAN vs AGENT_*)
            amount: Transaction amount for monetary tracking
            payment_id: Razorpay payment ID
        
        Returns:
            Dict with:
              - action: ActionType
              - audit_id: str
              - reason_codes: List[str]
              - hold_expires_at: Optional[datetime] (only for HOLD)
              - risk_score: float
              - intent_alignment: Optional[float]
        """
        audit_id = f"EP-{uuid.uuid4().hex[:8].upper()}"
        prediction_set = risk_decision.prediction_set
        reason_codes = list(risk_decision.reason_codes)
        
        is_agent = source in (
            TransactionSource.AGENT_MCP,
            TransactionSource.AGENT_AP2,
            TransactionSource.AGENT_UCP,
        )
        
        # ── Decision Logic ──
        
        if is_agent and intent_result:
            # AGENT path: combine conformal + semantic
            self._stats["agent_transactions"] += 1
            
            alignment = intent_result.get("alignment", IntentAlignment.AMBIGUOUS)
            alignment_score = intent_result.get("alignment_score", 0.5)
            intent_reasons = intent_result.get("reason_codes", [])
            reason_codes.extend(intent_reasons)
            
            if prediction_set == ["BENIGN"] and alignment == IntentAlignment.ALIGNED:
                action = ActionType.RELEASE
            elif prediction_set == ["FRAUD"] or alignment == IntentAlignment.MISMATCH:
                action = ActionType.REFUSE
                if alignment == IntentAlignment.MISMATCH:
                    reason_codes.append("agent_intent_mismatch")
            else:
                action = ActionType.HOLD
                if alignment == IntentAlignment.AMBIGUOUS:
                    reason_codes.append("ambiguous_intent")
        else:
            # HUMAN path: conformal only
            self._stats["human_transactions"] += 1
            alignment_score = None
            
            if prediction_set == ["BENIGN"]:
                action = ActionType.RELEASE
            elif prediction_set == ["FRAUD"]:
                action = ActionType.REFUSE
            else:
                action = ActionType.HOLD
        
        # ── Update stats ──
        self._stats["total_routed"] += 1
        self._stats[action.value.lower()] += 1
        
        if action == ActionType.REFUSE:
            self._stats["fraud_prevented_amount"] += amount
        elif action == ActionType.HOLD:
            self._stats["held_amount"] += amount
        
        # ── Compute hold expiry ──
        hold_expires_at = None
        if action == ActionType.HOLD:
            hold_expires_at = datetime.now() + timedelta(hours=self.hold_max_hours)
        
        # ── Build risk score ──
        # For display: fraud probability normalized to 0-1
        if prediction_set == ["BENIGN"]:
            risk_score = 1.0 - risk_decision.confidence
        elif prediction_set == ["FRAUD"]:
            risk_score = risk_decision.confidence
        else:
            risk_score = 0.5  # Uncertain
        
        # ── Log to audit trail ──
        audit_entry = AuditLogEntry(
            audit_id=audit_id,
            payment_id=payment_id or risk_decision.transaction_id,
            source=source,
            amount=amount,
            risk_score=round(risk_score, 4),
            prediction_set=prediction_set,
            intent_alignment=alignment_score if is_agent else None,
            intent_result=intent_result.get("alignment", IntentAlignment.ALIGNED).value if intent_result else None,
            decision=action,
            reason_codes=reason_codes,
            engine="conformal+semantic" if is_agent else "conformal",
        )
        self._audit_log.append(audit_entry)
        
        # ── Log for the engine log panel ──
        log_prefix = "[Decision Router]" if len(prediction_set) > 1 else "[Conformal Engine]"
        log_msg = (
            f"{log_prefix} {payment_id or risk_decision.transaction_id} "
            f"set: {{{', '.join(prediction_set)}}}"
        )
        if is_agent and alignment_score is not None:
            log_msg += f" | alignment: {alignment_score:.2f}"
        log_msg += f" → {action.value}"
        if hold_expires_at:
            log_msg += f" ({self.hold_max_hours}h)"
        
        logger.info(log_msg)
        
        return {
            "action": action,
            "audit_id": audit_id,
            "reason_codes": reason_codes,
            "hold_expires_at": hold_expires_at,
            "risk_score": round(risk_score, 4),
            "prediction_set": prediction_set,
            "intent_alignment": alignment_score,
        }
    
    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Return the most recent audit log entries for the dashboard."""
        entries = self._audit_log[-limit:]
        entries.reverse()  # Most recent first
        return [
            {
                "audit_id": e.audit_id,
                "payment_id": e.payment_id,
                "timestamp": e.timestamp.isoformat(),
                "source": e.source.value,
                "amount": e.amount,
                "risk_score": e.risk_score,
                "prediction_set": e.prediction_set,
                "intent_alignment": e.intent_alignment,
                "decision": e.decision.value,
                "reason_codes": e.reason_codes,
                "engine": e.engine,
            }
            for e in entries
        ]
    
    def get_risk_log(self, limit: int = 20) -> List[Dict]:
        """
        Return engine log entries for the Conformal Engine Log panel.
        
        Formatted as human-readable log messages with timestamps.
        """
        entries = self._audit_log[-limit:]
        entries.reverse()
        
        logs = []
        for e in entries:
            time_str = e.timestamp.strftime("%I:%M:%S %p")
            
            # Build the engine-tagged log message
            if len(e.prediction_set) > 1:
                engine_tag = "[Decision Router]"
            elif e.intent_result and e.intent_result == "MISMATCH":
                engine_tag = "[Semantic Engine]"
            else:
                engine_tag = "[Conformal Engine]"
            
            pid_short = e.payment_id[:12] + "..." if len(e.payment_id) > 12 else e.payment_id
            
            msg = f"{engine_tag} {pid_short} set: {{{', '.join(e.prediction_set)}}}"
            if e.intent_alignment is not None:
                msg += f" | alignment: {e.intent_alignment:.2f}"
            msg += f" | conf: {e.risk_score:.2f} → {e.decision.value}"
            
            if e.decision == ActionType.HOLD:
                msg += f" ({self.hold_max_hours}h)"
            
            # Extra semantic line if mismatch detected
            if e.intent_result == "MISMATCH":
                logs.append({
                    "time": time_str,
                    "msg": f"[Semantic Engine] {pid_short} CART MISMATCH DETECTED",
                    "engine": "semantic",
                })
            
            logs.append({
                "time": time_str,
                "msg": msg,
                "engine": engine_tag.strip("[]").lower().replace(" ", "_"),
            })
        
        return logs
    
    def get_stats(self) -> Dict:
        """Return router statistics for the dashboard."""
        return {
            "total_routed": self._stats["total_routed"],
            "release": self._stats["release"],
            "refuse": self._stats["refuse"],
            "hold": self._stats["hold"],
            "agent_transactions": self._stats["agent_transactions"],
            "human_transactions": self._stats["human_transactions"],
            "fraud_prevented_amount": round(self._stats["fraud_prevented_amount"], 2),
            "held_amount": round(self._stats["held_amount"], 2),
        }
