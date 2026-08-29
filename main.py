import logging
import yaml
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from ingestion.webhook_listener import router as webhook_router
from ingestion.mcp_proxy import router as mcp_proxy_router
from risk_kernel.conformal_engine import ConformalRiskEngine
from risk_kernel.semantic_engine import SemanticEntailmentEngine
from risk_kernel.decision_router import DecisionRouter
from schemas import (
    RiskEvaluationRequest, RiskEvaluationResponse,
    RiskStats, ActionType, TransactionSource,
)

from actions.route_transfer import RouteTransferClient
from actions.disputes_client import DisputesClient
from actions.refund_client import RefundClient
from flywheel.calibration_job import CalibrationJob
from flywheel.trust_passport import TrustPassportService
from sweeper.reconcile_cron import ReconcileSweeper
import asyncio

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("eqlipz")

# ──────────────────────────────────────────────
# Load config
# ──────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config" / "thresholds.yaml"

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return {
            "alpha": 0.10,
            "hold_max_hours": 48,
            "intent_alignment_threshold": 0.65,
            "intent_mismatch_threshold": 0.35,
            "agent_hold_bias": 0.1,
        }

config = load_config()

# ──────────────────────────────────────────────
# Initialize Risk Kernel Engines (singletons)
# ──────────────────────────────────────────────

conformal_engine = ConformalRiskEngine(alpha=config.get("alpha", 0.10))

semantic_engine = SemanticEntailmentEngine(
    alignment_threshold=config.get("intent_alignment_threshold", 0.65),
    mismatch_threshold=config.get("intent_mismatch_threshold", 0.35),
)

decision_router = DecisionRouter(
    hold_max_hours=config.get("hold_max_hours", 48),
    agent_hold_bias=config.get("agent_hold_bias", 0.1),
)

# ──────────────────────────────────────────────
# Initialize Day 3 Modules (Actions, Flywheel, Sweeper)
# ──────────────────────────────────────────────

route_transfer = RouteTransferClient()
disputes_client = DisputesClient()
refund_client = RefundClient()

calibration_job = CalibrationJob(
    target_coverage=config.get("target_coverage", 0.90),
    recalibration_window_hours=24
)
# Connect calibration to conformal engine for live threshold updates
calibration_job.set_conformal_engine(conformal_engine)

trust_passport = TrustPassportService()
reconcile_sweeper = ReconcileSweeper(interval_seconds=900)

# Wire sweeper callback for auto-released holds
reconcile_sweeper.on_hold_released = lambda transfer_id, payment_id: route_transfer.modify_hold(transfer_id, release=True)

# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

description = """
<div style="font-family: 'Outfit', sans-serif;">
  <p><strong>EqlipZ Pay API</strong> provides a robust <strong>Trust Layer for Payments made by Humans and AI Agents.</strong></p>
  
  <h3>Features</h3>
  <ul>
    <li><strong>Conformal Risk Engine</strong>: Mathematically bounded risk evaluation using conformal prediction.</li>
    <li><strong>Semantic Entailment</strong>: Verifies agent intents against transaction context to prevent unauthorized rogue AI purchases.</li>
    <li><strong>Smart Escrow</strong>: Holds ambiguous transactions securely for up to 48 hours instead of outright refusing them.</li>
    <li><strong>Continuous Calibration</strong>: Learns dynamically from dispute outcomes to auto-adjust risk thresholds.</li>
  </ul>

  <h3>Testing Playground</h3>
  <p>You can use the <strong>Try it out</strong> button on any endpoint below to test the API directly from your browser! The parameters and request bodies are pre-filled with detailed examples to help you explore the API capabilities.</p>
</div>
"""

app = FastAPI(
    title="EqlipZ Pay API", 
    description=description,
    version="5.0.0",
    docs_url=None,
    redoc_url=None,
    contact={
        "name": "EqlipZ Engineering",
        "url": "https://github.com/itzsouravkumar/Eqlipzpay",
    }
)

app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")

