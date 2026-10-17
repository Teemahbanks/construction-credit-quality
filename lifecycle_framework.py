"""Uncalibrated loan-stage interface for future pilot implementations.

FFIEC Call Reports do not provide loan-level project stages, PD, LGD, or draw
schedules. This module specifies arithmetic and input contracts; it is not a
fitted or validated PD/LGD model. Test values are illustrative, not actual loans,
underwriting guidance, regulatory capital estimates, or CECL allowances.
"""

from dataclasses import dataclass
from enum import Enum
import math


class Stage(str, Enum):
    PRE_DEVELOPMENT = "pre_development"
    CONSTRUCTION_DRAW = "construction_draw"
    COMPLETION = "completion"
    STABILIZATION = "stabilization"


@dataclass(frozen=True)
class StageInput:
    stage: Stage
    probability_of_default: float
    loss_given_default: float
    funded_balance: float
    unfunded_commitment: float
    credit_conversion_factor: float


def _fraction(name: str, value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return value


def exposure_at_default(
    funded_balance: float, unfunded_commitment: float, credit_conversion_factor: float
) -> float:
    """Compute EAD as funded balance plus CCF-adjusted undrawn commitment.

    The credit conversion factor is an input; this function does not estimate it.
    """
    if not math.isfinite(funded_balance) or funded_balance < 0:
        raise ValueError("funded_balance must be finite and nonnegative")
    if not math.isfinite(unfunded_commitment) or unfunded_commitment < 0:
        raise ValueError("unfunded_commitment must be finite and nonnegative")
    return (
        funded_balance
        + _fraction("credit_conversion_factor", credit_conversion_factor)
        * unfunded_commitment
    )


def illustrative_pd_lgd_ead_product(inputs: StageInput) -> float:
    """Compute PD × LGD × EAD for a shared, specified measurement horizon.

    PD, LGD, and EAD must use the same horizon. CECL, stress testing, discounted
    cash flows, and capital adequacy require separate governance and estimation.
    """
    if not isinstance(inputs.stage, Stage):
        raise ValueError("stage must be a Stage enum value")
    pd = _fraction("probability_of_default", inputs.probability_of_default)
    lgd = _fraction("loss_given_default", inputs.loss_given_default)
    ead = exposure_at_default(
        inputs.funded_balance,
        inputs.unfunded_commitment,
        inputs.credit_conversion_factor,
    )
    return pd * lgd * ead
