from app import clock, store
from app.events import log_event
from app.geo import travel_minutes
from app.matcher import is_feasible
from app.models import (
    EventSeverity,
    EventType,
    ItemType,
    Resource,
    ShipmentStatus,
)
from app.rules import REQUIRED_RESOURCES, is_compatible


def reroute_shelter_shipments(
    shelter_id: str, removed_resources: set[Resource]
) -> tuple[list[dict], list[dict]]:
    rerouted: list[dict] = []
    at_risk: list[dict] = []
    source_shelter = store.shelters[shelter_id]
    active_statuses = (
        ShipmentStatus.CLAIMED,
        ShipmentStatus.IN_TRANSIT,
    )

    for shipment in list(store.shipments.values()):
        if (
            shipment.shelter_id != shelter_id
            or shipment.status not in active_statuses
        ):
            continue

        batch = store.batches.get(shipment.batch_id)
        rider = store.riders.get(shipment.rider_id)
        if batch is None or rider is None:
            reason = "Shipment batch or rider is unavailable for rerouting."
            shipment.status = ShipmentStatus.AT_RISK
            at_risk.append({"shipmentId": shipment.id, "reason": reason})
            log_event(
                EventType.AT_RISK,
                EventSeverity.WARNING,
                f"Shipment {shipment.id} is at risk: {reason}",
                {"batchId": shipment.batch_id, "shipmentId": shipment.id},
            )
            continue

        required_resource_removed = bool(
            set(REQUIRED_RESOURCES[ItemType(batch.item_type)])
            & removed_resources
        )
        needs_reroute = (
            source_shelter.demand_remaining <= 0
            or not source_shelter.is_open
            or required_resource_removed
        )
        if not needs_reroute:
            continue

        donor = store.donors.get(batch.donor_id)
        candidates = []
        if donor is not None:
            for shelter in store.shelters.values():
                if shelter.id == shelter_id or not shelter.is_open:
                    continue
                free_demand = shelter.demand_remaining - shelter.reserved_qty
                if free_demand < shipment.qty:
                    continue
                if not is_compatible(ItemType(batch.item_type), shelter)[0]:
                    continue
                if not is_feasible(rider, donor, shelter, batch, clock.now())[0]:
                    continue
                travel_time = travel_minutes(rider.location, donor.location) + (
                    travel_minutes(donor.location, shelter.location)
                )
                candidates.append((travel_time, shelter.id, shelter))

        if candidates:
            _, _, destination = min(candidates, key=lambda item: (item[0], item[1]))
            previous_shelter_id = shipment.shelter_id
            if shipment.original_shelter_id is None:
                shipment.original_shelter_id = previous_shelter_id
            source_shelter.reserved_qty = max(
                0, source_shelter.reserved_qty - shipment.qty
            )
            destination.reserved_qty += shipment.qty
            shipment.shelter_id = destination.id
            shipment.status = ShipmentStatus.REROUTED
            rerouted.append(
                {
                    "shipmentId": shipment.id,
                    "fromShelterId": previous_shelter_id,
                    "toShelterId": destination.id,
                }
            )
            log_event(
                EventType.REROUTED,
                EventSeverity.WARNING,
                f"Shipment {shipment.id} rerouted from {previous_shelter_id} to {destination.id}.",
                {
                    "batchId": batch.id,
                    "shipmentId": shipment.id,
                    "riderId": rider.id,
                    "shelterId": destination.id,
                },
            )
        else:
            reason = "No open compatible shelter with sufficient demand is reachable before expiry."
            shipment.status = ShipmentStatus.AT_RISK
            shipment.lease_expires_at = None
            source_shelter.reserved_qty = max(
                0, source_shelter.reserved_qty - shipment.qty
            )
            if shipment.id in rider.active_shipment_ids:
                rider.active_shipment_ids.remove(shipment.id)
            if (
                not rider.active_shipment_ids
                and rider.id not in store.simulated_unresponsive
            ):
                rider.status = "AVAILABLE"
            batch.status = "AT_RISK"
            batch.status_reason = reason
            at_risk.append({"shipmentId": shipment.id, "reason": reason})
            log_event(
                EventType.AT_RISK,
                EventSeverity.WARNING,
                f"Shipment {shipment.id} is at risk: {reason}",
                {
                    "batchId": batch.id,
                    "shipmentId": shipment.id,
                    "riderId": rider.id,
                    "shelterId": shelter_id,
                },
            )

    return rerouted, at_risk
