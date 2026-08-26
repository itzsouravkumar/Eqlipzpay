"""
EqlipZ Pay — Semantic Entailment Engine
========================================
Checks whether an AI agent's actual cart still matches what the
human originally asked for. This catches:

  1. Prompt injection: A malicious product description hijacks the agent
     into buying something entirely different.
  2. Budget drift: The agent's cart total exceeds the stated budget.
  3. Category mismatch: The agent buys items from wrong categories.
  4. Quantity anomalies: Unexpected quantities or items not mentioned.

For Day 2, this uses deterministic rule-based checks + TF-IDF cosine
similarity. An LLM-backed version can be swapped in on Day 4.

The engine is only invoked for AGENT transactions (MCP, AP2, UCP).
Human transactions skip this check entirely.
"""

import re
import logging
import math
from typing import Dict, List, Optional
from collections import Counter

from schemas import IntentAlignment

logger = logging.getLogger("eqlipz.semantic")


class SemanticEntailmentEngine:
    """
    Semantic Entailment Engine — verifies AI agent intent alignment.
    
    Given a user's stated intent and the agent's final cart, determines
    whether the purchase action is ALIGNED, AMBIGUOUS, or a MISMATCH.
    """
    
    def __init__(
        self,
        alignment_threshold: float = 0.65,
        mismatch_threshold: float = 0.35,
    ):
        self.alignment_threshold = alignment_threshold
        self.mismatch_threshold = mismatch_threshold
        
        # Runtime stats
        self._stats = {
            "total_checked": 0,
            "aligned": 0,
            "ambiguous": 0,
            "mismatch": 0,
        }
    
    def check_alignment(
        self,
        user_intent: str,
        cart_items: List[Dict],
        agent_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Check whether the agent's cart aligns with the user's stated intent.
        
        Args:
            user_intent: The user's original instruction (e.g., "Buy the cheapest 16GB laptop under Rs.80,000")
            cart_items: List of items the agent is trying to purchase
            agent_context: Optional metadata about the agent session
        
        Returns:
            Dict with:
              - alignment_score: float 0.0 to 1.0
              - alignment: IntentAlignment enum
              - reason_codes: List[str] explaining the assessment
              - details: Dict with individual check scores
        """
        if not user_intent or not cart_items:
            return {
                "alignment_score": 0.5,
                "alignment": IntentAlignment.AMBIGUOUS,
                "reason_codes": ["missing_intent_or_cart"],
                "details": {},
            }
        
        reason_codes = []
        scores = {}
        
        # ── Check 1: Budget compliance ──
        budget_score = self._check_budget(user_intent, cart_items)
        scores["budget_compliance"] = budget_score
        if budget_score < 0.3:
            reason_codes.append("budget_exceeded")
        
        # ── Check 2: Text similarity (TF-IDF cosine) ──
        similarity_score = self._check_text_similarity(user_intent, cart_items)
        scores["text_similarity"] = similarity_score
        if similarity_score < 0.3:
            reason_codes.append("intent_mismatch")
        
        # ── Check 3: Category alignment ──
        category_score = self._check_category(user_intent, cart_items)
        scores["category_alignment"] = category_score
        if category_score < 0.3:
            reason_codes.append("category_mismatch")
        
        # ── Check 4: Quantity reasonableness ──
        quantity_score = self._check_quantity(user_intent, cart_items)
        scores["quantity_check"] = quantity_score
        if quantity_score < 0.5:
            reason_codes.append("unusual_quantity")
        
        # ── Check 5: Suspicious patterns (injection markers) ──
        injection_score = self._check_injection_markers(cart_items)
        scores["injection_check"] = injection_score
        if injection_score < 0.5:
            reason_codes.append("possible_injection")
        
        # ── Combine scores ──
        # Weighted average: budget and injection are most critical
        weights = {
            "budget_compliance": 0.25,
            "text_similarity": 0.25,
            "category_alignment": 0.20,
            "quantity_check": 0.15,
            "injection_check": 0.15,
        }
        
        alignment_score = sum(
            scores[k] * weights[k] for k in weights
        )
        alignment_score = round(min(1.0, max(0.0, alignment_score)), 4)
        
        # Hard overrides: injection and severe budget violations force MISMATCH
        if injection_score == 0.0:
            alignment_score = min(alignment_score, 0.15)  # Hard cap on injection
        if budget_score == 0.0:
            alignment_score = min(alignment_score, 0.30)  # Hard cap on budget blowout
        
        # Map to discrete alignment level
        if alignment_score >= self.alignment_threshold:
            alignment = IntentAlignment.ALIGNED
            self._stats["aligned"] += 1
        elif alignment_score <= self.mismatch_threshold:
            alignment = IntentAlignment.MISMATCH
            self._stats["mismatch"] += 1
        else:
            alignment = IntentAlignment.AMBIGUOUS
            self._stats["ambiguous"] += 1
        
        self._stats["total_checked"] += 1
        
        logger.info(
            f"[Semantic Engine] alignment: {alignment_score:.2f} → {alignment.value} "
            f"reasons: {reason_codes}"
        )
        
        return {
            "alignment_score": alignment_score,
            "alignment": alignment,
            "reason_codes": reason_codes,
            "details": scores,
        }
    
    def _check_budget(self, intent: str, cart_items: List[Dict]) -> float:
        """
        Check if the cart total respects the budget stated in the intent.
        
        Extracts budget figures from intent text and compares against
        cart total. Returns 1.0 if compliant, degrades as overshoot grows.
        """
        # Extract monetary values from intent
        # Matches: Rs.80,000 / ₹80000 / Rs 80,000 / 80000 rupees / under 50k
        budget_patterns = [
            r"(?:under|below|max|budget|upto|up\s*to|within|less\s*than)\s*(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k)?",
            r"(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)\s*(k)?",
            r"([\d,]+(?:\.\d+)?)\s*(?:rupees|rs|inr)\s*(k)?",
        ]
        
        budgets = []
        intent_lower = intent.lower()
        for pattern in budget_patterns:
            matches = re.findall(pattern, intent_lower, re.IGNORECASE)
            for m in matches:
                try:
                    # m is a tuple: (number, optional_k)
                    val = float(m[0].replace(",", ""))
                    if len(m) > 1 and m[1].lower() == "k":
                        val *= 1000
                    budgets.append(val)
                except (ValueError, IndexError):
                    continue
        
        if not budgets:
            return 0.7  # No budget stated, mild neutral
        
        max_budget = max(budgets)
        cart_total = sum(
            item.get("price", 0) * item.get("quantity", 1) 
            for item in cart_items
        )
        
        if cart_total <= max_budget:
            return 1.0
        
        # Penalize proportionally to overshoot
        overshoot = (cart_total - max_budget) / max_budget
        return max(0.0, 1.0 - overshoot)
    
    def _check_text_similarity(self, intent: str, cart_items: List[Dict]) -> float:
        """
        Compute TF-IDF cosine similarity between intent and cart descriptions.
        
        This catches cases where the cart is completely unrelated to what
        the user asked for (e.g., asked for laptop, cart has jewelry).
        """
        # Build cart text from item names and categories
        cart_texts = []
        for item in cart_items:
            parts = [item.get("name", "")]
            if item.get("category"):
                parts.append(item["category"])
            cart_texts.append(" ".join(parts))
        cart_text = " ".join(cart_texts)
        
        if not cart_text.strip():
            return 0.5  # No cart text to compare
        
        # Simple TF-IDF cosine similarity without sklearn
        # (to avoid import overhead for a lightweight check)
        return self._cosine_similarity(intent.lower(), cart_text.lower())
    
    def _cosine_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two text strings using term frequency."""
        # Tokenize
        words_a = re.findall(r'\b[a-z]+\b', text_a)
        words_b = re.findall(r'\b[a-z]+\b', text_b)
        
        if not words_a or not words_b:
            return 0.0
        
        # Build TF vectors
        counter_a = Counter(words_a)
        counter_b = Counter(words_b)
        
        # All unique words
        all_words = set(counter_a.keys()) | set(counter_b.keys())
        
        # Stop words to filter out
        stop_words = {
            "the", "a", "an", "is", "it", "to", "of", "and", "for", "in",
            "on", "at", "by", "this", "that", "with", "from", "or", "but",
            "buy", "get", "want", "need", "please", "me", "my", "i",
        }
        all_words -= stop_words
        
        if not all_words:
            return 0.5
        
        # Compute dot product and magnitudes
        dot = 0.0
        mag_a = 0.0
        mag_b = 0.0
        
        for w in all_words:
            va = counter_a.get(w, 0)
            vb = counter_b.get(w, 0)
            dot += va * vb
            mag_a += va * va
            mag_b += vb * vb
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot / (math.sqrt(mag_a) * math.sqrt(mag_b))
    
    def _check_category(self, intent: str, cart_items: List[Dict]) -> float:
        """
        Check if cart items belong to categories mentioned in the intent.
        
        Uses keyword matching against common product categories.
        """
        # Common category keywords
        category_map = {
            "laptop": ["laptop", "notebook", "computer", "macbook", "chromebook"],
            "phone": ["phone", "mobile", "smartphone", "iphone", "android"],
            "electronics": ["electronic", "gadget", "device", "charger", "cable"],
            "clothing": ["shirt", "pant", "dress", "shoe", "wear", "jacket", "tshirt"],
            "food": ["food", "grocery", "snack", "meal", "drink", "beverage"],
            "book": ["book", "novel", "textbook", "ebook"],
            "furniture": ["furniture", "chair", "table", "desk", "sofa", "bed"],
            "jewelry": ["jewelry", "ring", "necklace", "bracelet", "gold", "diamond"],
        }
        
        intent_lower = intent.lower()
        
        # Detect intended categories
        intended = set()
        for cat, keywords in category_map.items():
            if any(kw in intent_lower for kw in keywords):
                intended.add(cat)
        
        if not intended:
            return 0.7  # Can't determine category from intent
        
        # Check cart items against intended categories
        cart_categories = set()
        for item in cart_items:
            item_text = f"{item.get('name', '')} {item.get('category', '')}".lower()
            for cat, keywords in category_map.items():
                if any(kw in item_text for kw in keywords):
                    cart_categories.add(cat)
        
        if not cart_categories:
            return 0.5  # Can't determine cart categories
        
        # Score: overlap / intended
        overlap = intended & cart_categories
        if overlap:
            return len(overlap) / len(intended)
        
        return 0.0  # No overlap = complete mismatch
    
    def _check_quantity(self, intent: str, cart_items: List[Dict]) -> float:
        """
        Check if cart quantities are reasonable given the intent.
        
        Flags bulk purchases when intent says "a" or "one", and
        catches suspiciously large quantities.
        """
        total_quantity = sum(item.get("quantity", 1) for item in cart_items)
        
        # Check if intent implies single item
        single_markers = ["a ", "one ", "the ", "cheapest ", "best "]
        intent_lower = intent.lower()
        implies_single = any(intent_lower.startswith(m) or f" {m}" in intent_lower for m in single_markers)
        
        if implies_single and total_quantity > 3:
            return 0.2  # Intent says "a laptop", cart has 10 items
        
        if total_quantity > 20:
            return 0.3  # Suspiciously large quantity regardless
        
        return 1.0
    
    def _check_injection_markers(self, cart_items: List[Dict]) -> float:
        """
        Check for known prompt injection patterns in cart item names.
        
        These patterns indicate that a malicious product listing
        may have hijacked the agent's decision-making.
        """
        injection_patterns = [
            r"ignore\s+(previous|all|above)",
            r"system\s*prompt",
            r"you\s+are\s+now",
            r"disregard\s+(all|the)",
            r"new\s+instruction",
            r"override\s+(all|the)",
            r"<\s*script",
            r"javascript:",
            r"\{\{.*\}\}",
            r"\\n\\n",
            r"IMPORTANT:\s*ignore",
        ]
        
        for item in cart_items:
            item_name = item.get("name", "").lower()
            for pattern in injection_patterns:
                if re.search(pattern, item_name, re.IGNORECASE):
                    logger.warning(
                        f"[Semantic Engine] INJECTION MARKER DETECTED in: {item_name[:80]}"
                    )
                    return 0.0  # Hard fail on injection
        
        return 1.0  # No injection markers found
    
    def get_stats(self) -> Dict:
        """Return semantic engine statistics."""
        return {
            "total_checked": self._stats["total_checked"],
            "aligned": self._stats["aligned"],
            "ambiguous": self._stats["ambiguous"],
            "mismatch": self._stats["mismatch"],
            "mismatch_rate": (
                round(self._stats["mismatch"] / self._stats["total_checked"], 4)
                if self._stats["total_checked"] > 0 else 0.0
            ),
        }
