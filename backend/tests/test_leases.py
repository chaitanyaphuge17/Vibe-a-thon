from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import clock, store
from app.main import app
from app.matcher import split_batch
from app.models import Batch, BatchStatus, ItemType, ShipmentStatus


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture
def client():
    return TestClient(app)


def create_batch(total_qty: int = 30, expires_in_minutes: int = 60) -> Batch:
    created_at = clock.now()
    batch = Batch(
        id=f"batch_{store.next_batch_id}",
        donor_id="donor_1",
        item_type=ItemType.COOKED_MEAL,
        total_qty=total_qty,
        remaining_qty=total_qty,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=expires_in_minutes),
        status=BatchStatus.OPEN,
        status_reason=None,
    )
    store.next_batch_id += 1
    store.batches[batch.id] = batch
    return batch


def create_shipment_batch() -> tuple[Batch, str]:
    batch = create_batch()
    shipments, _ = split_batch(batch)
    assert shipments
    return batch, shipments[0].id


def test_claim_sets_lease_and_returns_ttl(client: TestClient):
    _, shipment_id = create_shipment_batch()
    shipment = store.shipments[shipment_id]

    response = client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": shipment.rider_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["shipment"]["status"] == "CLAIMED"
    assert payload["shipment"]["leaseExpiresAt"]
    assert 0 < payload["leaseTtlSeconds"] <= 300
    assert shipment.status == ShipmentStatus.CLAIMED
    assert shipment.lease_expires_at is not None
    second_claim = client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": shipment.rider_id},
    )
    assert second_claim.status_code == 409
    assert second_claim.json()["error"]["code"] == "NOT_CLAIMABLE"


def test_claim_rejects_load_above_rider_capacity(client: TestClient):
    _, shipment_id = create_shipment_batch()
    shipment = store.shipments[shipment_id]
    rider = store.riders[shipment.rider_id]
    rider.capacity = shipment.qty - 1

    response = client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": rider.id},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RIDER_AT_CAPACITY"


def test_state_has_all_collections_and_events_filter_after_id(client: TestClient):
    created = client.post(
        "/api/batches",
        json={
            "donorId": "donor_1",
            "itemType": "cooked_meal",
            "totalQty": 10,
            "expiresInMinutes": 60,
        },
    )
    assert created.status_code == 201
    batch_id = created.json()["batch"]["id"]
    dispatched = client.post(f"/api/batches/{batch_id}/dispatch", json={})
    assert dispatched.status_code == 200
    state = client.get("/api/state").json()
    assert {
        "clock",
        "donors",
        "riders",
        "shelters",
        "batches",
        "shipments",
        "events",
    } <= state.keys()

    events = client.get("/api/events", params={"since": "evt_1"}).json()["events"]
    assert events
    assert all(int(event["id"].removeprefix("evt_")) > 1 for event in events)


def test_shelter_update_rejects_non_object_body_with_contract_error(
    client: TestClient,
):
    response = client.post("/api/shelters/shelter_a", json=[])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD"


def test_expired_lease_marks_rider_unresponsive_and_reassigns(client: TestClient):
    batch, shipment_id = create_shipment_batch()
    shipment = store.shipments[shipment_id]
    failed_rider_id = shipment.rider_id

    response = client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": failed_rider_id},
    )
    assert response.status_code == 200

    response = client.post("/api/sim/clock", json={"advanceMinutes": 6})
    assert response.status_code == 200
    summary = response.json()["tickSummary"]

    assert summary["leasesExpired"] == 1
    assert summary["reassigned"] >= 1
    assert shipment.status == ShipmentStatus.EXPIRED_LEASE
    assert store.riders[failed_rider_id].status == "UNRESPONSIVE"
    assert failed_rider_id in store.simulated_unresponsive
    assert batch.remaining_qty == 0
    replacement = [
        item
        for item in store.shipments.values()
        if item.batch_id == batch.id and item.id != shipment_id
    ]
    assert replacement
    assert all(item.rider_id != failed_rider_id for item in replacement)
    replacement_shipment = replacement[0]
    assert client.post(
        f"/api/shipments/{replacement_shipment.id}/claim",
        json={"riderId": replacement_shipment.rider_id},
    ).status_code == 200
    assert client.post(
        f"/api/shipments/{replacement_shipment.id}/pickup",
        json={},
    ).status_code == 200
    assert client.post(
        f"/api/shipments/{replacement_shipment.id}/deliver",
        json={},
    ).status_code == 200
    assert batch.status == BatchStatus.COMPLETED


