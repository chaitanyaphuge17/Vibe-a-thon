import mockState from './mock-state.json'
import type { AdvanceClockRequest, AdvanceClockResponse, Batch, ClaimResponse, CreateBatchRequest, CreateBatchResponse, DeliverResponse, DispatchResponse, Event, HeartbeatRequest, HeartbeatResponse, PickupResponse, ResetResponse, Rules, ScenarioBatchResponse, ShelterUpdateRequest, ShelterUpdateResponse, State, UnresponsiveRequest, UnresponsiveResponse } from './types'

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const mock = mockState as State

function mockNotice(message: string): void {
  window.dispatchEvent(new CustomEvent('freshrelay:toast', { detail: { message, tone: 'info' } }))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null
    throw new Error(body?.error?.message || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const getState = (): Promise<State> => useMock ? Promise.resolve(mock) : request<State>('/api/state')
export const getRules = (): Promise<Rules> => useMock ? Promise.resolve({ cooked_meal: [], short_life_medicine: [], raw_ration_kit: ['cooking_fuel'], infant_formula: ['clean_water'] }) : request<Rules>('/api/rules')
export const getEvents = (since?: string): Promise<{ events: Event[] }> => useMock ? Promise.resolve({ events: mock.events }) : request<{ events: Event[] }>(`/api/events${since ? `?since=${encodeURIComponent(since)}` : ''}`)
export const createBatch = (body: CreateBatchRequest): Promise<CreateBatchResponse> => useMock ? (mockNotice('Mock: batch creation simulated'), Promise.resolve({ batch: mock.batches[0] })) : request<CreateBatchResponse>('/api/batches', { method: 'POST', body: JSON.stringify(body) })
export const dispatchBatch = (id: string): Promise<DispatchResponse> => useMock ? (mockNotice('Mock: dispatch simulated'), Promise.resolve({ batch: { id, remainingQty: 20, status: 'PARTIALLY_ASSIGNED' }, createdShipments: mock.shipments, rejections: [] })) : request<DispatchResponse>(`/api/batches/${encodeURIComponent(id)}/dispatch`, { method: 'POST', body: '{}' })
export const claimShipment = (id: string): Promise<ClaimResponse> => useMock ? (mockNotice('Mock: shipment claim simulated'), Promise.resolve({ shipment: { id, status: 'CLAIMED', riderId: 'rider_1', leaseExpiresAt: null }, leaseTtlSeconds: 300 })) : request<ClaimResponse>(`/api/shipments/${encodeURIComponent(id)}/claim`, { method: 'POST', body: '{}' })
export const heartbeatRider = (id: string, body: HeartbeatRequest): Promise<HeartbeatResponse> => useMock ? (mockNotice('Mock: rider heartbeat simulated'), Promise.resolve({ rider: { id, status: 'AVAILABLE', lastHeartbeatAt: mock.clock.now }, extendedShipmentIds: [] })) : request<HeartbeatResponse>(`/api/riders/${encodeURIComponent(id)}/heartbeat`, { method: 'POST', body: JSON.stringify(body) })
export const pickupShipment = (id: string): Promise<PickupResponse> => useMock ? (mockNotice('Mock: pickup simulated'), Promise.resolve({ shipment: { id, status: 'PICKED_UP', leaseExpiresAt: null } })) : request<PickupResponse>(`/api/shipments/${encodeURIComponent(id)}/pickup`, { method: 'POST', body: '{}' })
export const deliverShipment = (id: string): Promise<DeliverResponse> => useMock ? (mockNotice('Mock: delivery simulated'), Promise.resolve({ shipment: { id, status: 'DELIVERED' }, shelter: { id: 'shelter_a', demandRemaining: 0 }, batch: { id: 'batch_1', status: 'COMPLETED' } })) : request<DeliverResponse>(`/api/shipments/${encodeURIComponent(id)}/deliver`, { method: 'POST', body: '{}' })
export const updateShelter = (id: string, body: ShelterUpdateRequest): Promise<ShelterUpdateResponse> => useMock ? (mockNotice('Mock: shelter update simulated'), Promise.resolve({ shelter: { id, demandRemaining: body.demandRemaining ?? 50, isOpen: body.isOpen ?? true, resources: body.resources ?? ['clean_water', 'cooking_fuel'] }, rerouted: [], atRisk: [] })) : request<ShelterUpdateResponse>(`/api/shelters/${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify(body) })
export const advanceClock = (body: AdvanceClockRequest): Promise<AdvanceClockResponse> => useMock ? (mockNotice('Mock: clock advance simulated'), Promise.resolve({ clock: { ...mock.clock, offsetMinutes: mock.clock.offsetMinutes + body.advanceMinutes }, tickSummary: { leasesExpired: 0, reassigned: 0, spoiled: 0 } })) : request<AdvanceClockResponse>('/api/sim/clock', { method: 'POST', body: JSON.stringify(body) })
export const setRiderUnresponsive = (id: string, body: UnresponsiveRequest): Promise<UnresponsiveResponse> => useMock ? (mockNotice('Mock: rider status simulated'), Promise.resolve({ rider: { id, status: body.unresponsive ? 'UNRESPONSIVE' : 'AVAILABLE' } })) : request<UnresponsiveResponse>(`/api/sim/rider/${encodeURIComponent(id)}/unresponsive`, { method: 'POST', body: JSON.stringify(body) })
export const createHandoutScenario = (): Promise<ScenarioBatchResponse> => useMock ? (mockNotice('Mock: handout scenario simulated'), Promise.resolve({ batch: mock.batches[0] })) : request<ScenarioBatchResponse>('/api/sim/scenario/handout', { method: 'POST', body: '{}' })
export const createTightExpiryScenario = (): Promise<ScenarioBatchResponse> => useMock ? (mockNotice('Mock: tight-expiry scenario simulated'), Promise.resolve({ batch: mock.batches[0] })) : request<ScenarioBatchResponse>('/api/sim/scenario/tight-expiry', { method: 'POST', body: '{}' })
export const createIncompatibleScenario = (): Promise<ScenarioBatchResponse> => useMock ? (mockNotice('Mock: incompatible scenario simulated'), Promise.resolve({ batch: mock.batches[0] })) : request<ScenarioBatchResponse>('/api/sim/scenario/incompatible', { method: 'POST', body: '{}' })
export const resetSimulation = (): Promise<ResetResponse> => useMock ? (mockNotice('Mock: simulation reset simulated'), Promise.resolve({ ok: true })) : request<ResetResponse>('/api/sim/reset', { method: 'POST', body: '{}' })
