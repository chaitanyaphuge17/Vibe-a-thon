from datetime import datetime, timedelta
from typing import Iterable

from app import clock, store
from app.events import log_event
from app.geo import travel_minutes
from app.models import (
    Batch,
    BatchStatus,
    Donor,
    EventSeverity,
    EventType,
    Rider,
    RiderStatus,
    Shipment,
    ShipmentStatus,
    Shelter,
)
from app.rules import is_compatible


SAFETY_BUFFER = 10


def is_feasible(
    rider: Rider,
    donor: Donor,
    shelter: Shelter,
    batch: Batch,
    now: datetime,
) -> tuple[bool, str]:
    travel_time = travel_minutes(rider.location, donor.location) + travel_minutes(
        donor.location, shelter.location
    )
    arrival = now + timedelta(minutes=travel_time)
    latest_arrival = batch.expires_at - timedelta(minutes=SAFETY_BUFFER)
    if arrival > latest_arrival:
        return False, "Cannot reach donor and shelter before expiry."
    return True, ""


def _rejection(
    rejections: list[dict[str, str]],
    seen: set[tuple[str, str]],
    reference: str,
    identifier: str,
    reason: str,
) -> None:
    key = (identifier, reason)
    if key not in seen:
        seen.add(key)
        rejections.append({reference: identifier, "reason": reason})


def split_batch(
    batch: Batch,
    exclude_rider_ids: Iterable[str] = (),
) -> tuple[list[Shipment], list[dict[str, str]]]:
    with store.lock:
        donor = store.donors.get(batch.donor_id)
        if donor is None:
            raise ValueError(f"Batch {batch.id} references missing donor {batch.donor_id}")

        excluded = set(exclude_rider_ids)
        created_shipments: list[Shipment] = []
        rejections: list[dict[str, str]] = []
        seen_rejections: set[tuple[str, str]] = set()
        current_time = clock.now()

        while batch.remaining_qty > 0:
            candidate_shelters: list[Shelter] = []
            for shelter in store.shelters.values():
                if not shelter.is_open:
                    _rejection(
                        rejections, seen_rejections, "shelterId",
                        shelter.id, "Shelter is closed.",
                    )
                    continue
                if shelter.demand_remaining - shelter.reserved_qty <= 0:
                    _rejection(
                        rejections, seen_rejections, "shelterId",
                        shelter.id, "Shelter has no remaining demand.",
                    )
                    continue
                compatible, reason = is_compatible(batch.item_type, shelter)
                if not compatible:
                    _rejection(
                        rejections, seen_rejections, "shelterId",
                        shelter.id, reason,
                    )
                    continue
                candidate_shelters.append(shelter)

            candidate_riders = [
                rider
                for rider in store.riders.values()
                if rider.status == RiderStatus.AVAILABLE
                and rider.id not in excluded
            ]
            for rider in store.riders.values():
                if rider.id in excluded:
                    _rejection(
                        rejections, seen_rejections, "riderId",
                        rider.id, "Rider is excluded from matching.",
                    )
                elif rider.status != RiderStatus.AVAILABLE:
                    _rejection(
                        rejections, seen_rejections, "riderId",
                        rider.id, "Rider is not available.",
                    )

            feasible_pairs: list[tuple[float, float, str, str, Rider, Shelter]] = []
            for shelter in candidate_shelters:
                for rider in candidate_riders:
                    feasible, reason = is_feasible(
                        rider, donor, shelter, batch, current_time
                    )
                    if not feasible:
                        _rejection(
                            rejections, seen_rejections, "riderId",
                            rider.id, reason,
                        )
                        continue
                    rider_to_donor = travel_minutes(rider.location, donor.location)
                    donor_to_shelter = travel_minutes(
                        donor.location, shelter.location
                    )
                    total_travel = rider_to_donor + donor_to_shelter
                    spare_minutes = (
                        batch.expires_at - timedelta(minutes=SAFETY_BUFFER)
                        - current_time
                    ).total_seconds() / 60 - total_travel
                    feasible_pairs.append(
                        (
                            total_travel,
                            -spare_minutes,
                            rider.id,
                            shelter.id,
                            rider,
                            shelter,
                        )
                    )

            if not feasible_pairs:
                break

            _, _, _, _, rider, shelter = min(
                feasible_pairs, key=lambda pair: pair[:4]
            )
            qty = min(
                rider.capacity,
                shelter.demand_remaining - shelter.reserved_qty,
                batch.remaining_qty,
            )
            rider_to_donor = travel_minutes(rider.location, donor.location)
            donor_to_shelter = travel_minutes(donor.location, shelter.location)
            shipment_id = f"ship_{store.next_shipment_id}"
            store.next_shipment_id += 1
            shipment = Shipment(
                id=shipment_id,
                batch_id=batch.id,
                rider_id=rider.id,
                shelter_id=shelter.id,
                original_shelter_id=None,
                qty=qty,
                status=ShipmentStatus.CREATED,
                eta_pickup_at=current_time + timedelta(minutes=rider_to_donor),
                eta_delivery_at=current_time
                + timedelta(minutes=rider_to_donor + donor_to_shelter),
                lease_expires_at=None,
                created_at=current_time,
            )
            store.shipments[shipment_id] = shipment
            created_shipments.append(shipment)
            batch.remaining_qty -= qty
            shelter.reserved_qty += qty
            rider.status = RiderStatus.BUSY
            rider.active_shipment_ids.append(shipment_id)
            log_event(
                EventType.SHIPMENT_CREATED,
                EventSeverity.INFO,
                f"Shipment {shipment_id} created for batch {batch.id}.",
                {
                    "batchId": batch.id,
                    "shipmentId": shipment_id,
                    "riderId": rider.id,
                    "shelterId": shelter.id,
                },
            )

        if not created_shipments:
            batch.status = BatchStatus.AT_RISK
            priority_reasons = (
                "Cannot reach donor and shelter before expiry.",
                "Missing required resource:",
            )
            batch.status_reason = next(
                (
                    reason
                    for preferred in priority_reasons
                    for rejection in rejections
                    if (reason := rejection["reason"]).startswith(preferred)
                ),
                (
                    rejections[0]["reason"]
                    if rejections
                    else "No available rider and compatible open shelter with remaining demand."
                ),
            )
            log_event(
                EventType.AT_RISK,
                EventSeverity.WARNING,
                f"Batch {batch.id} is at risk: {batch.status_reason}",
                {"batchId": batch.id},
            )
        elif batch.remaining_qty > 0:
            batch.status = BatchStatus.PARTIALLY_ASSIGNED
            batch.status_reason = None
        else:
            batch.status = BatchStatus.FULLY_ASSIGNED
            batch.status_reason = None

        return created_shipments, rejections
