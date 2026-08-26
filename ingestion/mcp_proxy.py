from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from schemas import (
    Transaction, TransactionSource, TransactionStatus,
    CartItem, ActionType,
)

router = APIRouter()

class MCPProxyRequest(BaseModel):
    agent_id: str
    tool_name: str
    parameters: dict
    user_intent: Optional[str] = None
    cart: Optional[List[CartItem]] = None
    protocol: str = "MCP"  # MCP, AP2, UCP

@router.post("/proxy")
async def handle_agent_call(request: Request, proxy_req: MCPProxyRequest):
    """
    Proxies MCP tool calls from AI agents (like AP2 or UCP).
    This endpoint intercepts the call, checks intent, runs the risk engine, 
    and either holds, releases, or refuses the action.
    """
    if proxy_req.tool_name in ("capture_payment", "create_transfer", "create_instant_settlement"):
        payment_id = proxy_req.parameters.get("payment_id")
        amount = proxy_req.parameters.get("amount")
        
        if not payment_id or not amount:
            raise HTTPException(status_code=400, detail="Missing payment_id or amount")

        # Create Transaction record
        source_map = {
            "MCP": TransactionSource.AGENT_MCP,
            "AP2": TransactionSource.AGENT_AP2,
            "UCP": TransactionSource.AGENT_UCP,
        }
        source = source_map.get(proxy_req.protocol, TransactionSource.AGENT_MCP)
        
        transaction = Transaction(
            payment_id=payment_id,
            amount=amount,
            source=source,
            status=TransactionStatus.AUTHORIZED
        )
        
        # Get engine instances from app state
        conformal_engine = request.app.state.conformal_engine
        semantic_engine = request.app.state.semantic_engine
        decision_router = request.app.state.decision_router
        
        # ── Step 1: Conformal Risk Engine ──
        features = {
            "payment_id": payment_id,
            "amount": amount / 100 if amount > 1000 else amount,  # Handle paise vs rupees
            "TransactionAmt": amount / 100 if amount > 1000 else amount,
        }
        risk_decision = conformal_engine.score(features)
        
        # ── Step 2: Semantic Entailment Engine ──
        intent_result = None
        if proxy_req.user_intent and proxy_req.cart:
            cart_dicts = [item.model_dump() for item in proxy_req.cart]
            intent_result = semantic_engine.check_alignment(
                user_intent=proxy_req.user_intent,
                cart_items=cart_dicts,
                agent_context={"agent_id": proxy_req.agent_id, "protocol": proxy_req.protocol},
            )
        
        # ── Step 3: Decision Router ──
        result = decision_router.route(
            risk_decision=risk_decision,
            intent_result=intent_result,
            source=source,
            amount=amount / 100 if amount > 1000 else amount,
            payment_id=payment_id,
        )
        
        action = result["action"]
        
        # Build response based on decision
        response = {
            "status": "processed",
            "decision": action.value,
            "audit_id": result["audit_id"],
            "prediction_set": result["prediction_set"],
            "risk_score": result["risk_score"],
            "reason_codes": result["reason_codes"],
        }
        
        if intent_result:
            response["intent_alignment"] = result.get("intent_alignment")
        
        if action == ActionType.RELEASE:
            response["message"] = f"Action approved: {proxy_req.tool_name} for {payment_id}"
            response["forward_to_razorpay"] = True
        elif action == ActionType.HOLD:
            response["message"] = f"Action held for review: {payment_id}"
            response["hold_expires_at"] = result["hold_expires_at"].isoformat() if result.get("hold_expires_at") else None
            response["forward_to_razorpay"] = False
        elif action == ActionType.REFUSE:
            response["message"] = f"Action refused: {payment_id}"
            response["forward_to_razorpay"] = False
        
        return response
        
    return {"status": "ignored", "message": "Unhandled tool"}
