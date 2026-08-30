import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

from schemas import ActionType, ExposurePolicy, RiskComponent

logger = logging.getLogger("eqlipz.policy")

class PolicyControlPlane:
    """
    EqlipZ Pay — Policy Control Plane
    Maps the Exposure score (E*) and constraints into an ActionType and ExposurePolicy.
    """
    
    def __init__(self):
        # Exposure thresholds (E*)
        self.L1_THRESHOLD = 100.0    # Below L1 -> RELEASE
        self.L2_THRESHOLD = 500.0    # L1 to L2 -> STEP_UP
        self.L3_THRESHOLD = 2000.0   # L2 to L3 -> HOLD / PARTIAL_RESERVE, Above -> REFUSE

    def evaluate_policy(
        self,
        e_star: float,
        risk_components: RiskComponent,
        reason_codes: List[str]
    ) -> Tuple[ActionType, ExposurePolicy, List[str]]:
        """
        Evaluate the final settlement policy based on the Exposure score E*.
        """
        policy = ExposurePolicy()
        action = ActionType.RELEASE
        
        # Hard Refusals (Deterministic Overrides)
        if "budget_exceeded" in reason_codes or "possible_injection" in reason_codes:
            action = ActionType.REFUSE
            return action, policy, reason_codes
            
        if "category_mismatch" in reason_codes or "brand_mismatch" in reason_codes:
            # Maybe not a hard refuse, but definitely high risk
            # We'll let the risk components push E* up, or force a hold here.
            e_star += 1000.0 # Artificial penalty
            
        # Tiered Logic based on E*
        if e_star < self.L1_THRESHOLD:
            action = ActionType.RELEASE
            policy.reserve_percent = 0
            policy.hold_duration_hours = 0
            
        elif self.L1_THRESHOLD <= e_star < self.L2_THRESHOLD:
            action = ActionType.STEP_UP
            policy.step_up_required = True
            policy.reserve_percent = 0
            policy.hold_duration_hours = 0
            
        elif self.L2_THRESHOLD <= e_star < self.L3_THRESHOLD:
            # Decide between HOLD and PARTIAL_RESERVE
            # If the user has some trust but E* is high, we might do partial reserve.
            # For simplicity, if e_star is closer to L2 we HOLD, closer to L3 we PARTIAL_RESERVE
            if e_star < (self.L2_THRESHOLD + self.L3_THRESHOLD) / 2:
                action = ActionType.HOLD
                policy.hold_duration_hours = 12
                policy.review_required = True
            else:
                action = ActionType.PARTIAL_RESERVE
                policy.reserve_percent = 30
                policy.hold_duration_hours = 24
                policy.review_required = True
                
        else:
            action = ActionType.REFUSE

        # Ensure we always add reason codes for non-release
        if action == ActionType.REFUSE and "HIGH_EXPOSURE" not in reason_codes:
            reason_codes.append("HIGH_EXPOSURE")
        elif action == ActionType.HOLD and "MODERATE_EXPOSURE" not in reason_codes:
            reason_codes.append("MODERATE_EXPOSURE")
        elif action == ActionType.STEP_UP and "STEP_UP_REQUIRED" not in reason_codes:
            reason_codes.append("STEP_UP_REQUIRED")

        logger.info(
            f"[Policy] E*: {e_star:.2f} -> Action: {action.value} "
            f"(Reserve: {policy.reserve_percent}%, Hold: {policy.hold_duration_hours}h)"
        )

        return action, policy, reason_codes

policy_control_plane = PolicyControlPlane()
