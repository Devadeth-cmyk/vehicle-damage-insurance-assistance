def test_create_and_get_vehicles(client, auth_headers):
    vehicle_payload = {
        "registration_number": "ABC-1234",
        "make": "Toyota",
        "model": "Camry",
        "year": 2022,
        "fuel_type": "Hybrid",
    }

    create_res = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload,
        headers=auth_headers,
    )
    assert create_res.status_code == 200
    created_data = create_res.json()
    assert created_data["registration_number"] == "ABC-1234"
    assert "id" in created_data

    list_res = client.get("/api/v1/vehicles", headers=auth_headers)
    assert list_res.status_code == 200
    vehicles = list_res.json()
    assert len(vehicles) == 1
    assert vehicles[0]["make"] == "Toyota"
