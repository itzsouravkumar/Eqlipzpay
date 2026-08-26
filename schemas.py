from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class TransactionSource(str, Enum):
    HUMAN = "HUMAN"
    AGENT_MCP = "AGENT_MCP"
    AGENT_AP2 = "AGENT_AP2"
    AGENT_UCP = "AGENT_UCP"

class TransactionStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"

class Transaction(BaseModel):
    payment_id: str
    amount: int  # Amount in paise/cents
    source: TransactionSource
    status: TransactionStatus
    created_at: datetime = datetime.now()

class ActionType(str, Enum):
    RELEASE = "RELEASE"
    REFUSE = "REFUSE"
    HOLD = "HOLD"

class RiskDecision(BaseModel):
    transaction_id: str
    prediction_set: List[str]  # e.g., ["benign"], ["fraud"], or ["benign", "fraud"]
    confidence: float
    action: ActionType
    created_at: datetime = datetime.now()

class EscrowHold(BaseModel):
    transfer_id: str
    hold_until: datetime
    verdict: Optional[str] = None
    resolved_by: Optional[str] = None

class DisputeOutcome(BaseModel):
    dispute_id: str
    phase: str
    result: str
    evidence_reference: Optional[str] = None

class TrustPassport(BaseModel):
    entity_id: str
    hold_count: int
    benign_count: int
    credential_hash: str
