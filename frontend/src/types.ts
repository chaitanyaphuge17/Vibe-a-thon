export type ItemType = 'cooked_meal' | 'raw_ration_kit' | 'infant_formula' | 'short_life_medicine'
export type Resource = 'clean_water' | 'cooking_fuel'
export type BatchStatus = 'OPEN' | 'PARTIALLY_ASSIGNED' | 'FULLY_ASSIGNED' | 'AT_RISK' | 'SPOILED' | 'COMPLETED'
export type ShipmentStatus = 'CREATED' | 'CLAIMED' | 'PICKED_UP' | 'IN_TRANSIT' | 'DELIVERED' | 'EXPIRED_LEASE' | 'REROUTED' | 'AT_RISK' | 'SPOILED'
export type RiderStatus = 'AVAILABLE' | 'BUSY' | 'UNRESPONSIVE'
export type EventSeverity = 'info' | 'success' | 'warning' | 'error'
export type EventType = 'BATCH_CREATED' | 'BATCH_REJECTED' | 'SHIPMENT_CREATED' | 'SHIPMENT_CLAIMED' | 'PICKED_UP' | 'DELIVERED' | 'LEASE_EXPIRED' | 'REASSIGNED' | 'SHELTER_UPDATED' | 'REROUTED' | 'AT_RISK' | 'SPOILED' | 'RIDER_UNRESPONSIVE' | 'CLOCK_ADVANCED' | 'RESET'

export interface Location { lat: number; lng: number }
export interface Donor { id: string; name: string; location: Location }
export interface Rider { id: string; name: string; location: Location; capacity: number; status: RiderStatus; lastHeartbeatAt: string; activeShipmentIds: string[] }
export interface Shelter { id: string; name: string; location: Location; demandRemaining: number; reservedQty: number; isOpen: boolean; resources: Resource[] }
export interface Batch { id: string; donorId: string; itemType: ItemType; totalQty: number; remainingQty: number; createdAt: string; expiresAt: string; status: BatchStatus; statusReason: string | null }
export interface Shipment { id: string; batchId: string; riderId: string | null; shelterId: string; originalShelterId: string | null; qty: number; status: ShipmentStatus; etaPickupAt: string; etaDeliveryAt: string; leaseExpiresAt: string | null; createdAt: string }
export interface Event { id: string; at: string; type: EventType; severity: EventSeverity; message: string; refs: { batchId?: string; shipmentId?: string; riderId?: string; shelterId?: string } }
export interface Clock { now: string; offsetMinutes: number }
export interface State { clock: Clock; donors: Donor[]; riders: Rider[]; shelters: Shelter[]; batches: Batch[]; shipments: Shipment[]; events: Event[] }
export type Rules = Record<ItemType, Resource[]>

export interface CreateBatchRequest { donorId: string; itemType: ItemType; totalQty: number; expiresInMinutes: number }
export interface CreateBatchResponse { batch: Batch }
export interface DispatchResponse { batch: Pick<Batch, 'id' | 'remainingQty' | 'status'> & Partial<Pick<Batch, 'statusReason'>>; createdShipments: Shipment[]; rejections: Array<{ shelterId?: string; riderId?: string; reason: string }> }
export interface ClaimResponse { shipment: Pick<Shipment, 'id' | 'status' | 'riderId' | 'leaseExpiresAt'>; leaseTtlSeconds: number }
export interface HeartbeatRequest { lat: number; lng: number }
export interface HeartbeatResponse { rider: Pick<Rider, 'id' | 'status' | 'lastHeartbeatAt'>; extendedShipmentIds: string[]; ignored?: boolean }
export interface PickupResponse { shipment: Pick<Shipment, 'id' | 'status' | 'leaseExpiresAt'> }
export interface DeliverResponse { shipment: Pick<Shipment, 'id' | 'status'>; shelter: Pick<Shelter, 'id' | 'demandRemaining'>; batch: Pick<Batch, 'id' | 'status'> }
export interface ShelterUpdateRequest { demandRemaining?: number; isOpen?: boolean; resources?: Resource[] }
export interface ShelterUpdateResponse { shelter: Pick<Shelter, 'id' | 'demandRemaining' | 'isOpen' | 'resources'>; rerouted: Array<{ shipmentId: string; fromShelterId: string; toShelterId: string }>; atRisk: Array<{ shipmentId: string; reason: string }> }
export interface AdvanceClockRequest { advanceMinutes: number }
export interface AdvanceClockResponse { clock: Clock; tickSummary: { leasesExpired: number; reassigned: number; spoiled: number } }
export interface UnresponsiveRequest { unresponsive: boolean }
export interface UnresponsiveResponse { rider: Pick<Rider, 'id' | 'status'> }
export interface ScenarioBatchResponse { batch: Batch }
export interface ResetResponse { ok: true }
