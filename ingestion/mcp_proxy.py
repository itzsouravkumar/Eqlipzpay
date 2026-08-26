from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from schemas import Transaction, TransactionSource, TransactionStatus

router = APIRouter()

class MCPProxyRequest(BaseModel):
    agent_id: str
    tool_name: str
    parameters: dict

@router.post("/proxy")
async def handle_agent_call(request: MCPProxyRequest):
    """
    Proxies MCP tool calls from AI agents (like AP2 or UCP).
    This endpoint intercepts the call, checks intent, runs the risk engine, 
    and either holds, releases, or refuses the action.
    """
    if request.tool_name == "capture_payment":
        payment_id = request.parameters.get("payment_id")
        amount = request.parameters.get("amount")
        
        if not payment_id or not amount:
            raise HTTPException(status_code=400, detail="Missing payment_id or amount")

        # Create Transaction record
        transaction = Transaction(
            payment_id=payment_id,
            amount=amount,
            source=TransactionSource.AGENT_MCP,
            status=TransactionStatus.AUTHORIZED
        )
        
        # TODO: Pass to Semantic Entailment Engine & Conformal Risk Engine
        # If safe -> forward to actual Razorpay MCP server
        # If risky -> generate a Hold
        # If fraud -> Refuse
        
        return {
            "status": "pending", 
            "message": f"Action intercepted for risk analysis: {payment_id}"
        }
        
    return {"status": "ignored", "message": "Unhandled tool"}
