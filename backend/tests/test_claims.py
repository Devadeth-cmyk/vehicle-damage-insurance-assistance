def test_create_and_get_claims(client, auth_headers):
    # 1. Create a vehicle first
    v_res = client.post(
        "/api/v1/vehicles",
        json={
            "registration_number": "XYZ-999",
            "make": "Honda",
            "model": "Civic",
        },
        headers=auth_headers,
    )
    vehicle_id = v_res.json()["id"]

    # 2. Create claim
    claim_payload = {
        "vehicle_id": vehicle_id,
        "accident_date": "2026-09-20",
        "accident_location": "Main St & 5th Ave",
        "accident_description": "Rear-end collision at traffic light",
    }
    create_res = client.post(
        "/api/v1/claims", json=claim_payload, headers=auth_headers
    )
    assert create_res.status_code == 200
    claim_data = create_res.json()
    assert "claim_id" in claim_data
    claim_str_id = claim_data["claim_id"]

    # 3. Get all user claims
    list_res = client.get("/api/v1/claims", headers=auth_headers)
    assert list_res.status_code == 200
    claims = list_res.json()
    assert len(claims) == 1

    # 4. Get specific claim by ID
    get_res = client.get(f"/api/v1/claims/{claim_str_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["claim_id"] == claim_str_id
