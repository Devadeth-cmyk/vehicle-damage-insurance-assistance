"""Vehicle makes supported by the customer registration workflow."""

import re

SUPPORTED_VEHICLE_MAKES = (
    "Maruti Suzuki",
    "Hyundai",
    "Tata Motors",
    "Mahindra",
    "Toyota",
    "Kia",
)


def canonical_vehicle_make(value: str) -> str | None:
    normalized = " ".join(value.strip().casefold().replace("maruthi", "maruti").split())
    aliases = {
        "maruti": "Maruti Suzuki",
        "maruti suzuki": "Maruti Suzuki",
        "hyundai": "Hyundai",
        "tata": "Tata Motors",
        "tata motors": "Tata Motors",
        "mahindra": "Mahindra",
        "toyota": "Toyota",
        "kia": "Kia",
    }
    return aliases.get(normalized)


def infer_vehicle_make_from_center_name(value: str) -> str | None:
    """Infer a center's single routed make from its name, longest phrase first."""
    words = re.findall(r"[a-z0-9]+", value.casefold().replace("maruthi", "maruti"))
    for size in range(len(words), 0, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start : start + size])
            make = canonical_vehicle_make(phrase)
            if make:
                return make
    return None
