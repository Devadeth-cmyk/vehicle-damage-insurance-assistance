"""
Repair estimation service.

This module is adapted from the repair-estimation logic in the
vehicle insurance claim package notebook.

It produces two separate figures:

1. AI indicative estimate
   - Based on the configured project rate card.
   - Not an insurer-approved amount.
   - Remains unverified until technician verification.

2. Workshop estimate
   - Entered by the service center/workshop.
   - Authoritative when entered.
   - NEVER added to the AI indicative estimate.

Important:
- GST is excluded.
- Parts depreciation is excluded.
- Policy excess/deductible is excluded.
- The insurer/surveyor makes the final assessment.
"""

from __future__ import annotations

from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

RATE_CARD_VERSION = "project-demo-rate-card-v1"

REPAIR_RATES = {
    "dent": {
        "Minor": {
            "repair": 2000,
            "replace": 8000,
        },
        "Moderate": {
            "repair": 4000,
            "replace": 10000,
        },
        "Severe": {
            "repair": 7000,
            "replace": 15000,
        },
    },

    "scratch": {
        "Minor": {
            "repair": 1500,
            "replace": 7000,
        },
        "Moderate": {
            "repair": 3000,
            "replace": 8000,
        },
        "Severe": {
            "repair": 5000,
            "replace": 10000,
        },
    },

    "crack": {
        "Minor": {
            "repair": 2500,
            "replace": 8000,
        },
        "Moderate": {
            "repair": 4500,
            "replace": 10000,
        },
        "Severe": {
            "repair": 7000,
            "replace": 15000,
        },
    },

    "lamp broken": {
        "Minor": {
            "repair": 2000,
            "replace": 6000,
        },
        "Moderate": {
            "repair": 3000,
            "replace": 8000,
        },
        "Severe": {
            "repair": 4000,
            "replace": 12000,
        },
    },

    "glass shatter": {
        "Minor": {
            "repair": 3000,
            "replace": 10000,
        },
        "Moderate": {
            "repair": 5000,
            "replace": 15000,
        },
        "Severe": {
            "repair": 7000,
            "replace": 20000,
        },
    },

    "tire flat": {
        "Minor": {
            "repair": 1000,
            "replace": 5000,
        },
        "Moderate": {
            "repair": 1500,
            "replace": 6000,
        },
        "Severe": {
            "repair": 2000,
            "replace": 8000,
        },
    },
}


DEFAULT_ACTION_BY_SEVERITY = {
    "Minor": "repair",
    "Moderate": "repair",
    "Severe": "replace",
}


SEVERITY_ORDER = {
    "Minor": 1,
    "Moderate": 2,
    "Severe": 3,
}


# Optional multiplier per vehicle part.
#
# Example:
#
# PART_COST_FACTOR = {
#     "hood": 1.3,
#     "front_glass": 1.5,
# }
#
# Default = 1.0
PART_COST_FACTOR: dict[str, float] = {}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_damage_name(
    damage_type: str | None,
) -> str:

    if damage_type is None:
        return ""

    return (
        str(damage_type)
        .strip()
        .lower()
        .replace("_", " ")
    )


# ============================================================
# VERIFICATION HELPERS
# ============================================================

