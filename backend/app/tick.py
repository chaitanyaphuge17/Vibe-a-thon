from app import clock, store
from app.events import log_event
from app.matcher import split_batch
from app.models import (
    BatchStatus,
    EventSeverity,
    EventType,
    RiderStatus,
    ShipmentStatus,
)


def _release_reservation(qty: int, shelter_id: str) -> None:
    shelter = store.shelters.get(shelter_id)
    if shelter is not None:
        shelter.reserved_qty = max(0, shelter.reserved_qty - qty)


def _release_rider(shipment_id: str, rider_id: str) -> None:
    rider = store.riders.get(rider_id)
    if rider is None:
        return
    if shipment_id in rider.active_shipment_ids:
        rider.active_shipment_ids.remove(shipment_id)
    if not rider.active_shipment_ids and rider_id not in store.simulated_unresponsive:
        rider.status = RiderStatus.AVAILABLE


def run_tick() -> dict[str, int]:
    with store.lock:
        now = clock.now()
        summary = {"leasesExpired": 0, "reassigned": 0, "spoiled": 0}

        for shipment in list(store.shipments.values()):
            if (
                shipment.status
                not in (
                    ShipmentStatus.CLAIMED,
                    ShipmentStatus.IN_TRANSIT,
                    ShipmentStatus.REROUTED,
                )
                or shipment.lease_expires_at is None
                or shipment.lease_expires_at >= now
            ):
                continue

            batch = store.batches.get(shipment.batch_id)
            shipment.status = ShipmentStatus.EXPIRED_LEASE
            shipment.lease_expires_at = None
            _release_reservation(
                shipment.qty, shipment.shelter_id
            )
            _release_rider(shipment.id, shipment.rider_id)
            failed_rider = store.riders.get(shipment.rider_id)
            if failed_rider is not None:
                failed_rider.status = RiderStatus.UNRESPONSIVE
                store.simulated_unresponsive.add(failed_rider.id)
            summary["leasesExpired"] += 1
            log_event(
                EventType.LEASE_EXPIRED,
                EventSeverity.WARNING,
                f"Lease expired for shipment {shipment.id}.",
                {
                    "batchId": shipment.batch_id,
                    "shipmentId": shipment.id,
                    "riderId": shipment.rider_id,
                },
            )

            if batch is None or batch.status == BatchStatus.SPOILED:
                continue
            batch.remaining_qty += shipment.qty
            created, _ = split_batch(
                batch, exclude_rider_ids={shipment.rider_id}
            )
            if created:
                summary["reassigned"] += len(created)
                log_event(
                    EventType.REASSIGNED,
                    EventSeverity.INFO,
                    f"Shipment {shipment.id} quantity reassigned.",
                    {
                        "batchId": batch.id,
                        "shipmentId": shipment.id,
                        "riderId": shipment.rider_id,
                    },
                )

        for batch in store.batches.values():
            if batch.status != BatchStatus.SPOILED and batch.expires_at < now:
                batch.status = BatchStatus.SPOILED
                batch.status_reason = "Batch expired."
                batch.remaining_qty = 0
                summary["spoiled"] += 1
                log_event(
                    EventType.SPOILED,
                    EventSeverity.ERROR,
                    f"Batch {batch.id} spoiled after expiry.",
                    {"batchId": batch.id},
                )

                for shipment in store.shipments.values():
                    if (
                        shipment.batch_id != batch.id
                        or shipment.status
                        in (ShipmentStatus.DELIVERED, ShipmentStatus.SPOILED)
                    ):
                        continue
                    previous_status = shipment.status
                    if previous_status in (
                        ShipmentStatus.CREATED,
                        ShipmentStatus.CLAIMED,
                        ShipmentStatus.PICKED_UP,
                        ShipmentStatus.IN_TRANSIT,
                        ShipmentStatus.REROUTED,
                    ):
                        _release_reservation(
                            shipment.qty, shipment.shelter_id
                        )
                        _release_rider(shipment.id, shipment.rider_id)
                    shipment.status = ShipmentStatus.SPOILED
                    shipment.lease_expires_at = None
                    summary["spoiled"] += 1
                    log_event(
                        EventType.SPOILED,
                        EventSeverity.ERROR,
                        f"Shipment {shipment.id} spoiled with batch {batch.id}.",
                        {
                            "batchId": batch.id,
                            "shipmentId": shipment.id,
                            "riderId": shipment.rider_id,
                        },
                    )

        return summary
