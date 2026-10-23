from threading import RLock

from app import clock
from app.events import events, reset_events
from app.models import Batch, Donor, Rider, Shelter, Shipment
from app.seed import seed_entities


lock: RLock = clock.state_lock
donors: dict[str, Donor] = {}
riders: dict[str, Rider] = {}
shelters: dict[str, Shelter] = {}
batches: dict[str, Batch] = {}
shipments: dict[str, Shipment] = {}
simulated_unresponsive: set[str] = set()
next_batch_id = 1
next_shipment_id = 1


def reset() -> None:
    global donors, riders, shelters, batches, shipments
    global next_batch_id, next_shipment_id
    with lock:
        clock.reset()
        reset_events()
        donors, riders, shelters = seed_entities()
        batches = {}
        shipments = {}
        simulated_unresponsive.clear()
        next_batch_id = 1
        next_shipment_id = 1


reset()
