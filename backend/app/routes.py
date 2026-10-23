from datetime import timedelta
from math import ceil
from typing import Any

from fastapi import APIRouter

from app import clock, store
from app.events import log_event
from app.geo import travel_minutes
from app.leases import extend_shipment_lease, lease_expiry
from app.matcher import SAFETY_BUFFER, is_feasible, split_batch
from app.models import (
    Batch,
    BatchStatus,
    CamelModel,
    EventSeverity,
    EventType,
    ItemType,
    Location,
    Resource,
)
from app.rules import REQUIRED_RESOURCES
from app.rules import is_compatible
from app.reroute import reroute_shelter_shipments
from app.tick import run_tick


router = APIRouter(prefix="/api")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class CreateBatchRequest(CamelModel):
    donor_id: str
    item_type: str
    total_qty: int
    expires_in_minutes: int


class ClaimShipmentRequest(CamelModel):
    rider_id: str


class EmptyRequest(CamelModel):
    pass


class ShelterUpdateRequest(CamelModel):
    demand_remaining: int | None = None
    is_open: bool | None = None
    resources: list[Resource] | None = None


class AdvanceClockRequest(CamelModel):
    advance_minutes: int


class RiderUnresponsiveRequest(CamelModel):
    unresponsive: bool


def _json(model: CamelModel) -> dict:
    return model.model_dump(mode="json", by_alias=True)


def _timestamp(minutes: int = 0) -> str:
    return (clock.now() + timedelta(minutes=minutes)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/state")
def get_state() -> dict:
    run_tick()
    with store.lock:
        return {
            "clock": {
                "now": _timestamp(),
                "offsetMinutes": clock.offset_minutes(),
            },
            "donors": [_json(item) for item in store.donors.values()],
            "riders": [_json(item) for item in store.riders.values()],
            "shelters": [_json(item) for item in store.shelters.values()],
            "batches": [_json(item) for item in store.batches.values()],
            "shipments": [_json(item) for item in store.shipments.values()],
            "events": [_json(item) for item in store.events[-100:]],
        }


@router.get("/rules")
def get_rules() -> dict[str, list[str]]:
    return {
        item_type.value: [resource.value for resource in resources]
        for item_type, resources in REQUIRED_RESOURCES.items()
    }


@router.get("/events")
def get_events(since: str | None = None) -> dict:
    # STUB: replaced in phase Bx
    return {"events": []}


def _create_batch(
    donor_id: str, item_type: ItemType, total_qty: int, expires_in_minutes: int
) -> Batch:
    batch_id = f"batch_{store.next_batch_id}"
    store.next_batch_id += 1
    created_at = clock.now()
    batch = Batch(
        id=batch_id,
        donor_id=donor_id,
        item_type=item_type,
        total_qty=total_qty,
        remaining_qty=total_qty,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=expires_in_minutes),
        status=BatchStatus.OPEN,
        status_reason=None,
    )
    store.batches[batch_id] = batch
    log_event(
        EventType.BATCH_CREATED,
        EventSeverity.SUCCESS,
        f"Batch {batch_id} created.",
        {"batchId": batch_id, "donorId": donor_id},
    )
    return batch


@router.post("/batches", status_code=201)
def create_batch(request: CreateBatchRequest) -> dict:
    try:
        item_type = ItemType(request.item_type)
    except ValueError:
        raise ApiError(400, "INVALID_ITEM_TYPE", "The itemType is not supported.")

    if request.total_qty <= 0:
        raise ApiError(400, "INVALID_QTY", "totalQty must be greater than zero.")

    with store.lock:
        if request.donor_id not in store.donors:
            raise ApiError(404, "DONOR_NOT_FOUND", "The donor does not exist.")

        batch = _create_batch(
            request.donor_id,
            item_type,
            request.total_qty,
            request.expires_in_minutes,
        )
        return {"batch": _json(batch)}