# Share engine instances with routers via app.state
app.state.conformal_engine = conformal_engine
app.state.semantic_engine = semantic_engine
app.state.decision_router = decision_router
app.state.route_transfer = route_transfer
app.state.disputes_client = disputes_client
app.state.refund_client = refund_client
app.state.calibration_job = calibration_job
app.state.trust_passport = trust_passport

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(reconcile_sweeper.start())
    
    # Dynamically determine the port for accurate logging
    import sys, os
    port = os.getenv("PORT", "8000")
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = sys.argv[i+1]
            break

    # Log helpful URLs to the terminal
    logger.info("EqlipZ Pay running locally")
    logger.info(f"Dashboard: http://127.0.0.1:{port}/dashboard")
    logger.info(f"API Docs (Swagger): http://127.0.0.1:{port}/docs")

@app.on_event("shutdown")
def shutdown_event():
    reconcile_sweeper.stop()

app.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(mcp_proxy_router, prefix="/mcp", tags=["MCP Proxy"])


# ──────────────────────────────────────────────
# Layer 1: The EqlipZ Risk API (core product)
# ──────────────────────────────────────────────

@app.post("/v1/risk/evaluate", response_model=RiskEvaluationResponse, tags=["Risk API"])
async def evaluate_risk(request: RiskEvaluationRequest):
    """
    Evaluates a digital transaction and returns a mathematically calibrated decision using EqlipZ Pay's Risk Kernel.

    ## Syntax
    `POST /v1/risk/evaluate`

    ### Parameters (Request Body)
    - `transaction` **(Required)**: An object containing all numerical and categorical features of the current transaction.
    - `source` *(Optional)*: Specifies the origin. Defaults to `HUMAN`. Valid values: `HUMAN`, `AGENT_MCP`, `AGENT_AP2`, `AGENT_UCP`.
    - `payment_id` *(Optional)*: The unique gateway identifier for the transaction.
    - `user_intent` *(Optional)*: The raw natural language instruction provided by the human user. **Required** if `source` is an AI agent.
    - `cart` *(Optional)*: An array of items in the shopping cart. **Required** if `source` is an AI agent.
    - `agent_context` *(Optional)*: Metadata describing the AI Agent executing the transaction.

    ## Return value
    Returns a JSON object matching the `RiskEvaluationResponse` schema.
    - **`decision`**: The outcome action (`RELEASE`, `REFUSE`, or `HOLD`).
    - **`risk_score`**: Float between 0.0 and 1.0 representing raw fraud probability.
    - **`prediction_set`**: A Conformal Prediction array containing mathematically guaranteed possible outcomes.
    - **`intent_alignment`**: The semantic alignment score between the user's intent and the agent's cart (Agent transactions only).

    ## Exceptions / Status Codes
    - **`200 OK`**: The transaction was successfully evaluated.
    - **`422 Unprocessable Entity`**: The request payload was missing required fields or incorrectly formatted.

    ## Examples

    ### 1. Evaluating a Human Transaction
    ```json
    {
      "transaction": {
        "amount": 45.00,
        "is_international": false
      },
      "source": "HUMAN"
    }
    ```

    ### 2. Evaluating an Agent Transaction
    ```json
    {
      "transaction": {
        "amount": 250.50
      },
      "source": "AGENT_MCP",
      "user_intent": "Please buy a high-quality mechanical keyboard under $300.",
      "cart": [
        {"name": "Keychron Q1 Pro", "price": 199.00, "quantity": 1}
      ]
    }
    ```

    ## Specifications
    This endpoint utilizes **Conformal Risk Prediction** to bound the False Positive Rate precisely to the configured `alpha` (default: 10%). For agent transactions, it routes the `cart` and `user_intent` through the **Semantic Entailment Engine** to guarantee goal alignment.
    """
    # Build features dict for the conformal engine
    features = {
        "payment_id": request.payment_id or "api-eval",
        "amount": request.transaction.amount,
        "TransactionAmt": request.transaction.amount,
        "is_international": request.transaction.is_international,
        "transaction_count_1h": request.transaction.transaction_count_1h or 0,
        "transaction_count_24h": request.transaction.transaction_count_24h or 0,
    }
    
    # Add extra features if provided
    if request.transaction.extra_features:
        features.update(request.transaction.extra_features)
    
    # ── Step 1: Conformal Risk Engine ──
    risk_decision = conformal_engine.score(features)
    
    # ── Step 2: Semantic Engine (agent transactions only) ──
    intent_result = None
    is_agent = request.source in (
        TransactionSource.AGENT_MCP,
        TransactionSource.AGENT_AP2,
        TransactionSource.AGENT_UCP,
    )
    
    if is_agent and request.user_intent and request.cart:
        cart_dicts = [item.model_dump() for item in request.cart]
        agent_ctx = request.agent_context.model_dump() if request.agent_context else None
        intent_result = semantic_engine.check_alignment(
            user_intent=request.user_intent,
            cart_items=cart_dicts,
            agent_context=agent_ctx,
        )
    
    # ── Step 3: Decision Router ──
    result = decision_router.route(
        risk_decision=risk_decision,
        intent_result=intent_result,
        source=request.source,
        amount=request.transaction.amount,
        payment_id=request.payment_id or "api-eval",
    )
    
    # ── Step 4: Actions Layer Execution ──
    payment_id = request.payment_id or f"pay_{result['audit_id'][:12]}"
    
    if result["action"] == ActionType.RELEASE.value:
        route_transfer.create_transfer(
            payment_id=payment_id,
            amount=int(request.transaction.amount * 100), # in paise
            hold=False
        )
    elif result["action"] == ActionType.HOLD.value:
        transfer = route_transfer.create_transfer(
            payment_id=payment_id,
            amount=int(request.transaction.amount * 100),
            hold=True,
            hold_until=result["hold_expires_at"]
        )
        if transfer.get("transfer_id"):
            reconcile_sweeper.track_hold(payment_id, transfer["transfer_id"], result["hold_expires_at"])
    elif result["action"] == ActionType.REFUSE.value:
        refund_client.create_refund(
            payment_id=payment_id,
            reason="fraud_detected"
        )
    
    return RiskEvaluationResponse(
        decision=result["action"],
        risk_score=result["risk_score"],
        intent_alignment=result.get("intent_alignment"),
        prediction_set=result["prediction_set"],
        reason_codes=result["reason_codes"],
        audit_id=result["audit_id"],
        hold_expires_at=result.get("hold_expires_at"),
    )