def safe_get_detections(image_result: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(image_result, dict):
        return []
    dets = image_result.get("detections", [])
    if isinstance(dets, dict):
        dets = dets.get("fused_items", []) or dets.get("detections", [])
    if not isinstance(dets, list):
        return []
    return [d for d in dets if isinstance(d, dict)]


def is_rejected(
    finding: dict[str, Any],
) -> bool:
    if not isinstance(finding, dict):
        return False

    return (
        finding.get("verification_status")
        == "TECHNICIAN_REJECTED"
    )


def is_verified(
    finding: dict[str, Any],
) -> bool:
    """
    Returns True only when the technician has explicitly
    verified the finding.
    """

    return (
        finding.get("verification_status")
        == "TECHNICIAN_VERIFIED"
    )


# ============================================================
# RATE LOOKUP
# ============================================================

def rate_for(
    damage_type: str,
    severity: str,
    action: str,
) -> float | None:
    """
    Return the configured repair/replace rate.

    Returns None when no rate exists.
    """

    rates = REPAIR_RATES.get(
        normalize_damage_name(damage_type)
    )

    if rates is None:
        return None

    if severity not in rates:
        return None

    return float(
        rates[severity].get(
            action,
            0,
        )
    )


# ============================================================
# WORKSHOP ESTIMATE
# ============================================================

def build_workshop_items(
    workshop_items: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Normalize workshop-entered repair items.

    Expected input:

    [
        {
            "description": "Front bumper repair + paint",
            "quantity": 1,
            "unit_price": 6500
        },
        {
            "description": "Labour",
            "quantity": 1,
            "unit_price": 2000
        }
    ]

    Negative quantity or price is rejected.
    """

    normalized_items = []

    for item in workshop_items or []:

        quantity = float(
            item.get(
                "quantity",
                1,
            )
        )

        unit_price = float(
            item.get(
                "unit_price",
                0,
            )
        )

        if quantity < 0:

            raise ValueError(
                f"Negative quantity in workshop item: {item}"
            )

        if unit_price < 0:

            raise ValueError(
                f"Negative unit price in workshop item: {item}"
            )

        amount = round(
            quantity * unit_price,
            2,
        )

        normalized_items.append(
            {
                "description": item.get(
                    "description",
                    "Workshop item",
                ),
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount,
                "currency": "INR",
                "source": item.get(
                    "source",
                    "workshop",
                ),
            }
        )

    return normalized_items


# ============================================================
# MAIN REPAIR ESTIMATION
# ============================================================

def build_repair_estimate(
    claim: dict[str, Any],
    workshop_items: list[dict[str, Any]] | None = None,
    part_cost_factor: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Build the complete repair estimate.

    Parameters
    ----------
    claim:
        Claim analysis dictionary containing:

        {
            "images": [
                {
                    "image": "...",
                    "detections": [
                        {
                            "damage_id": 1,
                            "part": "front_bumper",
                            "damage_type": "dent",
                            "severity": "Moderate",
                            "verification_status":
                                "TECHNICIAN_VERIFIED",
                            "ref": "IMG001-D1"
                        }
                    ]
                }
            ]
        }

    workshop_items:
        Workshop/service-center estimate.

    part_cost_factor:
        Optional cost multiplier for specific parts.

    Returns
    -------
    dict
        Complete repair estimate object.
    """

    if part_cost_factor is None:
        part_cost_factor = PART_COST_FACTOR

    groups: dict[
        tuple[str, str],
        list[tuple[str, dict[str, Any]]]
    ] = {}

    unpriced: list[dict[str, Any]] = []

    # ========================================================
    # COLLECT FINDINGS
    # ========================================================

    for image_result in claim.get(
        "images",
        [],
    ):

        image_name = image_result.get(
            "image",
            "",
        )

        for finding in safe_get_detections(image_result):

            # ------------------------------------------------
            # Technician rejected findings are excluded.
            # ------------------------------------------------

            if is_rejected(finding):
                continue

            part = finding.get(
                "part",
                "unknown",
            )

            damage_type = normalize_damage_name(
                finding.get(
                    "damage_type"
                )
            )

            severity = finding.get(
                "severity"
            )

            base = {
                "image": image_name,
                "damage_id": finding.get(
                    "damage_id"
                ),
                "ref": finding.get(
                    "ref"
                ),
                "part": part,
                "damage_type": damage_type,
                "severity": (
                    severity
                    if severity
                    else "Unknown"
                ),
            }

            # ------------------------------------------------
            # Cannot price unknown part/severity.
            # ------------------------------------------------

            if (
                part == "unknown"
                or not severity
            ):

                unpriced.append(
                    {
                        **base,
                        "reason": (
                            "insufficient_information_for_"
                            "preliminary_pricing"
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # Check whether a rate exists.
            # ------------------------------------------------

            repair_rate = rate_for(
                damage_type,
                severity,
                "repair",
            )

            if repair_rate is None:

                unpriced.append(
                    {
                        **base,
                        "reason": (
                            "no_configured_rate_for_"
                            "damage_type"
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # Group identical part + damage combinations.
            #
            # This prevents:
            #
            # Front bumper dent in image 1
            # Front bumper dent in image 2
            # Front bumper dent in image 3
            #
            # from being charged three times.
            # ------------------------------------------------

            groups.setdefault(
                (
                    part,
                    damage_type,
                ),
                [],
            ).append(
                (
                    image_name,
                    finding,
                )
            )

    # ========================================================
    # BUILD AI INDICATIVE ITEMS
    # ========================================================

    ai_items: list[dict[str, Any]] = []

    for (
        part,
        damage_type,
    ), members in groups.items():

        # ----------------------------------------------------
        # Select the worst severity among multiple photographs.
        # ----------------------------------------------------

        valid_members = [
            member
            for member in members
            if member[1].get("severity") in SEVERITY_ORDER
        ]

        if not valid_members:

            continue

        worst = max(
            valid_members,
            key=lambda member:
                SEVERITY_ORDER[
                    member[1]["severity"]
                ],
        )

        image_name, finding = worst

        severity = finding[
            "severity"
        ]

        action = DEFAULT_ACTION_BY_SEVERITY.get(
            severity,
            "repair",
        )

        base_rate = rate_for(
            damage_type,
            severity,
            action,
        )

        if base_rate is None:

            unpriced.append(
                {
                    "image": image_name,
                    "damage_id": finding.get(
                        "damage_id"
                    ),
                    "ref": finding.get(
                        "ref"
                    ),
                    "part": part,
                    "damage_type": damage_type,
                    "severity": severity,
                    "reason": (
                        "no_configured_rate_for_"
                        "recommended_action"
                    ),
                }
            )

            continue

        multiplier = float(
            part_cost_factor.get(
                part,
                1.0,
            )
        )

        unit_price = (
            base_rate * multiplier
        )

        source_refs = [
            member[1].get("ref")
            for member in members
            if member[1].get("ref")
        ]

        # ----------------------------------------------------
        # An AI estimate is verified only when ALL contributing
        # findings have been technician verified.
        # ----------------------------------------------------

        review_required = not all(
            is_verified(member[1])
            for member in members
        )

        ai_items.append(
            {
                "image": image_name,
                "damage_id": finding.get(
                    "damage_id"
                ),
                "part": part,
                "damage_type": damage_type,
                "severity": severity,
                "recommended_action": action,
                "quantity": 1,
                "unit_price": round(
                    unit_price,
                    2,
                ),
                "amount": round(
                    unit_price,
                    2,
                ),
                "currency": "INR",
                "source_refs": source_refs,
                "review_required": review_required,
                "source": (
                    "ai_indicative_rate_card"
                ),
            }
        )

    # ========================================================
    # WORKSHOP ITEMS
    # ========================================================

    workshop = build_workshop_items(
        workshop_items
    )

    # ========================================================
    # TOTALS
    # ========================================================

    ai_total = round(
        sum(
            item["amount"]
            for item in ai_items
        ),
        2,
    )

    workshop_total = round(
        sum(
            item["amount"]
            for item in workshop
        ),
        2,
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {
        "estimate_type": (
            "WORKSHOP_ESTIMATE_WITH_AI_INDICATIVE"
            if workshop
            else
            "AI_INDICATIVE_ONLY_PENDING_WORKSHOP_ESTIMATE"
        ),

        "currency": "INR",

        "workshop_items": workshop,

        "workshop_total": workshop_total,

        "ai_preliminary_items": ai_items,

        "ai_preliminary_total": ai_total,

        "unpriced_findings": unpriced,

        "rate_card_version": (
            RATE_CARD_VERSION
        ),

        "excludes": [
            "GST",
            "parts depreciation",
            "policy excess/deductible",
        ],

        "review_required": (
            bool(unpriced)
            or any(
                item["review_required"]
                for item in ai_items
            )
            or not workshop
        ),

        "disclaimer": (
            "The AI figure is an unverified "
            "indicative value from a generic "
            "rate card and is not a quotation. "
            "The workshop figure is the workshop's "
            "own estimate. Neither is an "
            "insurer-approved settlement amount; "
            "the insurer/surveyor makes the final "
            "assessment."
        ),
    }