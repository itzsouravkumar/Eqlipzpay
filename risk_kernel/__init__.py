"""
EqlipZ Pay — Risk Kernel
=========================
The core decision-making brain of EqlipZ Pay.

Contains three engines:
  1. ConformalRiskEngine — prediction sets with coverage guarantees
  2. SemanticEntailmentEngine — AI agent intent verification
  3. DecisionRouter — three-way action combiner

All three are initialized as module-level singletons so the FastAPI
app can import and use them directly.
"""

from risk_kernel.conformal_engine import ConformalRiskEngine
from risk_kernel.semantic_engine import SemanticEntailmentEngine
from risk_kernel.decision_router import DecisionRouter

__all__ = [
    "ConformalRiskEngine",
    "SemanticEntailmentEngine",
    "DecisionRouter",
]