@app.get("/v1/risk/stats", response_model=RiskStats, tags=["Risk API"])
async def get_risk_stats():
    """
    Retrieves global coverage metrics and decision statistics for the EqlipZ Pay Risk Kernel.

    ## Syntax
    `GET /v1/risk/stats`

    ### Parameters
    *This endpoint takes no parameters.*

    ## Return value
    Returns a JSON object containing the following aggregates:
    - **`total_transactions`**: The absolute number of transactions processed.
    - **`total_released`**: Number of transactions immediately approved.
    - **`total_refused`**: Number of transactions immediately declined.
    - **`total_held`**: Number of transactions routed to smart escrow.
    - **`agents_checked`**: Number of AI agent intents semantically validated.
    - **`fraud_prevented_amount`**: Total value of fraudulent transactions blocked.
    - **`conformal_coverage`**: The empirical coverage rate achieved by the conformal predictor.
    - **`false_positive_cost`**: The cumulative financial penalty incurred by false positives.

    ## Examples

    ### Successful Response
    ```json
    {
      "total_transactions": 1420,
      "total_released": 1305,
      "total_refused": 42,
      "total_held": 73,
      "agents_checked": 215,
      "fraud_prevented_amount": 42500.0,
      "conformal_coverage": 0.902,
      "false_positive_cost": 150.0
    }
    ```
    """
    conformal_stats = conformal_engine.get_coverage_stats()
    router_stats = decision_router.get_stats()
    semantic_stats = semantic_engine.get_stats()
    calibration_stats = calibration_job.get_stats()
    
    return RiskStats(
        total_transactions=router_stats["total_routed"],
        total_released=router_stats["release"],
        total_refused=router_stats["refuse"],
        total_held=router_stats["hold"],
        agents_checked=semantic_stats["total_checked"],
        fraud_prevented_amount=router_stats["fraud_prevented_amount"],
        conformal_coverage=conformal_stats["empirical_coverage"],
        false_positive_cost=calibration_stats.get("fp_cost", 0.0),
    )


# ──────────────────────────────────────────────
# Day 3: Actions & Flywheel APIs
# ──────────────────────────────────────────────

