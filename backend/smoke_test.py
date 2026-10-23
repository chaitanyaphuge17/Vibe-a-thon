import os
import sys
from collections import defaultdict
from typing import Callable

import httpx


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SECONDS = 10.0


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def reset(client: httpx.Client) -> None:
    response = client.post("/api/sim/reset")
    require(response.status_code == 200, f"reset returned {response.status_code}")


def handout_split(client: httpx.Client) -> None:
    reset(client)
    created = client.post("/api/sim/scenario/handout")
    require(created.status_code == 201, f"handout returned {created.status_code}")
    batch = created.json()["batch"]
    require(batch["totalQty"] == 180, "handout quantity was not 180")
    dispatched = client.post(f"/api/batches/{batch['id']}/dispatch", json={})
    require(dispatched.status_code == 200, f"dispatch returned {dispatched.status_code}")
    result = dispatched.json()
    shipments = result["createdShipments"]
    require(len(shipments) > 1, "handout did not split across multiple riders")

    state = client.get("/api/state")
    require(state.status_code == 200, f"state returned {state.status_code}")
    riders = {rider["id"]: rider for rider in state.json()["riders"]}
    shelters = {shelter["id"]: shelter for shelter in state.json()["shelters"]}
    by_shelter: dict[str, int] = defaultdict(int)
    for shipment in shipments:
        require(
            shipment["qty"] <= riders[shipment["riderId"]]["capacity"],
            f"{shipment['id']} exceeds rider capacity",
        )
        by_shelter[shipment["shelterId"]] += shipment["qty"]
    for shelter_id, total in by_shelter.items():
        require(
            total <= shelters[shelter_id]["demandRemaining"],
            f"shipments exceed demand at {shelter_id}",
        )


def tight_expiry(client: httpx.Client) -> None:
    reset(client)
    created = client.post("/api/sim/scenario/tight-expiry")
    require(created.status_code == 201, f"tight-expiry returned {created.status_code}")
    batch_id = created.json()["batch"]["id"]
    dispatched = client.post(f"/api/batches/{batch_id}/dispatch", json={})
    require(dispatched.status_code == 200, f"dispatch returned {dispatched.status_code}")
    batch = dispatched.json()["batch"]
    require(batch["status"] == "AT_RISK", "tight-expiry batch was not AT_RISK")
    require(bool(batch.get("statusReason")), "AT_RISK batch has no statusReason")
    require(not dispatched.json()["createdShipments"], "tight-expiry created shipments")


def unresponsive_reassignment(client: httpx.Client) -> None:
    reset(client)
    created = client.post(
        "/api/batches",
        json={
            "donorId": "donor_1",
            "itemType": "cooked_meal",
            "totalQty": 40,
            "expiresInMinutes": 60,
        },
    )
    require(created.status_code == 201, f"batch create returned {created.status_code}")
    batch_id = created.json()["batch"]["id"]
    dispatched = client.post(f"/api/batches/{batch_id}/dispatch", json={})
    require(dispatched.status_code == 200, f"dispatch returned {dispatched.status_code}")
    shipment = dispatched.json()["createdShipments"][0]
    rider_id = shipment["riderId"]
    claim = client.post(
        f"/api/shipments/{shipment['id']}/claim",
        json={"riderId": rider_id},
    )
    require(claim.status_code == 200, f"claim returned {claim.status_code}")
    flagged = client.post(
        f"/api/sim/rider/{rider_id}/unresponsive",
        json={"unresponsive": True},
    )
    require(flagged.status_code == 200, f"unresponsive toggle returned {flagged.status_code}")

    advanced = client.post("/api/sim/clock", json={"advanceMinutes": 6})
    require(advanced.status_code == 200, f"clock advance returned {advanced.status_code}")
    require(
        advanced.json()["tickSummary"]["leasesExpired"] >= 1,
        "tick did not expire the rider's lease",
    )
    state = client.get("/api/state").json()
    shipments = [item for item in state["shipments"] if item["batchId"] == batch_id]
    expired = next(item for item in shipments if item["id"] == shipment["id"])
    replacements = [
        item for item in shipments
        if item["id"] != shipment["id"] and item["riderId"] != rider_id
    ]
    require(expired["status"] == "EXPIRED_LEASE", "shipment did not expire its lease")
    require(replacements, "expired quantity was not reassigned to another rider")


def shelter_closes_mid_transit(client: httpx.Client) -> None:
    reset(client)
    created = client.post(
        "/api/batches",
        json={
            "donorId": "donor_1",
            "itemType": "cooked_meal",
            "totalQty": 20,
            "expiresInMinutes": 75,
        },
    )
    require(created.status_code == 201, f"batch create returned {created.status_code}")
    batch_id = created.json()["batch"]["id"]
    dispatched = client.post(f"/api/batches/{batch_id}/dispatch", json={})
    require(dispatched.status_code == 200, f"dispatch returned {dispatched.status_code}")
    shipment = dispatched.json()["createdShipments"][0]
    shipment_id = shipment["id"]
    source_shelter_id = shipment["shelterId"]
    claim = client.post(
        f"/api/shipments/{shipment_id}/claim",
        json={"riderId": shipment["riderId"]},
    )
    require(claim.status_code == 200, f"claim returned {claim.status_code}")
    pickup = client.post(f"/api/shipments/{shipment_id}/pickup", json={})
    require(pickup.status_code == 200, f"pickup returned {pickup.status_code}")

    update = client.post(
        f"/api/shelters/{source_shelter_id}",
        json={"isOpen": False},
    )
    require(update.status_code == 200, f"shelter update returned {update.status_code}")
    result = update.json()
    moved = any(
        item["shipmentId"] == shipment_id for item in result["rerouted"]
    )
    require(moved, "in-transit shipment was not rerouted")
    state = client.get("/api/state").json()
    current = next(item for item in state["shipments"] if item["id"] == shipment_id)
    require(current["shelterId"] != source_shelter_id, "shelter did not change")


def incompatible_shipment(client: httpx.Client) -> None:
    reset(client)
    created = client.post("/api/sim/scenario/incompatible")
    require(created.status_code == 201, f"incompatible scenario returned {created.status_code}")
    batch = created.json()["batch"]
    require(batch["itemType"] == "infant_formula", "scenario itemType is incorrect")
    dispatched = client.post(f"/api/batches/{batch['id']}/dispatch", json={})
    require(dispatched.status_code == 200, f"dispatch returned {dispatched.status_code}")
    result = dispatched.json()
    require(not result["createdShipments"], "incompatible batch created shipments")
    require(
        any("clean_water" in rejection["reason"] for rejection in result["rejections"]),
        "rejection did not explain the missing clean_water requirement",
    )


def run_case(
    client: httpx.Client, label: str, scenario: Callable[[httpx.Client], None]
) -> bool:
    try:
        scenario(client)
    except (AssertionError, httpx.HTTPError, KeyError, StopIteration, ValueError) as error:
        print(f"FAIL {label}: {error}")
        return False
    print(f"PASS {label}")
    return True


def main() -> int:
    cases = (
        ("handout split", handout_split),
        ("tight expiry", tight_expiry),
        ("unresponsive rider + fast-forward", unresponsive_reassignment),
        ("shelter close mid-transit", shelter_closes_mid_transit),
        ("incompatible shipment", incompatible_shipment),
    )
    try:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
            results = [run_case(client, label, scenario) for label, scenario in cases]
    except httpx.HTTPError as error:
        print(f"FAIL server connection ({BASE_URL}): {error}")
        return 1
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
