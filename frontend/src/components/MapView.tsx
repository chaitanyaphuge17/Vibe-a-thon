import { useEffect, useRef, type ReactNode } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import { DivIcon } from 'leaflet'
import type { Donor, Location, Rider, Shipment, Shelter, State } from '../types'
import { minutesAgo } from '../utils/time'
import { statusLabel } from '../utils/status'
import 'leaflet/dist/leaflet.css'

interface MapViewProps { state: State; now: string }

const markerIcon = (className: string, label: string): DivIcon => new DivIcon({ className: `map-marker ${className}`, html: `<span>${label}</span>`, iconSize: [34, 34], iconAnchor: [17, 17] })
const shipmentColor: Record<Shipment['status'], string> = {
  CREATED: '#3478b9', CLAIMED: '#3478b9', PICKED_UP: '#3478b9', IN_TRANSIT: '#687C45', DELIVERED: '#9ba59a',
  REROUTED: '#d77e1d', AT_RISK: '#F2A33A', EXPIRED_LEASE: '#D64545', SPOILED: '#D64545',
}

function BoundsController({ locations }: { locations: Location[] }): null {
  const map = useMap()
  const fitted = useRef(false)
  useEffect(() => {
    if (fitted.current || locations.length === 0) return
    map.fitBounds(locations.map(({ lat, lng }) => [lat, lng] as [number, number]), { padding: [42, 42], maxZoom: 14 })
    fitted.current = true
  }, [locations, map])
  return null
}

function MarkerPopup({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return <Popup><strong>{title}</strong><div className="map-popup__body">{children}</div></Popup>
}

function DonorMarker({ donor }: { donor: Donor }): JSX.Element {
  return <Marker position={[donor.location.lat, donor.location.lng]} icon={markerIcon('map-marker--donor', 'D')}><MarkerPopup title={donor.name}><span>Donor</span><code>{donor.id}</code></MarkerPopup></Marker>
}

function RiderMarker({ rider, now }: { rider: Rider; now: string }): JSX.Element {
  return <Marker position={[rider.location.lat, rider.location.lng]} icon={markerIcon(`map-marker--rider map-marker--${rider.status.toLowerCase()}`, 'R')}><MarkerPopup title={rider.name}><StatusLine status={rider.status} /><span>Capacity {rider.capacity}</span><span>Last seen {minutesAgo(rider.lastHeartbeatAt, now)}</span></MarkerPopup></Marker>
}

function ShelterMarker({ shelter }: { shelter: Shelter }): JSX.Element {
  return <Marker position={[shelter.location.lat, shelter.location.lng]} icon={markerIcon(`map-marker--shelter ${shelter.isOpen ? '' : 'map-marker--closed'}`, String(shelter.demandRemaining))}><MarkerPopup title={shelter.name}><StatusLine status={shelter.isOpen ? 'OPEN' : 'CLOSED'} /><span>Demand remaining: {shelter.demandRemaining}</span><div className="popup-chips">{shelter.resources.map((resource) => <span className="resource-chip" key={resource}>{resource.replace(/_/g, ' ')}</span>)}</div></MarkerPopup></Marker>
}

function StatusLine({ status }: { status: string }): JSX.Element {
  return <span className="map-popup__status"><span className={`status-dot status-dot--${status.toLowerCase()}`} aria-hidden="true" />{statusLabel(status)}</span>
}

function ShipmentRoute({ shipment, state }: { shipment: Shipment; state: State }): JSX.Element | null {
  const donor = state.donors.find((item) => item.id === state.batches.find((batch) => batch.id === shipment.batchId)?.donorId)
  const shelter = state.shelters.find((item) => item.id === shipment.shelterId)
  if (!donor || !shelter) return null
  const positions: [number, number][] = [[donor.location.lat, donor.location.lng], [shelter.location.lat, shelter.location.lng]]
  const isDashed = shipment.status === 'AT_RISK'
  return <><Polyline positions={positions} pathOptions={{ color: shipmentColor[shipment.status], weight: shipment.status === 'DELIVERED' ? 2 : 4, opacity: shipment.status === 'DELIVERED' ? .45 : .8, dashArray: isDashed ? '8 8' : undefined }} /><RouteOriginal shipment={shipment} state={state} /></>
}

function RouteOriginal({ shipment, state }: { shipment: Shipment; state: State }): JSX.Element | null {
  if (shipment.status !== 'REROUTED' || !shipment.originalShelterId) return null
  const donor = state.donors.find((item) => item.id === state.batches.find((batch) => batch.id === shipment.batchId)?.donorId)
  const shelter = state.shelters.find((item) => item.id === shipment.originalShelterId)
  if (!donor || !shelter) return null
  return <Polyline positions={[[donor.location.lat, donor.location.lng], [shelter.location.lat, shelter.location.lng]]} pathOptions={{ color: '#73716c', weight: 2, dashArray: '4 7', opacity: .7 }} />
}

export function MapView({ state, now }: MapViewProps): JSX.Element {
  const locations = [...state.donors, ...state.riders, ...state.shelters].map((item) => item.location)
  return <section className="map-panel" aria-label="Live logistics map">
    <div className="map-heading"><div><p className="eyebrow">NETWORK MAP</p><h2>Live routes</h2></div><span className="map-heading__count">{state.shipments.length} shipments</span></div>
    <div className="map-wrap">
      <MapContainer center={[18.53, 73.86]} zoom={13} scrollWheelZoom className="map">
        <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <BoundsController locations={locations} />
        {state.donors.map((donor) => <DonorMarker donor={donor} key={donor.id} />)}
        {state.riders.map((rider) => <RiderMarker rider={rider} now={now} key={rider.id} />)}
        {state.shelters.map((shelter) => <ShelterMarker shelter={shelter} key={shelter.id} />)}
        {state.shipments.map((shipment) => <ShipmentRoute shipment={shipment} state={state} key={shipment.id} />)}
      </MapContainer>
      <div className="map-legend" aria-label="Map legend">
        <span><i className="legend-line legend-line--blue" /> Allocated</span><span><i className="legend-line legend-line--green" /> In transit</span><span><i className="legend-line legend-line--orange" /> Rerouted</span><span><i className="legend-line legend-line--red" /> Failure</span>
      </div>
    </div>
  </section>
}
