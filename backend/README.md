# FreshRelay Backend

FreshRelay is an in-memory FastAPI dispatch API. Run all commands in this
directory.

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

Fixed port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use the deployment-provided `PORT` in a POSIX shell:

```bash
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

Swagger UI is available at `/docs`.

## Test

```bash
python -m pytest -q tests
```

For live judge-scenario checks, start the server and run:

```bash
python smoke_test.py
```

Set `BASE_URL` to target a different running instance; the default is
`http://127.0.0.1:8000`. The script resets the simulation before each scenario.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/state` | Clock, donors, riders, shelters, batches, shipments, and recent events |
| GET | `/api/rules` | Item compatibility requirements |
| GET | `/api/events?since=<eventId>` | Recent events, optionally after an event ID |
| POST | `/api/batches` | Create a donor batch |
| POST | `/api/batches/{id}/dispatch` | Match and split a batch into shipments |
| POST | `/api/shipments/{id}/claim` | Claim an assigned shipment and start its lease |
| POST | `/api/riders/{id}/heartbeat` | Update rider location and renew active shipment leases |
| POST | `/api/shipments/{id}/pickup` | Move a claimed shipment into transit |
| POST | `/api/shipments/{id}/deliver` | Deliver an in-transit shipment |
| POST | `/api/shelters/{id}` | Partially update shelter demand, open state, or resources |
| POST | `/api/sim/clock` | Advance simulated time and run a tick |
| POST | `/api/sim/rider/{id}/unresponsive` | Set or clear a rider's simulated unresponsive flag |
| POST | `/api/sim/scenario/handout` | Create the handout batch |
| POST | `/api/sim/scenario/tight-expiry` | Create a batch that cannot arrive before expiry |
| POST | `/api/sim/scenario/incompatible` | Create an infant-formula batch without a nearby compatible shelter |
| POST | `/api/sim/reset` | Restore seed state, clock, and event IDs |

## Assumptions

- Rider travel speed is **25 km/h**, using straight-line haversine distance.
- Matching reserves a **10-minute safety buffer** before a batch expires.
- A shipment lease is **20% of the seconds remaining until batch expiry**, capped
  at **300 seconds** (and never below zero).
- State is held in process memory and resets when the process restarts.
