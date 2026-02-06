import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import type { LatLngExpression } from "leaflet";

interface MapProps {
  /** Centre of the map. Defaults to Milton Keynes. */
  center?: LatLngExpression;
  /** Zoom level. Defaults to 12. */
  zoom?: number;
}

/** Default centre: Milton Keynes city centre */
const MILTON_KEYNES: LatLngExpression = [52.0406, -0.7594];

export default function Map({ center = MILTON_KEYNES, zoom = 12 }: MapProps) {
  return (
    <div className="h-full w-full overflow-hidden rounded-lg border border-gray-200">
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={center}>
          <Popup>Search location</Popup>
        </Marker>
      </MapContainer>
    </div>
  );
}
