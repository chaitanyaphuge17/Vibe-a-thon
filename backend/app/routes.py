from datetime import timedelta

from fastapi import APIRouter

from app import clock, store
from app.events import log_event
from app.matcher import split_batch
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

        batch_id = f"batch_{store.next_batch_id}"
        store.next_batch_id += 1
        created_at = clock.now()
        batch = Batch(
            id=batch_id,
            donor_id=request.donor_id,
            item_type=item_type,
            total_qty=request.total_qty,
            remaining_qty=request.total_qty,
            created_at=created_at,
            expires_at=created_at + timedelta(minutes=request.expires_in_minutes),
            status=BatchStatus.OPEN,
            status_reason=None,
        )
        store.batches[batch_id] = batch
        log_event(
            EventType.BATCH_CREATED,
            EventSeverity.SUCCESS,
            f"Batch {batch_id} created.",
            {"batchId": batch_id, "donorId": request.donor_id},
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
    # STUB: replaced in phase Bx
    return {
        "shipment": {
            "id": shipment_id,
            "status": "CLAIMED",
            "riderId": request.rider_id,
            "leaseExpiresAt": _timestamp(5),
        },
        "leaseTtlSeconds": 300,
    }


@router.post("/riders/{rider_id}/heartbeat")
def rider_heartbeat(rider_id: str, location: Location) -> dict:
    # STUB: replaced in phase Bx
    return {
        "rider": {
            "id": rider_id,
            "status": "BUSY",
            "lastHeartbeatAt": _timestamp(),
        },
        "extendedShipmentIds": ["ship_1"],
    }


@router.post("/shipments/{shipment_id}/pickup")
def pickup_shipment(shipment_id: str, request: EmptyRequest) -> dict:
    # STUB: replaced in phase Bx
    return {
        "shipment": {
            "id": shipment_id,
            "status": "IN_TRANSIT",
            "leaseExpiresAt": _timestamp(5),
        }
    }


@router.post("/shipments/{shipment_id}/deliver")
def deliver_shipment(shipment_id: str, request: EmptyRequest) -> dict:
    # STUB: replaced in phase Bx
    return {
        "shipment": {"id": shipment_id, "status": "DELIVERED"},
        "shelter": {"id": "shelter_a", "demandRemaining": 10},
        "batch": {"id": "batch_1", "status": "PARTIALLY_ASSIGNED"},
    }


@router.post("/shelters/{shelter_id}")
def update_shelter(shelter_id: str, request: ShelterUpdateRequest) -> dict:
    # STUB: replaced in phase Bx
    return {
        "shelter": {
            "id": shelter_id,
            "demandRemaining": 0,
            "isOpen": True,
            "resources": ["clean_water", "cooking_fuel"],
        },
        "rerouted": [
            {
                "shipmentId": "ship_1",
                "fromShelterId": shelter_id,
                "toShelterId": "shelter_c",
            }
        ],
        "atRisk": [
            {
                "shipmentId": "ship_2",
                "reason": "No open compatible shelter reachable before expiry.",
            }
        ],
    }


@router.post("/sim/clock")
def advance_clock(request: AdvanceClockRequest) -> dict:
    # STUB: replaced in phase Bx
    return {
        "clock": {
            "now": _timestamp(request.advance_minutes),
            "offsetMinutes": clock.offset_minutes() + request.advance_minutes,
        },
        "tickSummary": {"leasesExpired": 1, "reassigned": 1, "spoiled": 0},
    }


@router.post("/sim/rider/{rider_id}/unresponsive")
def set_rider_unresponsive(
    rider_id: str, request: RiderUnresponsiveRequest
) -> dict:
    # STUB: replaced in phase Bx
    return {
        "rider": {
            "id": rider_id,
            "status": "UNRESPONSIVE" if request.unresponsive else "AVAILABLE",
        }
    }


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
