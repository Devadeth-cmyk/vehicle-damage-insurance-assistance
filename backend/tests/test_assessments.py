import io
from unittest.mock import patch

import cv2
import numpy as np


def _png_bytes() -> bytes:
    ok, buf = cv2.imencode(".png", np.zeros((100, 100, 3), np.uint8))
    assert ok
    return buf.tobytes()


def test_assessment_flow(client, auth_headers):
    # 1. Create vehicle and claim
    v_res = client.post(
        "/api/v1/vehicles",
        json={"registration_number": "ASS-555", "make": "BMW", "model": "3 Series"},
        headers=auth_headers,
    )
    vehicle_id = v_res.json()["id"]

    c_res = client.post(
        "/api/v1/claims",
        json={"vehicle_id": vehicle_id, "accident_description": "Bumper scratch"},
        headers=auth_headers,
    )
    claim_id = c_res.json()["claim_id"]

    # 2. Upload evidence image
    fake_file = io.BytesIO(_png_bytes())
    client.post(
        f"/api/v1/documents/claims/{claim_id}/evidence",
        files={"file": ("bumper.png", fake_file, "image/png")},
        headers=auth_headers,
    )

    # 3. Mock model detectors so YOLO missing files won't raise FileNotFoundError in test
    with (
        patch(
            "app.services.assessment_service.detect_damage",
            return_value=[
                {
                    "damage_id": 1,
                    "damage_type": "scratch",
                    "bbox": [10.0, 10.0, 50.0, 50.0],
                    "confidence": 0.92,
                    "severity": "Minor",
                    "severity_source": "heuristic",
                }
            ],
        ),
        patch(
            "app.services.assessment_service.detect_parts",
            return_value=[
                {
                    "part_id": 1,
                    "part": "front_bumper",
                    "confidence": 0.95,
                    "bbox": [0.0, 0.0, 100.0, 100.0],
                    "mask": np.ones((100, 100), dtype=bool),
                }
            ],
        ),
        patch(
            "app.services.assessment_service.detect_severity",
            return_value=[],
        ),
    ):

        run_res = client.post(
            f"/api/v1/assessments/{claim_id}/run", headers=auth_headers
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["claim_id"] == claim_id
        assert data["status"] in ["completed", "complete"]
        det = data["fusion"]["images"][0]["detections"][0]
        assert det["part"] == "front_bumper"
        assert det["damage_type"] == "scratch"

        get_res = client.get(
            f"/api/v1/assessments/{claim_id}", headers=auth_headers
        )
        assert get_res.status_code == 200
        assert get_res.json()["claim_id"] == claim_id