from pydantic import BaseModel

class HoldResolveRequest(BaseModel):
    transfer_id: str
    action: str  # "release" or "refund"
    vendor_id: str

@app.post("/v1/actions/hold/resolve", tags=["Actions"])
async def resolve_hold(req: HoldResolveRequest):
    """
    Manually resolves a pending smart escrow hold, triggering the Day 3/Day 4 continuous calibration feedback loop.

    ## Syntax
    `POST /v1/actions/hold/resolve`

    ### Parameters (Request Body)
    - `transfer_id` **(Required)**: The unique ID of the transfer currently held in escrow.
    - `action` **(Required)**: The resolution action to take. Must be `"release"` (transaction was benign) or `"refund"` (transaction was fraud).
    - `vendor_id` **(Required)**: The ID of the merchant or vendor associated with the hold.

    ## Return value
    Returns a JSON object confirming the resolution.
    - **`status`**: Should always be `"resolved"`.
    - **`action`**: Echos back the action taken (`"release"` or `"refund"`).

    ## Exceptions / Status Codes
    - **`200 OK`**: The hold was successfully resolved and fed back into the calibration engine.
    - **`422 Unprocessable Entity`**: The request payload was invalid.

    ## Specifications
    When a hold is resolved, the system mathematically updates the `CalibrationJob`. If released, it registers a `BENIGN_CONFIRMED` event. If refunded, it registers a `FRAUD_CONFIRMED` event. This allows the conformal thresholds to adapt dynamically over time without manual retraining.
    """
    # Look up payment_id from route_transfer (simplified for now, ideally in DB)
    # But since we just need payment_id, let's assume transfer_id starts with trf_ and payment_id can be passed, 
    # or we just try to find it in the audit log.
    # For now, let's search audit log by something, or just pass a generic ID.
    
    # Actually, we can fetch all audit entries and find the one that resulted in HOLD and matched this.
    # Let's skip payment_id exact match if not easily available, or just mock it.
    
    if req.action == "release":
        route_transfer.modify_hold(req.transfer_id, release=True)
        trust_passport.issue_credential(req.vendor_id, "cleared_hold")
        
        # A hold that is manually released means the transaction was BENIGN.
        calibration_job.ingest_outcome(
            payment_id=f"hold_{req.transfer_id}",
            our_prediction="HOLD",
            ground_truth="BENIGN_CONFIRMED",
            amount=0.0,
            source="hold_resolution"
        )
    else:
        # A hold that is manualy refunded means the transaction was FRAUD.
        calibration_job.ingest_outcome(
            payment_id=f"hold_{req.transfer_id}",
            our_prediction="HOLD",
            ground_truth="FRAUD_CONFIRMED",
            amount=0.0,
            source="hold_resolution"
        )
        
    reconcile_sweeper.resolve_hold(req.transfer_id)
    return {"status": "resolved", "action": req.action}

class DisputeWebhookPayload(BaseModel):
    dispute_id: str
    payment_id: str
    amount: float
    result: str # "won", "lost", "accepted"
    vendor_id: str

@app.post("/v1/disputes/webhook", tags=["Flywheel"])
async def dispute_webhook(payload: DisputeWebhookPayload):
    """Webhook for dispute outcome ingestion (Day 3 + Day 4 Calibration)."""
    outcome = disputes_client.on_dispute_resolved(
        dispute_id=payload.dispute_id,
        result=payload.result,
        payment_id=payload.payment_id,
        amount=payload.amount,
    )
    
    if payload.result in ("lost", "accepted"):
        trust_passport.issue_credential(payload.vendor_id, "dispute_lost")
        
    # Feed into calibration loop
    audit_entry = decision_router.get_audit_by_payment(payload.payment_id)
    our_prediction = audit_entry["action"] if audit_entry else "RELEASE"
    
    calibration_job.ingest_outcome(
        payment_id=payload.payment_id,
        our_prediction=our_prediction,
        ground_truth=outcome["ground_truth"],
        amount=payload.amount,
        source="dispute"
    )
    
    return {"status": "ingested"}

