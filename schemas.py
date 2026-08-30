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
    STEP_UP = "STEP_UP"
    PARTIAL_RESERVE = "PARTIAL_RESERVE"

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


class RiskDecision(BaseModel):
    transaction_id: str
    prediction_set: List[str]
    confidence: float
    action: ActionType
    reason_codes: List[str]


# ──────────────────────────────────────────────
# EqlipZ Pay 2.0 Engine Models
# ──────────────────────────────────────────────

class AgentRiskBudget(BaseModel):
    daily_limit: int
    transaction_limit: int
    allowed_categories: List[str] = []
    allowed_regions: List[str] = []
    max_merchant_risk: str = "MEDIUM"

class ExposurePolicy(BaseModel):
    reserve_percent: int = 0
    hold_duration_hours: int = 0
    step_up_required: bool = False
    review_required: bool = False

class IntentContract(BaseModel):
    category: Optional[str] = None
    max_amount: Optional[int] = None
    currency: str = "INR"
    allowed_brands: List[str] = []
    size: Optional[str] = None
    destination: Optional[str] = None
    expiry: Optional[datetime] = None

class ContextualTrust(BaseModel):
    category: str
    amount_range: str
    risk_band: str

class TrustCredential(BaseModel):
    entity_id: str
    risk_band: str
    contexts: List[ContextualTrust] = []
    success_count: int = 0
    dispute_count: int = 0
    fraud_count: int = 0
    credential_hash: str
    version: str = "1"

class EvidenceCapsule(BaseModel):
    transaction_id: str
    intent_hash: str
    mandate_hash: str
    risk_policy_version: str
    prediction_set: List[str]
    decision: str
    settlement_action: str
    review_verdict: Optional[str] = None
    outcome_hash: Optional[str] = None
    previous_hash: Optional[str] = None


# ──────────────────────────────────────────────
# API Request / Response Models
# ──────────────────────────────────────────────

class CartItem(BaseModel):
    name: str = Field(..., description="Name of the product or service being purchased.")
    price: float = Field(..., description="Price per unit of the item.")
    quantity: int = Field(1, description="Number of units purchased.")
    category: Optional[str] = Field(None, description="Product category (e.g., 'electronics', 'software').")
    brand: Optional[str] = Field(None, description="Brand of the product.")
    destination: Optional[str] = Field(None, description="Delivery destination.")

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
    merchant_id: Optional[str] = Field(None, description="Merchant identifier.")
    transaction_count_1h: Optional[int] = Field(0, description="Count of transactions in the last hour.")
    transaction_count_24h: Optional[int] = Field(0, description="Count of transactions in the last 24 hours.")
    # Additional raw features can be passed through
    extra_features: Optional[Dict[str, Any]] = Field(None, description="Any additional dynamic features for the risk model.")

class RiskEvaluationRequest(BaseModel):
    """The core POST /v1/risk/evaluate request body."""
    transaction: TransactionFeatures = Field(..., description="Detailed features of the transaction to be evaluated.")
    source: TransactionSource = Field(TransactionSource.HUMAN, description="Origin of the transaction (Human vs AI Agent).")
    payment_id: Optional[str] = Field(None, description="Unique identifier for the payment from the gateway.")
    user_intent: Optional[str] = Field(None, description="Natural language intent expressed by the user (Required for agent transactions).")
    cart: Optional[List[CartItem]] = Field(None, description="List of items in the shopping cart (Required for agent transactions).")
    agent_context: Optional[AgentContext] = Field(None, description="Contextual details about the AI agent (Required for agent transactions).")

class RiskComponent(BaseModel):
    fraud: float
    intent: float
    graph: float
    uncertainty: float

class ExposureComponent(BaseModel):
    gross: float
    estimated_loss: float

class RiskEvaluationResponse(BaseModel):
    """The core POST /v1/risk/evaluate response body."""
    decision: ActionType = Field(..., description="Final policy decision from the control plane.")
    risk: RiskComponent = Field(..., description="Disaggregated risk components.")
    exposure: ExposureComponent = Field(..., description="Financial exposure calculation.")
    policy: ExposurePolicy = Field(..., description="Risk-adaptive exposure policy applied.")
    reason_codes: List[str] = Field(..., description="List of codes explaining the primary factors for the decision.")

class IntentVerifyRequest(BaseModel):
    intent: IntentContract
    cart: CartItem

class IntentVerifyResponse(BaseModel):
    valid: bool
    violations: List[str]
    semantic_score: float
    constraint_score: float

class PolicySimulateRequest(BaseModel):
    transaction: TransactionFeatures
    agent_context: Optional[AgentContext] = None
    policy_version: str = "latest"

class PolicySimulateResponse(BaseModel):
    decision: ActionType
    counterfactuals: Dict[str, str]

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
