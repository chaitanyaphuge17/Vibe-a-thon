from datetime import datetime, timedelta

from app.models import Batch, Shipment


MAX_LEASE_SECONDS = 300


def lease_ttl_seconds(batch: Batch, now: datetime) -> int:
    seconds_until_expiry = (batch.expires_at - now).total_seconds()
    return max(0, min(MAX_LEASE_SECONDS, int(seconds_until_expiry * 0.2)))


def lease_expiry(batch: Batch, now: datetime) -> tuple[datetime, int]:
    ttl_seconds = lease_ttl_seconds(batch, now)
    return now + timedelta(seconds=ttl_seconds), ttl_seconds


def extend_shipment_lease(
    shipment: Shipment, batch: Batch, now: datetime
) -> int:
    expires_at, ttl_seconds = lease_expiry(batch, now)
    shipment.lease_expires_at = expires_at
    return ttl_seconds
