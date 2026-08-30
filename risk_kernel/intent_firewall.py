"""
EqlipZ Pay — Intent Firewall
========================================
Replaces Semantic Entailment Engine.
Applies deterministic constraints from the IntentContract first (e.g., max_amount, category).
Falls back to semantic LLM evaluation for ambiguous matching.
Returns an intent_risk score (0.0 to 1.0) and constraint evaluation details.
"""

import os
import re
import json
import logging
import math
from typing import Dict, List, Optional, Tuple
from collections import Counter
from pydantic import BaseModel

from schemas import IntentContract, CartItem, IntentAlignment

logger = logging.getLogger("eqlipz.intent_firewall")

try:
    import groq
except ImportError:
    groq = None


class IntentFirewall:
    def __init__(self):
        self.client = None
        if groq and os.environ.get("GROQ_API_KEY"):
            try:
                self.client = groq.Groq()
            except Exception as e:
                logger.error(f"[Intent Firewall] Failed to initialize Groq: {e}")
                
    def verify_intent(
        self,
        contract: IntentContract,
        cart: List[CartItem],
        raw_intent_string: Optional[str] = None
    ) -> Tuple[float, IntentAlignment, List[str]]:
        """
        Returns (intent_risk, alignment, reason_codes).
        intent_risk is 0.0 for perfect alignment, 1.0 for complete mismatch.
        """
        if not cart:
            return 1.0, IntentAlignment.MISMATCH, ["empty_cart"]

        reason_codes = []
        constraint_score = 1.0
        
        cart_total = sum(item.price * item.quantity for item in cart)
        
        # 1. Deterministic Checks against IntentContract
        if contract.max_amount is not None:
            if cart_total > contract.max_amount:
                constraint_score = 0.0
                reason_codes.append("budget_exceeded")
                
        if contract.category:
            for item in cart:
                if item.category and item.category.lower() != contract.category.lower():
                    # Simple deterministic category mismatch
                    constraint_score *= 0.5
                    if "category_mismatch" not in reason_codes:
                        reason_codes.append("category_mismatch")

        if contract.allowed_brands:
            allowed = [b.lower() for b in contract.allowed_brands]
            for item in cart:
                if item.brand and item.brand.lower() not in allowed:
                    constraint_score *= 0.5
                    if "brand_mismatch" not in reason_codes:
                        reason_codes.append("brand_mismatch")

        if contract.destination:
            for item in cart:
                if item.destination and contract.destination.lower() not in item.destination.lower():
                    constraint_score *= 0.5
                    if "destination_mismatch" not in reason_codes:
                        reason_codes.append("destination_mismatch")

        # 2. Injection Check
        injection_score = self._check_injection_markers([item.model_dump() for item in cart])
        if injection_score < 1.0:
            constraint_score = 0.0
            reason_codes.append("possible_injection")

        # 3. Fallback Semantic Check (if raw intent exists and deterministic checks didn't outright fail)
        semantic_score = 1.0
        if raw_intent_string and constraint_score > 0.0:
            if self.client:
                semantic_score = self._check_llm(raw_intent_string, [item.model_dump() for item in cart])
            else:
                semantic_score = self._check_text_similarity(raw_intent_string, [item.model_dump() for item in cart])
                
            if semantic_score < 0.3:
                reason_codes.append("semantic_mismatch")
                constraint_score *= semantic_score

        # Final Alignment
        alignment = IntentAlignment.AMBIGUOUS
        if constraint_score == 1.0 and semantic_score >= 0.7:
            alignment = IntentAlignment.ALIGNED
        elif constraint_score <= 0.3 or semantic_score <= 0.3:
            alignment = IntentAlignment.MISMATCH

        intent_risk = round(1.0 - constraint_score, 4)
        if alignment == IntentAlignment.AMBIGUOUS:
            intent_risk = max(intent_risk, 0.5)
            
        logger.info(f"[Intent Firewall] Risk: {intent_risk}, Alignment: {alignment.value}, Reasons: {reason_codes}")
        
        return intent_risk, alignment, reason_codes

    def _check_llm(self, user_intent: str, cart_items: List[Dict]) -> float:
        prompt = f"""
        Does this cart match the user intent perfectly? 
        User Intent: "{user_intent}"
        Cart Items: {json.dumps(cart_items, indent=2)}
        Output only a JSON object: {{"score": float between 0.0 and 1.0}}
        """
        try:
            res = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            val = json.loads(res.choices[0].message.content)
            return float(val.get("score", 0.5))
        except Exception as e:
            logger.error(f"[Intent Firewall] LLM fallback failed: {e}")
            return 0.5

    def _check_text_similarity(self, intent: str, cart_items: List[Dict]) -> float:
        # Basic word overlap
        intent_words = set(re.findall(r'\w+', intent.lower()))
        cart_texts = " ".join([f"{i.get('name', '')} {i.get('category', '')}" for i in cart_items]).lower()
        cart_words = set(re.findall(r'\w+', cart_texts))
        
        if not cart_words or not intent_words:
            return 0.5
            
        intersection = intent_words.intersection(cart_words)
        score = len(intersection) / float(len(cart_words))
        return min(1.0, score + 0.3)

    def _check_injection_markers(self, cart_items: List[Dict]) -> float:
        injection_patterns = [
            r"ignore\s+(previous|all|above)",
            r"system\s*prompt",
            r"you\s+are\s+now",
            r"disregard\s+(all|the)",
            r"new\s+instruction",
            r"override\s+(all|the)",
            r"<\s*script",
            r"javascript:",
            r"IMPORTANT:\s*ignore",
        ]
        for item in cart_items:
            item_name = item.get("name", "").lower()
            for p in injection_patterns:
                if re.search(p, item_name, re.IGNORECASE):
                    return 0.0
        return 1.0