def test_expired_batch_and_undelivered_shipment_become_spoiled(
    client: TestClient,
):
    batch, shipment_id = create_shipment_batch()
    clock.advance(61)

    state = client.get("/api/state").json()

    assert batch.status == BatchStatus.SPOILED
    assert store.shipments[shipment_id].status == ShipmentStatus.SPOILED
    assert next(item for item in state["batches"] if item["id"] == batch.id)["status"] == "SPOILED"
    assert any(
        event.type == "SPOILED"
        for event in store.events
    )


def test_unresponsive_heartbeat_is_ignored(client: TestClient):
    rider_id = "rider_2"
    previous_location = store.riders[rider_id].location.model_copy()
    previous_heartbeat = store.riders[rider_id].last_heartbeat_at
    marked = client.post(
        f"/api/sim/rider/{rider_id}/unresponsive",
        json={"unresponsive": True},
    )
    assert marked.status_code == 200

    response = client.post(
        f"/api/riders/{rider_id}/heartbeat",
        json={"lat": 18.6, "lng": 73.9},
    )

    assert response.status_code == 200
    assert response.json()["ignored"] is True
    assert store.riders[rider_id].location == previous_location
    assert store.riders[rider_id].last_heartbeat_at == previous_heartbeat
    restored = client.post(
        f"/api/sim/rider/{rider_id}/unresponsive",
        json={"unresponsive": False},
    )
    assert restored.status_code == 200
    assert rider_id not in store.simulated_unresponsive


def test_heartbeat_updates_location_and_extends_active_lease(client: TestClient):
    _, shipment_id = create_shipment_batch()
    shipment = store.shipments[shipment_id]
    rider_id = shipment.rider_id
    assert client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": rider_id},
    ).status_code == 200
    previous_expiry = shipment.lease_expires_at
    assert previous_expiry is not None
    clock.advance(1)

    response = client.post(
        f"/api/riders/{rider_id}/heartbeat",
        json={"lat": 18.6, "lng": 73.9},
    )

    assert response.status_code == 200
    assert response.json()["extendedShipmentIds"] == [shipment_id]
    assert shipment.lease_expires_at > previous_expiry
    assert store.riders[rider_id].location.lat == 18.6
    assert store.riders[rider_id].location.lng == 73.9


def test_pickup_and_delivery_update_demand_and_complete_batch(client: TestClient):
    batch, shipment_id = create_shipment_batch()
    shipment = store.shipments[shipment_id]
    rider_id = shipment.rider_id
    shelter = store.shelters[shipment.shelter_id]
    initial_demand = shelter.demand_remaining
    initial_reserved = shelter.reserved_qty

    assert client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": rider_id},
    ).status_code == 200
    pickup = client.post(
        f"/api/shipments/{shipment_id}/pickup",
        json={},
    )
    assert pickup.status_code == 200
    assert pickup.json()["shipment"]["status"] == "IN_TRANSIT"
    delivered = client.post(
        f"/api/shipments/{shipment_id}/deliver",
        json={},
    )

    assert delivered.status_code == 200
    assert shelter.demand_remaining == initial_demand - shipment.qty
    assert shelter.reserved_qty == initial_reserved - shipment.qty
    assert shipment.status == ShipmentStatus.DELIVERED
    assert batch.status == BatchStatus.COMPLETED
    assert store.riders[rider_id].active_shipment_ids == []
