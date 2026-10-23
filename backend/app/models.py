from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


def format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )

    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return format_timestamp(value)
        return value


class ItemType(str, Enum):
    COOKED_MEAL = "cooked_meal"
    RAW_RATION_KIT = "raw_ration_kit"
    INFANT_FORMULA = "infant_formula"
    SHORT_LIFE_MEDICINE = "short_life_medicine"


class Resource(str, Enum):
    CLEAN_WATER = "clean_water"
    COOKING_FUEL = "cooking_fuel"


class BatchStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_ASSIGNED = "PARTIALLY_ASSIGNED"
    FULLY_ASSIGNED = "FULLY_ASSIGNED"
    AT_RISK = "AT_RISK"
    SPOILED = "SPOILED"
    COMPLETED = "COMPLETED"


class ShipmentStatus(str, Enum):
    CREATED = "CREATED"
    CLAIMED = "CLAIMED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    EXPIRED_LEASE = "EXPIRED_LEASE"
    REROUTED = "REROUTED"
    AT_RISK = "AT_RISK"
    SPOILED = "SPOILED"


class RiderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    UNRESPONSIVE = "UNRESPONSIVE"


class EventSeverity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class EventType(str, Enum):
    BATCH_CREATED = "BATCH_CREATED"
    BATCH_REJECTED = "BATCH_REJECTED"
    SHIPMENT_CREATED = "SHIPMENT_CREATED"
    SHIPMENT_CLAIMED = "SHIPMENT_CLAIMED"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    REASSIGNED = "REASSIGNED"
    SHELTER_UPDATED = "SHELTER_UPDATED"
    REROUTED = "REROUTED"
    AT_RISK = "AT_RISK"
    SPOILED = "SPOILED"
    RIDER_UNRESPONSIVE = "RIDER_UNRESPONSIVE"
    CLOCK_ADVANCED = "CLOCK_ADVANCED"
    RESET = "RESET"


class Location(CamelModel):
    lat: float
    lng: float


class Donor(CamelModel):
    id: str
    name: str
    location: Location


class Rider(CamelModel):
    id: str
    name: str
    location: Location
    capacity: int
    status: RiderStatus
    last_heartbeat_at: datetime
    active_shipment_ids: list[str]


class Shelter(CamelModel):
    id: str
    name: str
    location: Location
    demand_remaining: int
    reserved_qty: int
    is_open: bool
    resources: list[Resource]


class Batch(CamelModel):
    id: str
    donor_id: str
    item_type: ItemType
    total_qty: int
    remaining_qty: int
    created_at: datetime
    expires_at: datetime
    status: BatchStatus
    status_reason: str | None


class Shipment(CamelModel):
    id: str
    batch_id: str
    rider_id: str
    shelter_id: str
    original_shelter_id: str | None
    qty: int
    status: ShipmentStatus
    eta_pickup_at: datetime
    eta_delivery_at: datetime
    lease_expires_at: datetime | None
    created_at: datetime


class Event(CamelModel):
    id: str
    at: datetime
    type: EventType
    severity: EventSeverity
    message: str
    refs: dict[str, str]