@router.post("/batches/{batch_id}/dispatch")
def dispatch_batch(batch_id: str, request: EmptyRequest) -> dict:
    with store.lock:
        batch = store.batches.get(batch_id)
        if batch is None:
            raise ApiError(404, "BATCH_NOT_FOUND", "The batch does not exist.")
        if batch.status == BatchStatus.SPOILED:
            raise ApiError(409, "BATCH_ALREADY_SPOILED", "The batch has spoiled.")

        created_shipments, rejections = split_batch(batch)
        return {
            "batch": {
                "id": batch.id,
                "remainingQty": batch.remaining_qty,
                "status": _json(batch)["status"],
                "statusReason": batch.status_reason,
            },
            "createdShipments": [_json(shipment) for shipment in created_shipments],
            "rejections": rejections,
        }


@router.post("/shipments/{shipment_id}/claim")
def claim_shipment(shipment_id: str, request: ClaimShipmentRequest) -> dict:
    with store.lock:
        shipment = store.shipments.get(shipment_id)
        if shipment is None:
            raise ApiError(
                404, "SHIPMENT_NOT_FOUND", "The shipment does not exist."
            )
        if (
            shipment.status != "CREATED"
            or shipment.rider_id != request.rider_id
        ):
            raise ApiError(
                409,
                "NOT_CLAIMABLE",
                "The shipment is not available for this rider to claim.",
            )
        batch = store.batches.get(shipment.batch_id)
        if batch is None:
            raise ApiError(409, "NOT_CLAIMABLE", "The shipment batch is unavailable.")

        now = clock.now()
        lease_expires_at, ttl_seconds = lease_expiry(batch, now)
        shipment.status = "CLAIMED"
        shipment.lease_expires_at = lease_expires_at
        log_event(
            EventType.SHIPMENT_CLAIMED,
            EventSeverity.INFO,
            f"Rider {request.rider_id} claimed shipment {shipment_id}.",
            {
                "batchId": shipment.batch_id,
                "shipmentId": shipment.id,
                "riderId": request.rider_id,
            },
        )
        return {
            "shipment": {
                "id": shipment.id,
                "status": shipment.status,
                "riderId": shipment.rider_id,
                "leaseExpiresAt": _json(shipment)["leaseExpiresAt"],
            },
            "leaseTtlSeconds": ttl_seconds,
        }


@router.post("/riders/{rider_id}/heartbeat")
def rider_heartbeat(rider_id: str, location: Location) -> dict:
    with store.lock:
        rider = store.riders.get(rider_id)
        if rider is None:
            raise ApiError(404, "RIDER_NOT_FOUND", "The rider does not exist.")

        if rider_id in store.simulated_unresponsive:
            return {
                "rider": {
                    "id": rider.id,
                    "status": rider.status,
                    "lastHeartbeatAt": _json(rider)["lastHeartbeatAt"],
                },
                "extendedShipmentIds": [],
                "ignored": True,
            }

        now = clock.now()
        rider.location = location
        rider.last_heartbeat_at = now
        extended_shipment_ids: list[str] = []
        for shipment_id in rider.active_shipment_ids:
            shipment = store.shipments.get(shipment_id)
            if shipment is None or shipment.status not in (
                "CLAIMED",
                "IN_TRANSIT",
                "REROUTED",
            ):
                continue
            batch = store.batches.get(shipment.batch_id)
            if batch is None:
                continue
            extend_shipment_lease(shipment, batch, now)
            extended_shipment_ids.append(shipment.id)

        return {
            "rider": {
                "id": rider.id,
                "status": rider.status,
                "lastHeartbeatAt": _json(rider)["lastHeartbeatAt"],
            },
            "extendedShipmentIds": extended_shipment_ids,
        }


@router.post("/shipments/{shipment_id}/pickup")
def pickup_shipment(shipment_id: str, request: EmptyRequest) -> dict:
    with store.lock:
        shipment = store.shipments.get(shipment_id)
        if shipment is None:
            raise ApiError(
                404, "SHIPMENT_NOT_FOUND", "The shipment does not exist."
            )
        if shipment.status not in ("CLAIMED", "REROUTED"):
            raise ApiError(
                409,
                "INVALID_TRANSITION",
                "Only a claimed shipment can be picked up.",
            )
        shipment.status = "IN_TRANSIT"
        log_event(
            EventType.PICKED_UP,
            EventSeverity.INFO,
            f"Shipment {shipment_id} picked up and is in transit.",
            {
                "batchId": shipment.batch_id,
                "shipmentId": shipment.id,
                "riderId": shipment.rider_id,
            },
        )
        return {
            "shipment": {
                "id": shipment.id,
                "status": shipment.status,
                "leaseExpiresAt": _json(shipment)["leaseExpiresAt"],
            }
        }


