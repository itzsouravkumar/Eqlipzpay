from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class TransactionSource(str, Enum):
    HUMAN = "HUMAN"
    AGENT_MCP = "AGENT_MCP"
    AGENT_AP2 = "AGENT_AP2"
    AGENT_UCP = "AGENT_UCP"

class TransactionStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"

class ActionType(str, Enum):
    RELEASE = "RELEASE"
    REFUSE = "REFUSE"
    HOLD = "HOLD"

class IntentAlignment(str, Enum):
    ALIGNED = "ALIGNED"
    AMBIGUOUS = "AMBIGUOUS"
    MISMATCH = "MISMATCH"


# ──────────────────────────────────────────────
# Core Data Models
# ──────────────────────────────────────────────

class Transaction(BaseModel):
    payment_id: str
    amount: int  # Amount in paise/cents
    source: TransactionSource
    status: TransactionStatus
    created_at: datetime = Field(default_factory=datetime.now)

class RiskDecision(BaseModel):
    transaction_id: str
    prediction_set: List[str]  # e.g., ["BENIGN"], ["FRAUD"], or ["BENIGN", "FRAUD"]
    confidence: float
    action: ActionType
    reason_codes: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)

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


# ──────────────────────────────────────────────
# Risk Evaluation API Models (Layer 1 from PRD)
# ──────────────────────────────────────────────

class CartItem(BaseModel):
    name: str
    price: float
    quantity: int = 1
    category: Optional[str] = None

class AgentContext(BaseModel):
    agent_id: str
    protocol: str = "MCP"  # MCP, AP2, UCP
    session_id: Optional[str] = None

class TransactionFeatures(BaseModel):
    """Raw transaction features for risk scoring."""
    amount: float
    card_type: Optional[str] = None
    product_category: Optional[str] = None
    email_domain: Optional[str] = None
    device_type: Optional[str] = None
    ip_country: Optional[str] = None
    is_international: bool = False
    transaction_hour: Optional[int] = None
    days_since_last_transaction: Optional[float] = None
    transaction_count_1h: Optional[int] = None
    transaction_count_24h: Optional[int] = None
    avg_transaction_amount: Optional[float] = None
    # Additional raw features can be passed through
    extra_features: Optional[Dict[str, Any]] = None

class RiskEvaluationRequest(BaseModel):
    """The core POST /v1/risk/evaluate request body from the PRD."""
    transaction: TransactionFeatures
    source: TransactionSource = TransactionSource.HUMAN
    payment_id: Optional[str] = None
    user_intent: Optional[str] = None  # Required for agent transactions
    cart: Optional[List[CartItem]] = None  # Required for agent transactions
    agent_context: Optional[AgentContext] = None

class RiskEvaluationResponse(BaseModel):
    """The core POST /v1/risk/evaluate response body from the PRD."""
    decision: ActionType
    risk_score: float
    intent_alignment: Optional[float] = None
    prediction_set: List[str]
    reason_codes: List[str]
    audit_id: str
    hold_expires_at: Optional[datetime] = None

class RiskStats(BaseModel):
    """GET /v1/risk/stats response."""
    total_transactions: int
    total_released: int
    total_refused: int
    total_held: int
    agents_checked: int
    fraud_prevented_amount: float
    conformal_coverage: float
    false_positive_cost: float

class AuditLogEntry(BaseModel):
    """Single entry in the decision audit log."""
    audit_id: str
    payment_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    source: TransactionSource
    amount: float
    risk_score: float
    prediction_set: List[str]
    intent_alignment: Optional[float] = None
    intent_result: Optional[str] = None
    decision: ActionType
    reason_codes: List[str] = []
    engine: str  # Which engine produced the log
