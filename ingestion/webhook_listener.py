import hmac
import hashlib
import os
from fastapi import APIRouter, Request, HTTPException, Header
from schemas import Transaction, TransactionSource, TransactionStatus

router = APIRouter()

# In a real app, this would be loaded from env or config file
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "dummy_secret_for_testing")

# Simple in-memory set to ensure idempotency across retries
processed_payments = set()

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verifies the Razorpay webhook signature."""
    expected_signature = hmac.new(
        secret.encode(), 
        payload, 
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@router.post("/razorpay")
async def receive_webhook(request: Request, x_razorpay_signature: str = Header(None)):
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")

    payload = await request.body()
    
    if not verify_signature(payload, x_razorpay_signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = await request.json()
    
    # Process the event, assuming it's a payment authorized event
    if data.get("event") == "payment.authorized":
        payment_id = data["payload"]["payment"]["entity"]["id"]
        amount = data["payload"]["payment"]["entity"]["amount"]

        # 1. Check Idempotency
        if payment_id in processed_payments:
            return {"status": "success", "message": "Already processed"}
            
        # 2. Mark as processing/processed
        processed_payments.add(payment_id)
        
        # 3. Create Transaction record
        transaction = Transaction(
            payment_id=payment_id,
            amount=amount,
            source=TransactionSource.HUMAN,  # Can determine source via metadata if agent
            status=TransactionStatus.AUTHORIZED
        )
        
        # 4. Send transaction through the Risk Kernel
        conformal_engine = request.app.state.conformal_engine
        decision_router = request.app.state.decision_router
        
        # Build features from webhook payload
        features = {
            "payment_id": payment_id,
            "amount": amount / 100,  # Razorpay sends amount in paise
            "TransactionAmt": amount / 100,
        }
        
        # Extract extra features from webhook payload if available
        entity = data["payload"]["payment"]["entity"]
        if entity.get("international"):
            features["is_international"] = True
        if entity.get("card"):
            features["card_type"] = entity["card"].get("type", "")
        
        # Score through conformal engine
        risk_decision = conformal_engine.score(features)
        
        # Route through decision router (HUMAN path: conformal only)
        result = decision_router.route(
            risk_decision=risk_decision,
            intent_result=None,  # No intent check for human transactions
            source=TransactionSource.HUMAN,
            amount=amount / 100,
            payment_id=payment_id,
        )
        
        return {
            "status": "success",
            "message": "Webhook processed through risk kernel",
            "decision": result["action"].value,
            "audit_id": result["audit_id"],
            "prediction_set": result["prediction_set"],
        }
        
    return {"status": "ignored", "message": "Unhandled event type"}