@router.post("/shipments/{shipment_id}/deliver")
def deliver_shipment(shipment_id: str, request: EmptyRequest) -> dict:
    with store.lock:
        shipment = store.shipments.get(shipment_id)
        if shipment is None:
            raise ApiError(
                404, "SHIPMENT_NOT_FOUND", "The shipment does not exist."
            )
        if shipment.status == "SPOILED":
            raise ApiError(
                409, "SHIPMENT_SPOILED", "The shipment has spoiled."
            )
        if shipment.status not in ("IN_TRANSIT", "REROUTED"):
            raise ApiError(
                409,
                "INVALID_TRANSITION",
                "Only an in-transit shipment can be delivered.",
            )
        shelter = store.shelters.get(shipment.shelter_id)
        batch = store.batches.get(shipment.batch_id)
        if shelter is None or batch is None:
            raise ApiError(
                409, "INVALID_TRANSITION", "The shipment's destination is unavailable."
            )

        shipment.status = "DELIVERED"
        shipment.lease_expires_at = None
        shelter.demand_remaining = max(0, shelter.demand_remaining - shipment.qty)
        shelter.reserved_qty = max(0, shelter.reserved_qty - shipment.qty)
        rider = store.riders.get(shipment.rider_id)
        if rider is not None:
            if shipment_id in rider.active_shipment_ids:
                rider.active_shipment_ids.remove(shipment_id)
            if (
                not rider.active_shipment_ids
                and rider.id not in store.simulated_unresponsive
            ):
                rider.status = "AVAILABLE"

        batch_shipments = [
            item
            for item in store.shipments.values()
            if item.batch_id == batch.id
        ]
        if batch.remaining_qty > 0:
            batch.status = (
                BatchStatus.PARTIALLY_ASSIGNED
                if batch_shipments
                else BatchStatus.OPEN
            )
        elif all(
            item.status in ("DELIVERED", "EXPIRED_LEASE")
            for item in batch_shipments
        ):
            batch.status = BatchStatus.COMPLETED
        else:
            batch.status = BatchStatus.FULLY_ASSIGNED

        log_event(
            EventType.DELIVERED,
            EventSeverity.SUCCESS,
            f"Shipment {shipment_id} delivered to {shelter.id}.",
            {
                "batchId": batch.id,
                "shipmentId": shipment.id,
                "riderId": shipment.rider_id,
                "shelterId": shelter.id,
            },
        )
        return {
            "shipment": {"id": shipment.id, "status": shipment.status},
            "shelter": {
                "id": shelter.id,
                "demandRemaining": shelter.demand_remaining,
            },
            "batch": {
                "id": batch.id,
                "status": _json(batch)["status"],
            },
        }