@app.get("/v1/trust/{entity_id}", tags=["Flywheel"])
async def get_trust_passport(entity_id: str):
    """Retrieve the trust passport for a vendor (Day 3)."""
    return trust_passport.check_trust(entity_id)


# ──────────────────────────────────────────────
# Dashboard API (feeds the web control plane)
# ──────────────────────────────────────────────

@app.get("/api/transactions", tags=["Dashboard"])
async def get_transactions():
    """
    Returns the recent transaction ledger for the EqlipZ Pay dashboard.
    
    ## Overview
    Fetches the recent transaction ledger for the web dashboard. The Decision Router stores a volatile in-memory log of every transaction evaluated by the Risk Engine. This endpoint paginates and retrieves that log for the real-time Transactions feed.
    
    ## Query Parameters
    - `filter` *(optional)*: A string to filter the ledger by decision outcome. Valid values are `all`, `RELEASE`, `HOLD`, or `REFUSE`. If omitted, defaults to `all`.

    ## Response Payload Details
    Returns a JSON array of transaction objects containing exact timestamps and reason codes.
    
    ```json
    [
      {
        "payment_id": "pay_OXYZ123456",
        "amount": 250.50,
        "source": "AGENT_MCP",
        "decision": "HOLD",
        "reason_codes": ["unusual_transaction", "intent_mismatch"],
        "timestamp": "2026-08-29T10:00:00Z"
      }
    ]
    ```
    """
    return decision_router.get_audit_log(limit=50)


@app.get("/api/risk-log", tags=["Dashboard"])
async def get_risk_log():
    """
    Returns a stream of internal logs detailing the Risk Engine's decision-making process.
    
    ## Overview
    Provides a real-time stream of diagnostic logs directly from the Risk Kernel's internal decision tree. This is highly useful for debugging why a specific transaction was held or refused.
    
    ## Log Contents
    - **Semantic Details:** Outputs the LLM reasoning if an agent's cart violates the user's instructions (e.g. *"Detected 0.42 intent mismatch due to budget violation"*).
    - **Threshold Boundaries:** Logs the exact Conformal Alpha value and the resulting prediction set (e.g. *"Set [BENIGN, FRAUD] resulted in HOLD"*).
    - **Fallback Mechanics:** Logs warnings when features are missing and the system safely defaults to mean imputation.
    """
    return decision_router.get_risk_log(limit=20)


@app.get("/api/stats", tags=["Dashboard"])
async def get_dashboard_stats():
    """
    Returns high-level summary stats for the dashboard scorecards.
    
    ## Description
    Aggregates data across the Conformal Risk Engine, Semantic Engine, and Decision Router.
    It calculates the total value of fraud prevented, the number of escrow holds active, and the current empirical coverage of the conformal predictors.
    """
    router_stats = decision_router.get_stats()
    conformal_stats = conformal_engine.get_coverage_stats()
    semantic_stats = semantic_engine.get_stats()
    
    # Try to load evaluation report
    coverage = conformal_stats["empirical_coverage"]
    try:
        import json
        with open(Path(__file__).parent / "data" / "models" / "evaluation_results.json", "r") as f:
            eval_data = json.load(f)
            coverage = float(eval_data["metrics"]["conformal_coverage"].strip('%')) / 100.0
    except Exception:
        pass

    return {
        "total_transactions": router_stats["total_routed"],
        "agents_checked": semantic_stats["total_checked"],
        "escrow_holds": router_stats["hold"],
        "fraud_prevented": router_stats["fraud_prevented_amount"],
        "conformal_coverage": coverage,
        "model_loaded": conformal_stats["model_loaded"],
        "hold_rate": conformal_stats["hold_rate"],
    }

@app.get("/api/evaluation", tags=["Dashboard"])
async def get_evaluation():
    """
    Returns the pre-calculated PRD evaluation report metrics.
    
    ## Overview
    Returns the strict mathematical evaluation metrics calculated during the model's offline calibration phase. EqlipZ Pay generates a static `evaluation_results.json` artifact when trained against historical datasets (e.g. ULB Credit Card Fraud).
    
    ## Key Metrics Returned
    - **Empirical Coverage:** The actual percentage of transactions where the true label fell within the generated prediction set (should hover near the 90% target).
    - **Precision & Recall:** Standard binary classification metrics outlining the model's accuracy on the hold-out test set.
    - **False Positive Cost:** A simulated financial impact metric showing how much money would have been lost if the system forcefully refused transactions instead of using smart escrow holds.
    """
    try:
        import json
        with open(Path(__file__).parent / "data" / "models" / "evaluation_results.json", "r") as f:
            return json.load(f)
    except Exception:
        return {"error": "Evaluation report not found. Run data/evaluation_report.py"}

