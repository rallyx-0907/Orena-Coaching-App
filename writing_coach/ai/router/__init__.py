"""The AI Cost Router (D-18X, proposals/AI_COST_ROUTER.md).

One router for every routed capability: `route(capability_key, input)` validates the input against the capability's
contract, answers from the result cache when it can, and otherwise runs the operator's ordered pool through the
existing capability runtime (`platform.generate_structured`). Feature code never names a model.
"""

from writing_coach.ai.router.contract import (  # noqa: F401
    CapabilityContract,
    RouterInputInvalid,
    get_contract,
)
from writing_coach.ai.router.router import RouteResult, route  # noqa: F401
