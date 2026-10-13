import io


def test_upload_evidence(client, auth_headers):
    # 1. Create vehicle and claim
    v_res = client.post(
        "/api/v1/vehicles",
        json={"registration_number": "DOC-100", "make": "Ford", "model": "Focus"},
        headers=auth_headers,
    )
    vehicle_id = v_res.json()["id"]

    c_res = client.post(
        "/api/v1/claims",
        json={"vehicle_id": vehicle_id, "accident_description": "Side dent"},
        headers=auth_headers,
    )
    claim_id = c_res.json()["claim_id"]

    # 2. Upload dummy image file
    fake_file = io.BytesIO(b"dummy image bytes")
    files = {"file": ("damage_photo.jpg", fake_file, "image/jpeg")}

    upload_res = client.post(
        f"/api/v1/documents/claims/{claim_id}/evidence",
        files=files,
        headers=auth_headers,
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["message"] == "Evidence uploaded successfully"
    assert upload_res.json()["file_name"] == "damage_photo.jpg"