@router.post("/shelters/{shelter_id}")
def update_shelter(shelter_id: str, request: dict[str, Any]) -> dict:
    allowed_fields = {"demandRemaining", "isOpen", "resources"}
    unknown_fields = set(request) - allowed_fields
    if unknown_fields:
        field = sorted(unknown_fields)[0]
        raise ApiError(400, "INVALID_FIELD", f"Unsupported shelter field: {field}.")

    parsed_resources: list[Resource] | None = None
    if "demandRemaining" in request:
        demand = request["demandRemaining"]
        if isinstance(demand, bool) or not isinstance(demand, int) or demand < 0:
            raise ApiError(
                400,
                "INVALID_FIELD",
                "demandRemaining must be a non-negative integer.",
            )
    if "isOpen" in request and not isinstance(request["isOpen"], bool):
        raise ApiError(400, "INVALID_FIELD", "isOpen must be a boolean.")
    if "resources" in request:
        resources = request["resources"]
        if not isinstance(resources, list):
            raise ApiError(400, "INVALID_FIELD", "resources must be a list.")
        try:
            parsed_resources = [Resource(resource) for resource in resources]
        except (TypeError, ValueError):
            raise ApiError(
                400,
                "INVALID_FIELD",
                "resources must contain supported resource values.",
            )

    with store.lock:
        shelter = store.shelters.get(shelter_id)
        if shelter is None:
            raise ApiError(404, "SHELTER_NOT_FOUND", "The shelter does not exist.")

        previous_resources = {
            Resource(resource) for resource in shelter.resources
        }
        if "demandRemaining" in request:
            shelter.demand_remaining = request["demandRemaining"]
        if "isOpen" in request:
            shelter.is_open = request["isOpen"]
        if parsed_resources is not None:
            shelter.resources = parsed_resources
        removed_resources = previous_resources - {
            Resource(resource) for resource in shelter.resources
        }
        log_event(
            EventType.SHELTER_UPDATED,
            EventSeverity.INFO,
            f"Shelter {shelter_id} updated.",
            {"shelterId": shelter_id},
        )
        rerouted, at_risk = reroute_shelter_shipments(
            shelter_id, removed_resources
        )
        shelter_response = {
            "id": shelter.id,
            "demandRemaining": shelter.demand_remaining,
            "isOpen": shelter.is_open,
            "resources": [Resource(resource).value for resource in shelter.resources],
        }
        return {
            "shelter": shelter_response,
            "rerouted": rerouted,
            "atRisk": at_risk,
        }


@router.post("/sim/clock")
def advance_clock(request: AdvanceClockRequest) -> dict:
    with store.lock:
        clock.advance(request.advance_minutes)
        tick_summary = run_tick()
        log_event(
            EventType.CLOCK_ADVANCED,
            EventSeverity.INFO,
            f"Simulation clock advanced by {request.advance_minutes} minutes.",
        )
        return {
            "clock": {
                "now": _timestamp(),
                "offsetMinutes": clock.offset_minutes(),
            },
            "tickSummary": tick_summary,
        }


@router.post("/sim/rider/{rider_id}/unresponsive")
def set_rider_unresponsive(
    rider_id: str, request: RiderUnresponsiveRequest
) -> dict:
    with store.lock:
        rider = store.riders.get(rider_id)
        if rider is None:
            raise ApiError(404, "RIDER_NOT_FOUND", "The rider does not exist.")
        if request.unresponsive:
            store.simulated_unresponsive.add(rider_id)
            rider.status = "UNRESPONSIVE"
            log_event(
                EventType.RIDER_UNRESPONSIVE,
                EventSeverity.WARNING,
                f"Rider {rider_id} marked unresponsive.",
                {"riderId": rider_id},
            )
        else:
            store.simulated_unresponsive.discard(rider_id)
            if rider.active_shipment_ids:
                rider.status = "BUSY"
            else:
                rider.status = "AVAILABLE"
            log_event(
                EventType.RIDER_UNRESPONSIVE,
                EventSeverity.INFO,
                f"Rider {rider_id} restored to responsive status.",
                {"riderId": rider_id},
            )
        return {"rider": {"id": rider.id, "status": rider.status}}


@router.post("/sim/scenario/handout", status_code=201)
def handout_scenario() -> dict:
    # STUB: replaced in phase Bx
    return {
        "batch": {
            "id": "batch_2",
            "totalQty": 180,
            "expiresAt": _timestamp(75),
        }
    }


@router.post("/sim/scenario/tight-expiry", status_code=201)
def tight_expiry_scenario() -> dict:
    # STUB: replaced in phase Bx
    return {
        "batch": {
            "id": "batch_3",
            "totalQty": 60,
            "expiresAt": _timestamp(2),
        }
    }


@router.post("/sim/scenario/incompatible", status_code=201)
def incompatible_scenario() -> dict:
    # STUB: replaced in phase Bx
    return {
        "batch": {
            "id": "batch_4",
            "itemType": "infant_formula",
            "totalQty": 30,
            "status": "OPEN",
        }
    }


@router.post("/sim/reset")
def reset_simulation() -> dict[str, bool]:
    with store.lock:
        store.reset()
        log_event(
            EventType.RESET,
            EventSeverity.INFO,
            "Simulation reset to seed data.",
        )
    return {"ok": True}
