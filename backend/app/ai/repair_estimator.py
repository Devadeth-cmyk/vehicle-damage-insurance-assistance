"""
ai/repair_estimator.py (ported unchanged from the validated pipeline)
Rule-based repair cost estimation, keyed on (part, damage_type, severity).

This is an INDICATIVE estimate based on researched approximate market rates,
not real workshop invoice data (which isn't available for this project) —
state this explicitly in your report, same as the severity heuristic.
The workshop's actual estimate remains authoritative; this only pre-fills
a starting number so the workshop isn't estimating from zero.
"""

# (part, damage_type, severity) -> (min_cost, max_cost) in INR, indicative only.
# Extend this table as needed; unmatched combinations fall back to a generic
# per-severity estimate rather than failing.
REPAIR_COST_TABLE = {
    ("front_bumper", "scratch", "Minor"): (1500, 3000),
    ("front_bumper", "dent", "Moderate"): (3000, 6000),
    ("front_bumper", "crack", "Moderate"): (3500, 7000),
    ("back_bumper", "scratch", "Minor"): (1500, 3000),
    ("back_bumper", "dent", "Moderate"): (3000, 6000),
    ("front_door", "dent", "Moderate"): (4000, 8000),
    ("back_door", "dent", "Moderate"): (4000, 8000),
    ("front_left_door", "dent", "Moderate"): (4000, 8000),
    ("front_right_door", "dent", "Moderate"): (4000, 8000),
    ("back_left_door", "dent", "Moderate"): (4000, 8000),
    ("back_right_door", "dent", "Moderate"): (4000, 8000),
    ("front_glass", "glass shatter", "Severe"): (8000, 15000),
    ("back_glass", "glass shatter", "Severe"): (7000, 13000),
    ("front_light", "lamp broken", "Moderate"): (5000, 9000),
    ("back_light", "lamp broken", "Moderate"): (4000, 7000),
    ("front_left_light", "lamp broken", "Moderate"): (5000, 9000),
    ("front_right_light", "lamp broken", "Moderate"): (5000, 9000),
    ("back_left_light", "lamp broken", "Moderate"): (4000, 7000),
    ("back_right_light", "lamp broken", "Moderate"): (4000, 7000),
    ("wheel", "tire flat", "Severe"): (3000, 6000),
    ("hood", "dent", "Moderate"): (5000, 10000),
    ("hood", "scratch", "Minor"): (2000, 4000),
    ("trunk", "dent", "Moderate"): (4500, 9000),
    ("tailgate", "dent", "Moderate"): (4500, 9000),
}

# Fallback when the exact (part, damage_type, severity) combination isn't in
# the table — a generic per-severity range, so the system always returns
# something rather than nothing.
GENERIC_SEVERITY_FALLBACK = {
    "Minor": (1500, 3500),
    "Moderate": (3500, 8000),
    "Severe": (7000, 15000),
}

SEGMENT_MULTIPLIER = {
    "economy": 1.0,
    "mid-range": 1.3,
    "luxury": 2.0,
}


def estimate_repair_cost(part, damage_type, severity, vehicle_segment="economy"):
    """
    Returns {"min_cost": int, "max_cost": int, "currency": "INR",
             "source": "lookup_table" | "generic_fallback", "vehicle_segment": str}

    Never raises — an unknown part/damage/severity combination or an
    unmatched "unknown" part still returns a usable estimate via the
    generic fallback, clearly marked as such.
    """
    key = (part, damage_type, severity)
    multiplier = SEGMENT_MULTIPLIER.get(vehicle_segment, 1.0)

    if key in REPAIR_COST_TABLE:
        base_min, base_max = REPAIR_COST_TABLE[key]
        source = "lookup_table"
    else:
        base_min, base_max = GENERIC_SEVERITY_FALLBACK.get(severity, GENERIC_SEVERITY_FALLBACK["Moderate"])
        source = "generic_fallback"

    return {
        "min_cost": round(base_min * multiplier),
        "max_cost": round(base_max * multiplier),
        "currency": "INR",
        "source": source,
        "vehicle_segment": vehicle_segment,
    }


def estimate_claim_repair_total(fused_detections, vehicle_segment="economy"):
    """
    Takes the list of fused detections from one image (or a whole claim) and
    returns a per-detection cost estimate plus a claim-level total range.
    Detections flagged requires_review are still estimated, but the result
    is marked provisional so downstream UI can show it as pending confirmation.
    """
    line_items = []
    total_min, total_max = 0, 0

    for det in fused_detections:
        part = det.get("part", "unknown")
        damage_type = det.get("damage_type")
        severity = det.get("severity") or "Moderate"  # never block on a missing severity

        cost = estimate_repair_cost(part, damage_type, severity, vehicle_segment)
        line_item = {
            "part": part,
            "damage_type": damage_type,
            "severity": severity,
            **cost,
            "provisional": bool(det.get("requires_review", False)),
        }
        line_items.append(line_item)
        total_min += cost["min_cost"]
        total_max += cost["max_cost"]

    return {
        "line_items": line_items,
        "total_min_cost": total_min,
        "total_max_cost": total_max,
        "currency": "INR",
        "disclaimer": "Indicative estimate based on approximate market rates, not actual workshop invoice data. Final cost is determined by the workshop.",
    }
