from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import store
from app.geo import travel_minutes
from app.main import app
from app.models import Resource, ShipmentStatus


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture
def client():
    return TestClient(app)


def create_in_transit_shipment(client: TestClient) -> tuple[str, str]:
    for shelter_id in ("shelter_b", "shelter_c"):
        store.shelters[shelter_id].is_open = False
    created = client.post(
        "/api/batches",
        json={
            "donorId": "donor_1",
            "itemType": "cooked_meal",
            "totalQty": 20,
            "expiresInMinutes": 75,
        },
    )
    assert created.status_code == 201
    dispatched = client.post("/api/batches/batch_1/dispatch", json={})
    assert dispatched.status_code == 200
    shipment = dispatched.json()["createdShipments"][0]
    claimed = client.post(
        f"/api/shipments/{shipment['id']}/claim",
        json={"riderId": shipment["riderId"]},
    )
    assert claimed.status_code == 200
    picked_up = client.post(
        f"/api/shipments/{shipment['id']}/pickup",
        json={},
    )
    assert picked_up.status_code == 200
    store.shelters["shelter_b"].is_open = True
    return shipment["id"], shipment["riderId"]


def test_closing_destination_reroutes_transit_shipment(client: TestClient):
    shipment_id, _ = create_in_transit_shipment(client)
    source = store.shelters["shelter_a"]
    destination = store.shelters["shelter_b"]
    original_reserved = source.reserved_qty

    response = client.post(
        "/api/shelters/shelter_a",
        json={"isOpen": False},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["rerouted"] == [
        {
            "shipmentId": shipment_id,
            "fromShelterId": "shelter_a",
            "toShelterId": "shelter_b",
        }
    ]
    assert result["atRisk"] == []
    shipment = store.shipments[shipment_id]
    assert shipment.status == ShipmentStatus.REROUTED
    assert shipment.shelter_id == "shelter_b"
    assert shipment.original_shelter_id == "shelter_a"
    assert source.reserved_qty == original_reserved - shipment.qty
    assert destination.reserved_qty == shipment.qty


def test_closing_destination_with_no_alternative_marks_at_risk(client: TestClient):
    shipment_id, rider_id = create_in_transit_shipment(client)
    store.shelters["shelter_b"].is_open = False
    source = store.shelters["shelter_a"]
    reserved_before = source.reserved_qty

    response = client.post(
        "/api/shelters/shelter_a",
        json={"isOpen": False},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["rerouted"] == []
    assert result["atRisk"][0]["shipmentId"] == shipment_id
    assert "No open compatible shelter" in result["atRisk"][0]["reason"]
    assert store.shipments[shipment_id].status == ShipmentStatus.AT_RISK
    assert source.reserved_qty == reserved_before - store.shipments[shipment_id].qty
    assert shipment_id not in store.riders[rider_id].active_shipment_ids


def test_removing_required_resource_reroutes_compatible_shipment(
    client: TestClient,
):
    for shelter_id in ("shelter_b", "shelter_c"):
        store.shelters[shelter_id].is_open = False
    created = client.post(
        "/api/batches",
        json={
            "donorId": "donor_1",
            "itemType": "infant_formula",
            "totalQty": 20,
            "expiresInMinutes": 75,
        },
    )
    assert created.status_code == 201
    dispatched = client.post("/api/batches/batch_1/dispatch", json={})
    assert dispatched.status_code == 200
    shipment = dispatched.json()["createdShipments"][0]
    assert shipment["shelterId"] == "shelter_a"
    assert client.post(
        f"/api/shipments/{shipment['id']}/claim",
        json={"riderId": shipment["riderId"]},
    ).status_code == 200
    assert client.post(
        f"/api/shipments/{shipment['id']}/pickup",
        json={},
    ).status_code == 200
    store.shelters["shelter_b"].is_open = True
    store.shelters["shelter_b"].resources.append(Resource.CLEAN_WATER)

    response = client.post(
        "/api/shelters/shelter_a",
        json={"resources": ["cooking_fuel"]},
    )

    assert response.status_code == 200
    assert response.json()["rerouted"][0]["toShelterId"] == "shelter_b"
    assert store.shipments[shipment["id"]].status == ShipmentStatus.REROUTED


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        ({"demandRemaining": -1}, "INVALID_FIELD"),
        ({"isOpen": "false"}, "INVALID_FIELD"),
        ({"resources": ["unknown"]}, "INVALID_FIELD"),
        ({"notAField": True}, "INVALID_FIELD"),
    ],
)
def test_shelter_update_validates_fields(
    client: TestClient, body: dict, expected_code: str
):
    response = client.post("/api/shelters/shelter_a", json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == expected_code


def test_shelter_update_not_found(client: TestClient):
    response = client.post("/api/shelters/missing", json={"isOpen": False})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHELTER_NOT_FOUND"


def test_sim_clock_advances_and_runs_tick(client: TestClient):
    response = client.post("/api/sim/clock", json={"advanceMinutes": 10})

    assert response.status_code == 200
    result = response.json()
    assert result["clock"]["offsetMinutes"] == 10
    assert result["tickSummary"] == {
        "leasesExpired": 0,
        "reassigned": 0,
        "spoiled": 0,
    }
    assert store.events[-1].type == "CLOCK_ADVANCED"


def test_scenario_endpoints_create_expected_batches(client: TestClient):
    handout = client.post("/api/sim/scenario/handout")
    tight = client.post("/api/sim/scenario/tight-expiry")
    incompatible = client.post("/api/sim/scenario/incompatible")

    assert handout.status_code == tight.status_code == incompatible.status_code == 201
    handout_batch = handout.json()["batch"]
    tight_batch = tight.json()["batch"]
    incompatible_batch = incompatible.json()["batch"]
    assert handout_batch["id"] == "batch_1"
    assert handout_batch["donorId"] == "donor_1"
    assert handout_batch["itemType"] == "cooked_meal"
    assert handout_batch["totalQty"] == 180
    assert handout_batch["expiresAt"] == (
        store.batches["batch_1"].created_at + timedelta(minutes=75)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    assert tight_batch["totalQty"] == 60
    best_travel = min(
        travel_minutes(rider.location, store.donors["donor_1"].location)
        + travel_minutes(
            store.donors["donor_1"].location, shelter.location
        )
        for rider in store.riders.values()
        for shelter in store.shelters.values()
    )
    tight_expiry_minutes = (
        store.batches[tight_batch["id"]].expires_at
        - store.batches[tight_batch["id"]].created_at
    ).total_seconds() / 60
    assert tight_expiry_minutes < best_travel + 10
    assert incompatible_batch["id"] == "batch_3"
    assert incompatible_batch["itemType"] == "infant_formula"
    assert incompatible_batch["totalQty"] == 30
    assert sum(
        Resource.CLEAN_WATER not in shelter.resources
        for shelter in store.shelters.values()
    ) >= 2

    dispatched = client.post(
        f"/api/batches/{incompatible_batch['id']}/dispatch",
        json={},
    )
    assert dispatched.status_code == 200
    assert dispatched.json()["createdShipments"] == []
    assert any(
        "clean_water" in rejection["reason"]
        for rejection in dispatched.json()["rejections"]
    )


def test_rerouted_shipment_can_still_be_delivered(client: TestClient):
    shipment_id, rider_id = create_in_transit_shipment(client)
    response = client.post(
        "/api/shelters/shelter_a",
        json={"isOpen": False},
    )
    assert response.json()["rerouted"]

    delivered = client.post(
        f"/api/shipments/{shipment_id}/deliver",
        json={},
    )

    assert delivered.status_code == 200
    assert delivered.json()["shipment"]["status"] == "DELIVERED"
    assert store.riders[rider_id].status == "AVAILABLE"
