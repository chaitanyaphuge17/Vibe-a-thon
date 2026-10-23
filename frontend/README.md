# FreshRelay frontend

FreshRelay is a React 18 and TypeScript logistics operations console for dispatching perishable surplus through donors, volunteer riders, and shelters.

## Requirements

- Node.js 18 or newer
- npm 9 or newer

## Install

From this directory:

```bash
npm install
```

## Run locally

```bash
npm run dev
```

Vite prints the local development URL in the terminal. The dashboard polls the configured backend state every two seconds.

## Build

```bash
npm run build
```

The production bundle is written to `dist/`.

## Environment

Copy `.env.example` to `.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK=true
```

- `VITE_API_BASE_URL` is the backend origin. Requests are made under the contract's `/api` base path.
- `VITE_USE_MOCK=true` loads the handout state from `src/mock-state.json`. Write actions show local toasts and do not call the network.
- `VITE_USE_MOCK=false` sends requests to the real backend configured by `VITE_API_BASE_URL`.

Restart the Vite development server after changing environment variables.

## Views

- **Dashboard** shows batches, the live Leaflet map, event log, shipments, and judge simulation controls.
- **Rider view** provides rider selection, shipment actions, lease countdowns, heartbeat controls, and failure banners.

## Screenshots

![](./screenshots/dashboard.png)

![](./screenshots/rider-view.png)