@app.get("/api/config", tags=["Dashboard"])
async def get_dashboard_config():
    """
    Returns the current Risk Engine thresholds and systemic configurations.
    
    ## Description
    Outputs the global `config` object which includes maximum hold windows, strict AI agent source validation flags, and conformal alpha limits.
    """
    return config


# ──────────────────────────────────────────────
# Root + Docs
# ──────────────────────────────────────────────

@app.get("/")
def read_root():
    return {
        "status": "operational",
        "service": "EqlipZ Pay",
        "version": "5.0.0",
        "model_loaded": conformal_engine.is_loaded,
        "engines": {
            "conformal": "active",
            "semantic": "active",
            "router": "active",
            "flywheel": "active",
            "sweeper": "active"
        },
    }


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(req: Request):
    html_content = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    ).body.decode("utf-8")
    
    custom_css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&display=swap');
        
        body {
            background-color: #f4f4f4 !important;
        }
        
        .swagger-ui, .swagger-ui *, .swagger-ui button, .swagger-ui input, .swagger-ui select {
            font-family: 'Outfit', sans-serif !important;
        }
        
        .swagger-ui .opblock, 
        .swagger-ui .models,
        .swagger-ui .model-container,
        .swagger-ui .parameters-col_description input,
        .swagger-ui .btn,
        .swagger-ui .dialog-ux .modal-ux,
        .swagger-ui .dialog-ux .modal-ux-header,
        .swagger-ui pre,
        .swagger-ui code,
        .swagger-ui .highlight-code,
        .swagger-ui .model-box,
        .swagger-ui .model {
            border-radius: 0px !important;
        }

        .swagger-ui .opblock {
            border: none !important;
            background-image: 
                repeating-linear-gradient(0deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(90deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(180deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(270deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px) !important;
            background-size: 1px 100%, 100% 1px, 1px 100%, 100% 1px !important;
            background-position: 0 0, 0 0, 100% 0, 0 100% !important;
            background-repeat: no-repeat !important;
            box-shadow: none !important;
            background-color: #ffffff !important;
            margin-bottom: 24px !important;
        }
        
        .swagger-ui .models {
            border: none !important;
            background-image: 
                repeating-linear-gradient(0deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(90deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(180deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(270deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px) !important;
            background-size: 1px 100%, 100% 1px, 1px 100%, 100% 1px !important;
            background-position: 0 0, 0 0, 100% 0, 0 100% !important;
            background-repeat: no-repeat !important;
            box-shadow: none !important;
            background-color: #ffffff !important;
        }
        
        .swagger-ui .opblock .opblock-summary {
            border-bottom: 1px dashed #c0c0c0 !important;
            padding: 8px 16px !important; /* Tighter premium padding */
        }
        
        .swagger-ui .opblock .opblock-summary-method {
            padding: 4px 10px !important;
            font-size: 12px !important;
            min-width: 60px !important;
        }
        
        .swagger-ui .opblock .opblock-summary-path {
            font-size: 14px !important;
        }
        
        .swagger-ui section.models .model-container {
            background-color: transparent !important;
            padding: 12px 16px !important;
        }
        
        .swagger-ui section.models h4 {
            padding: 12px 16px !important;
            font-size: 14px !important;
            border-bottom: 1px dashed #c0c0c0 !important;
        }
        
        .swagger-ui section.models .model-container:hover,
        .swagger-ui .model-box:hover,
        .swagger-ui .model:hover {
            background-color: transparent !important;
            background: transparent !important;
        }
        
        .swagger-ui .model-box {
            border-radius: 0px !important;
        }

        .swagger-ui .info {
            margin: 24px 0 !important;
        }

        .swagger-ui .info .title {
            font-size: 28px !important;
            font-weight: 500 !important;
            letter-spacing: -0.5px !important;
            display: flex !important;
            align-items: flex-end !important;
            gap: 12px !important;
            flex-wrap: wrap !important;
        }
        
        .swagger-ui .info .title span {
            display: flex !important;
            align-items: flex-end !important;
            gap: 8px !important;
            margin: 0 0 4px 0 !important;
        }
        
        .swagger-ui .info .title pre, 
        .swagger-ui .info .title .version-stamp, 
        .swagger-ui .info .title .version,
        .swagger-ui pre.version,
        .swagger-ui .version-stamp {
            border-radius: 0px !important;
            margin: 0 !important;
            transform: none !important;
            vertical-align: bottom !important;
        }

        /* Enforce custom blue and complete black */
        .swagger-ui .opblock-summary-method {
            border-radius: 0 !important;
        }
        
        .swagger-ui .btn {
            border: 1px dashed #4348E8 !important;
            color: #4348E8 !important;
            box-shadow: none !important;
        }
        
        .swagger-ui .btn.execute {
            background-color: #4348E8 !important;
            color: #ffffff !important;
        }
        
        /* Hide scrollbar */
        * {
            -ms-overflow-style: none !important;
            scrollbar-width: none !important;
        }
        *::-webkit-scrollbar {
            display: none !important;
        }
        
        /* Full width and Light Fonts Enforcements */
        .swagger-ui .wrapper {
            max-width: 100% !important;
            padding: 0 48px !important;
        }
        
        .swagger-ui, .swagger-ui *, .swagger-ui p, .swagger-ui span, .swagger-ui div {
            font-weight: 300 !important;
        }
        
        .swagger-ui b, .swagger-ui strong, .swagger-ui h1, .swagger-ui h2, .swagger-ui h3, .swagger-ui h4, .swagger-ui h5, .swagger-ui .info .title {
            font-weight: 400 !important;
        }
        
        .swagger-ui .opblock .opblock-summary-method, .swagger-ui .btn {
            font-weight: 500 !important;
        }
        
        /* Custom Selectors */
        .swagger-ui select {
            -webkit-appearance: none !important;
            -moz-appearance: none !important;
            appearance: none !important;
            border-radius: 0px !important;
            border: 1px dashed #c0c0c0 !important;
            background-color: transparent !important;
            padding: 4px 24px 4px 8px !important;
            background-image: url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23444444%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: right 8px center !important;
            background-size: 8px auto !important;
            box-shadow: none !important;
            outline: none !important;
        }
        
        .swagger-ui select:focus {
            border: 1px dashed #4348E8 !important;
            outline: none !important;
            box-shadow: none !important;
        }
        
        .swagger-ui select option {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-radius: 0px !important;
            padding: 8px !important;
        }
        
        /* Copy to clipboard icon cleanup */
        .swagger-ui .copy-to-clipboard {
            background: transparent !important;
            border: none !important;
            border-radius: 0px !important;
            padding: 4px !important;
        }
        
        .swagger-ui .copy-to-clipboard svg {
            fill: #444444 !important;
        }
        
        /* Parameter Table Layout Fixes */
        .swagger-ui table.parameters {
            width: 100% !important;
            display: table !important;
        }
        
        .swagger-ui .parameters-col_name {
            width: 300px !important; /* Prevent text wrapping */
            vertical-align: top !important;
        }
        
        .swagger-ui .parameters-col_description {
            width: auto !important;
            vertical-align: top !important;
        }
        
        .swagger-ui .parameters-col_description input[type="text"] {
            width: 100% !important;
            max-width: 100% !important;
            border: 1px dashed #c0c0c0 !important;
            background: transparent !important;
        }
        
        .swagger-ui .parameters-col_description input[type="text"]:focus {
            border: 1px dashed #4348E8 !important;
            outline: none !important;
        }
        /* Custom JS Dropdown Styles */
        .custom-select-wrapper {
            position: relative;
            width: 100%;
            min-width: 160px;
            font-family: 'Outfit', sans-serif !important;
            font-weight: 300 !important;
        }
        
        .custom-select-display {
            background-color: transparent !important;
            border: 1px dashed #c0c0c0;
            padding: 6px 10px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 14px;
            color: #000000;
        }
        
        .custom-select-display.active {
            border-color: #4348E8;
        }
        
        .custom-select-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            width: 100%;
            background: #ffffff;
            border: 1px dashed #4348E8;
            border-top: none;
            z-index: 9999;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .custom-select-dropdown.show {
            display: block;
        }
        
        .custom-select-item {
            padding: 8px 10px;
            cursor: pointer;
            font-size: 14px;
            color: #000000;
            background: #ffffff;
            border-bottom: 1px dashed #e0e0e0;
        }
        
        .custom-select-item:last-child {
            border-bottom: none;
        }
        
        .custom-select-item:hover {
            background: #f4f4f4;
            color: #4348E8;
        }
        
        /* Ensure dropdowns aren't clipped by containers */
        .swagger-ui .opblock-body, .swagger-ui .responses-wrapper, .swagger-ui .responses-inner {
            overflow: visible !important;
        }
        
        /* Fix overlapping inline code blocks, avoiding highlight-code blocks */
        .swagger-ui p code, .swagger-ui li code, .swagger-ui table.parameters td code {
            padding: 2px 6px !important;
            margin: 0 4px !important;
            background-color: #f4f4f4 !important;
            display: inline-block !important;
            border-radius: 4px !important;
        }
        
        /* Enforce dark theme for syntax highlighted JSON blocks */
        .swagger-ui .highlight-code, .swagger-ui .model-box {
            background-color: #2b2b2b !important;
            border-radius: 4px !important;
        }
        
        .swagger-ui .highlight-code code, .swagger-ui .model-box code {
            background-color: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
            display: inline !important;
            color: #ffffff !important;
        }
    </style>
    """
    
    custom_js = """
    <script>
    document.addEventListener("DOMContentLoaded", () => {
        function setNativeValue(element, value) {
            const valueSetter = Object.getOwnPropertyDescriptor(element, 'value').set;
            const prototype = Object.getPrototypeOf(element);
            const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
            if (valueSetter && valueSetter !== prototypeValueSetter) {
                prototypeValueSetter.call(element, value);
            } else {
                valueSetter.call(element, value);
            }
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function customizeSelects() {
            document.querySelectorAll('.swagger-ui select:not(.customized)').forEach(select => {
                select.classList.add('customized');
                select.style.display = 'none';

                const wrapper = document.createElement('div');
                wrapper.className = 'custom-select-wrapper';
                select.parentNode.insertBefore(wrapper, select);
                wrapper.appendChild(select);

                const display = document.createElement('div');
                display.className = 'custom-select-display';
                display.innerHTML = `<span>${select.options[select.selectedIndex]?.text || ''}</span> <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
                wrapper.appendChild(display);

                const dropdown = document.createElement('div');
                dropdown.className = 'custom-select-dropdown';
                
                Array.from(select.options).forEach(option => {
                    const item = document.createElement('div');
                    item.className = 'custom-select-item';
                    item.textContent = option.text;
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        display.querySelector('span').textContent = option.text;
                        setNativeValue(select, option.value);
                        dropdown.classList.remove('show');
                        display.classList.remove('active');
                    });
                    dropdown.appendChild(item);
                });
                wrapper.appendChild(dropdown);

                display.addEventListener('click', (e) => {
                    e.stopPropagation();
                    document.querySelectorAll('.custom-select-dropdown.show').forEach(d => {
                        if (d !== dropdown) {
                            d.classList.remove('show');
                            d.previousElementSibling.classList.remove('active');
                        }
                    });
                    dropdown.classList.toggle('show');
                    display.classList.toggle('active');
                });
                
                select.addEventListener('change', () => {
                   display.querySelector('span').textContent = select.options[select.selectedIndex]?.text || '';
                });
            });
        }

        document.addEventListener('click', () => {
            document.querySelectorAll('.custom-select-dropdown.show').forEach(d => {
                d.classList.remove('show');
                d.previousElementSibling.classList.remove('active');
            });
        });

        const observer = new MutationObserver(() => { customizeSelects(); });
        observer.observe(document.body, { childList: true, subtree: true });
    });
    </script>
    """
    
    html_content = html_content.replace("</head>", f"{custom_css}{custom_js}</head>")
    return HTMLResponse(html_content)
