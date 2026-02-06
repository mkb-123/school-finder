import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Circle,
  Popup,
  useMap,
} from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import { Link } from "react-router-dom";

/** A school as returned by the API. */
export interface School {
  id: number;
  name: string;
  urn: string;
  type: string;
  council: string;
  address: string;
  postcode: string;
  lat: number | null;
  lng: number | null;
  distance_km: number | null;
  gender_policy: string;
  faith: string | null;
  age_range_from: number;
  age_range_to: number;
  ofsted_rating: string | null;
  ofsted_date: string | null;
  is_private: boolean;
  catchment_radius_km: number;
}

interface MapProps {
  center?: LatLngExpression;
  zoom?: number;
  schools?: School[];
  /** ID of the school whose catchment to highlight. */
  selectedSchoolId?: number | null;
  onSchoolSelect?: (id: number) => void;
}

const MILTON_KEYNES: LatLngExpression = [52.0406, -0.7594];

/** Map colour by Ofsted rating. */
function ofstedColor(rating: string | null): string {
  switch (rating) {
    case "Outstanding":
      return "#16a34a";
    case "Good":
      return "#2563eb";
    case "Requires improvement":
      return "#d97706";
    case "Inadequate":
      return "#dc2626";
    default:
      return "#6b7280";
  }
}

function ofstedLabel(rating: string | null): string {
  return rating ?? "Not rated";
}

/** Recenter the map when the center prop changes. */
function RecenterMap({ center }: { center: LatLngExpression }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center);
  }, [map, center]);
  return null;
}

export default function Map({
  center = MILTON_KEYNES,
  zoom = 12,
  schools = [],
  selectedSchoolId = null,
  onSchoolSelect,
}: MapProps) {
  const schoolsWithCoords = schools.filter(
    (s) => s.lat != null && s.lng != null,
  );

  return (
    <div className="h-full w-full overflow-hidden rounded-lg border border-gray-200">
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <RecenterMap center={center} />

        {/* Catchment circles (behind pins) */}
        {schoolsWithCoords.map((school) => {
          const isSelected = school.id === selectedSchoolId;
          if (!isSelected) return null;
          return (
            <Circle
              key={`catchment-${school.id}`}
              center={[school.lat!, school.lng!]}
              radius={school.catchment_radius_km * 1000}
              pathOptions={{
                color: ofstedColor(school.ofsted_rating),
                fillColor: ofstedColor(school.ofsted_rating),
                fillOpacity: 0.12,
                weight: 2,
                dashArray: "6 4",
              }}
            />
          );
        })}

        {/* School pins */}
        {schoolsWithCoords.map((school) => {
          const color = ofstedColor(school.ofsted_rating);
          const isSelected = school.id === selectedSchoolId;
          return (
            <CircleMarker
              key={school.id}
              center={[school.lat!, school.lng!]}
              radius={isSelected ? 10 : 7}
              pathOptions={{
                color: isSelected ? "#000" : color,
                fillColor: color,
                fillOpacity: 0.9,
                weight: isSelected ? 3 : 2,
              }}
              eventHandlers={{
                click: () => onSchoolSelect?.(school.id),
              }}
            >
              <Popup>
                <div className="min-w-[180px]">
                  <Link
                    to={
                      school.is_private
                        ? `/private-schools/${school.id}`
                        : `/schools/${school.id}`
                    }
                    className="font-semibold text-blue-700 hover:underline"
                  >
                    {school.name}
                  </Link>
                  <div className="mt-1 text-xs text-gray-600">
                    {school.postcode}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-xs font-medium">
                      {ofstedLabel(school.ofsted_rating)}
                    </span>
                  </div>
                  {school.distance_km != null && (
                    <div className="mt-1 text-xs text-gray-500">
                      {school.distance_km.toFixed(1)} km away
                    </div>
                  )}
                  <div className="mt-1 text-xs text-gray-500">
                    Ages {school.age_range_from}&ndash;{school.age_range_to} |{" "}
                    {school.gender_policy}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
