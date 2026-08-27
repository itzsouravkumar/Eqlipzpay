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
    name: str = Field(..., description="Name of the product or service being purchased.")
    price: float = Field(..., description="Price per unit of the item.")
    quantity: int = Field(1, description="Number of units purchased.")
    category: Optional[str] = Field(None, description="Product category (e.g., 'electronics', 'software').")

class AgentContext(BaseModel):
    agent_id: str = Field(..., description="Unique identifier for the AI agent initiating the transaction.")
    protocol: str = Field("MCP", description="Agent protocol used (e.g., 'MCP', 'AP2', 'UCP').")
    session_id: Optional[str] = Field(None, description="Session ID linking the transaction to a specific user-agent interaction.")

class TransactionFeatures(BaseModel):
    """Raw transaction features for risk scoring."""
    amount: float = Field(..., description="Transaction amount in standard currency units.")
    card_type: Optional[str] = Field(None, description="Type of the card used (e.g., 'credit', 'debit').")
    product_category: Optional[str] = Field(None, description="Broad category of the product or service.")
    email_domain: Optional[str] = Field(None, description="Domain of the buyer's email address.")
    device_type: Optional[str] = Field(None, description="Device used for the transaction (e.g., 'mobile', 'desktop').")
    ip_country: Optional[str] = Field(None, description="Country code derived from the buyer's IP address.")
    is_international: bool = Field(False, description="Flag indicating if the transaction crosses borders.")
    transaction_hour: Optional[int] = Field(None, description="Hour of the day the transaction occurred (0-23).")
    days_since_last_transaction: Optional[float] = Field(None, description="Days elapsed since the user's last transaction.")
    transaction_count_1h: Optional[int] = Field(None, description="Number of transactions by this user in the last hour.")
    transaction_count_24h: Optional[int] = Field(None, description="Number of transactions by this user in the last 24 hours.")
    avg_transaction_amount: Optional[float] = Field(None, description="Average transaction amount for this user historically.")
    # Additional raw features can be passed through
    extra_features: Optional[Dict[str, Any]] = Field(None, description="Any additional dynamic features for the risk model.")

class RiskEvaluationRequest(BaseModel):
    """The core POST /v1/risk/evaluate request body from the PRD."""
    transaction: TransactionFeatures = Field(..., description="Detailed features of the transaction to be evaluated.")
    source: TransactionSource = Field(TransactionSource.HUMAN, description="Origin of the transaction (Human vs AI Agent).")
    payment_id: Optional[str] = Field(None, description="Unique identifier for the payment from the gateway.")
    user_intent: Optional[str] = Field(None, description="Natural language intent expressed by the user (Required for agent transactions).")
    cart: Optional[List[CartItem]] = Field(None, description="List of items in the shopping cart (Required for agent transactions).")
    agent_context: Optional[AgentContext] = Field(None, description="Contextual details about the AI agent (Required for agent transactions).")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "transaction": {
                        "amount": 250.50,
                        "is_international": False,
                        "transaction_count_1h": 1,
                        "transaction_count_24h": 2
                    },
                    "source": "AGENT_MCP",
                    "payment_id": "pay_xyz123",
                    "user_intent": "Please buy a high-quality mechanical keyboard under $300.",
                    "cart": [
                        {"name": "Keychron Q1 Pro", "price": 199.00, "quantity": 1, "category": "electronics"}
                    ],
                    "agent_context": {
                        "agent_id": "agent_alpha_01",
                        "protocol": "MCP",
                        "session_id": "sess_987654"
                    }
                }
            ]
        }
    }

class RiskEvaluationResponse(BaseModel):
    """The core POST /v1/risk/evaluate response body from the PRD."""
    decision: ActionType = Field(..., description="Final decision from the risk kernel (RELEASE, HOLD, or REFUSE).")
    risk_score: float = Field(..., description="Calculated risk probability score (0.0 to 1.0).")
    intent_alignment: Optional[float] = Field(None, description="Semantic alignment score between user intent and cart (for agents).")
    prediction_set: List[str] = Field(..., description="Conformal prediction set bounding the true label with mathematical guarantees.")
    reason_codes: List[str] = Field(..., description="List of codes explaining the primary factors for the decision.")
    audit_id: str = Field(..., description="Unique ID for this evaluation trace in the audit logs.")
    hold_expires_at: Optional[datetime] = Field(None, description="Timestamp when the escrow hold will automatically expire (if decision is HOLD).")

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
