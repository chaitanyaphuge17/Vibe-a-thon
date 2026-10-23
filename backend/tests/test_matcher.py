from datetime import timedelta

import pytest

from app import clock, store
from app.matcher import split_batch
from app.models import (
    Batch,
    BatchStatus,
    EventType,
    ItemType,
    Resource,
    RiderStatus,
)


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


def make_batch(item_type: ItemType, total_qty: int, expires_in_minutes: int) -> Batch:
    created_at = clock.now()
    return Batch(
        id="batch_test",
        donor_id="donor_1",
        item_type=item_type,
        total_qty=total_qty,
        remaining_qty=total_qty,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=expires_in_minutes),
        status=BatchStatus.OPEN,
        status_reason=None,
    )


def test_split_respects_rider_capacity_and_shelter_demand():
    for rider in store.riders.values():
        rider.capacity = 40
    store.shelters["shelter_b"].is_open = False
    store.shelters["shelter_c"].is_open = False
    batch = make_batch(ItemType.COOKED_MEAL, total_qty=180, expires_in_minutes=75)

    shipments, _ = split_batch(batch)

    assert len(shipments) > 1
    assert all(shipment.qty <= store.riders[shipment.rider_id].capacity for shipment in shipments)
    shelter_a_shipments = [
        shipment for shipment in shipments if shipment.shelter_id == "shelter_a"
    ]
    assert sum(shipment.qty for shipment in shelter_a_shipments) <= 50
    assert store.shelters["shelter_a"].reserved_qty <= 50
    assert batch.remaining_qty == batch.total_qty - sum(
        shipment.qty for shipment in shipments
    )
    assert all(store.riders[shipment.rider_id].status == RiderStatus.BUSY for shipment in shipments)
    assert any(event.type == EventType.SHIPMENT_CREATED for event in store.events)


def test_tight_expiry_batch_becomes_at_risk_with_reason():
    store.shelters["shelter_b"].is_open = False
    store.shelters["shelter_c"].is_open = False
    batch = make_batch(ItemType.COOKED_MEAL, total_qty=60, expires_in_minutes=5)

    shipments, rejections = split_batch(batch)

    assert shipments == []
    assert batch.status == BatchStatus.AT_RISK
    assert "before expiry" in batch.status_reason
    assert rejections
    assert any(event.type == EventType.AT_RISK for event in store.events)


def test_infant_formula_rejected_without_clean_water():
    for shelter in store.shelters.values():
        shelter.resources = [Resource.COOKING_FUEL]
    batch = make_batch(ItemType.INFANT_FORMULA, total_qty=30, expires_in_minutes=75)

    shipments, rejections = split_batch(batch)

    assert shipments == []
    assert batch.status == BatchStatus.AT_RISK
    assert any("clean_water" in rejection["reason"] for rejection in rejections)
    assert "clean_water" in batch.status_reason
