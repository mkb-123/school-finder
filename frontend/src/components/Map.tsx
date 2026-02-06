import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Circle,
  Popup,
  useMap,
  useMapEvents,
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
  prospectus_url: string | null;
  ethos: string | null;
}

export interface BusStopMarker {
  id: number;
  name: string;
  lat: number;
  lng: number;
  pickupTime?: string | null;
  schoolName: string;
}

interface MapProps {
  center?: LatLngExpression;
  zoom?: number;
  schools?: School[];
  /** ID of the school whose catchment to highlight. */
  selectedSchoolId?: number | null;
  onSchoolSelect?: (id: number) => void;
  /** Bus stops to display on the map. */
  busStops?: BusStopMarker[];
}

const MILTON_KEYNES: LatLngExpression = [52.0406, -0.7594];

/** Clustering threshold - cluster only when more than this many schools. */
const CLUSTER_THRESHOLD = 30;

/** Map colour by Ofsted rating. */
function ofstedColor(rating: string | null): string {
  switch (rating) {
    case "Outstanding":
      return "#16a34a";
    case "Good":
      return "#2563eb";
    case "Requires Improvement":
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

/** A cluster of nearby schools rendered as a single marker. */
interface Cluster {
  lat: number;
  lng: number;
  schools: School[];
}

/**
 * Grid-based clustering. Groups schools into grid cells based on the current
 * zoom level. At high zoom levels the grid is fine enough that no clustering
 * occurs. At low zoom levels schools are grouped into larger cells.
 */
function clusterSchools(
  schools: School[],
  zoom: number,
): { singles: School[]; clusters: Cluster[] } {
  // cellSize in degrees - shrinks as zoom increases
  const cellSize = 360 / Math.pow(2, zoom + 2);

  const grid: Record<string, School[]> = {};
  for (const s of schools) {
    if (s.lat == null || s.lng == null) continue;
    const cellX = Math.floor(s.lng / cellSize);
    const cellY = Math.floor(s.lat / cellSize);
    const key = `${cellX}_${cellY}`;
    if (!grid[key]) grid[key] = [];
    grid[key].push(s);
  }

  const singles: School[] = [];
  const clusters: Cluster[] = [];

  for (const cell of Object.values(grid)) {
    if (cell.length === 1) {
      singles.push(cell[0]);
    } else {
      // Compute centroid
      let latSum = 0;
      let lngSum = 0;
      for (const s of cell) {
        latSum += s.lat!;
        lngSum += s.lng!;
      }
      clusters.push({
        lat: latSum / cell.length,
        lng: lngSum / cell.length,
        schools: cell,
      });
    }
  }

  return { singles, clusters };
}

/** Recenter the map when the center prop changes. */
function RecenterMap({ center }: { center: LatLngExpression }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center);
  }, [map, center]);
  return null;
}

/** Track zoom level for clustering, and expose flyTo for cluster clicks. */
function ZoomTracker({
  onZoomChange,
  flyToRef,
}: {
  onZoomChange: (z: number) => void;
  flyToRef: React.MutableRefObject<((lat: number, lng: number) => void) | null>;
}) {
  const map = useMapEvents({
    zoomend: () => {
      onZoomChange(map.getZoom());
    },
  });
  // Expose a flyTo function for cluster clicks
  flyToRef.current = (lat: number, lng: number) => {
    map.flyTo([lat, lng], map.getZoom() + 2, { duration: 0.5 });
  };
  return null;
}

export default function Map({
  center = MILTON_KEYNES,
  zoom = 12,
  schools = [],
  selectedSchoolId = null,
  onSchoolSelect,
  busStops = [],
}: MapProps) {
  const [currentZoom, setCurrentZoom] = useState(zoom);
  const flyToRef = useRef<((lat: number, lng: number) => void) | null>(null);

  const schoolsWithCoords = useMemo(
    () => schools.filter((s) => s.lat != null && s.lng != null),
    [schools],
  );

  // Determine if we should cluster
  const shouldCluster = schoolsWithCoords.length > CLUSTER_THRESHOLD;

  const { singles, clusters } = useMemo(() => {
    if (!shouldCluster) {
      return { singles: schoolsWithCoords, clusters: [] as Cluster[] };
    }
    return clusterSchools(schoolsWithCoords, currentZoom);
  }, [schoolsWithCoords, currentZoom, shouldCluster]);

  return (
    <div
      className="h-full w-full overflow-hidden rounded-lg border border-gray-200"
      role="img"
      aria-label={`Map showing ${schools.length} school${schools.length !== 1 ? "s" : ""}`}
    >
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
        <ZoomTracker onZoomChange={setCurrentZoom} flyToRef={flyToRef} />

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

        {/* Individual school pins */}
        {singles.map((school) => {
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
                      aria-hidden="true"
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

        {/* Cluster markers */}
        {clusters.map((cluster, idx) => {
          const count = cluster.schools.length;
          // Size scales with count
          const radius = Math.min(12 + count * 1.5, 30);

          return (
            <CircleMarker
              key={`cluster-${idx}`}
              center={[cluster.lat, cluster.lng]}
              radius={radius}
              pathOptions={{
                color: "#3b82f6",
                fillColor: "#3b82f6",
                fillOpacity: 0.7,
                weight: 2,
              }}
              eventHandlers={{
                click: () => {
                  // Zoom in towards the cluster to break it apart
                  flyToRef.current?.(cluster.lat, cluster.lng);
                },
              }}
            >
              <Popup>
                <div className="min-w-[180px]">
                  <p className="font-semibold text-gray-900">
                    {count} schools in this area
                  </p>
                  <ul className="mt-1 max-h-32 overflow-y-auto text-xs text-gray-600">
                    {cluster.schools.slice(0, 8).map((s) => (
                      <li key={s.id} className="py-0.5">
                        <Link
                          to={
                            s.is_private
                              ? `/private-schools/${s.id}`
                              : `/schools/${s.id}`
                          }
                          className="text-blue-700 hover:underline"
                        >
                          {s.name}
                        </Link>
                        <span className="ml-1 text-gray-400">
                          ({ofstedLabel(s.ofsted_rating)})
                        </span>
                      </li>
                    ))}
                    {count > 8 && (
                      <li className="py-0.5 text-gray-400">
                        ...and {count - 8} more
                      </li>
                    )}
                  </ul>
                  <p className="mt-1 text-xs text-gray-400">
                    Zoom in to see individual schools
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {/* Bus stop markers */}
        {busStops.map((stop) => (
          <CircleMarker
            key={`bus-stop-${stop.id}`}
            center={[stop.lat, stop.lng]}
            radius={6}
            pathOptions={{
              color: "#f59e0b",
              fillColor: "#fbbf24",
              fillOpacity: 0.8,
              weight: 2,
            }}
          >
            <Popup>
              <div className="min-w-[140px]">
                <p className="font-semibold text-gray-900">{stop.name}</p>
                <p className="text-xs text-gray-600">{stop.schoolName}</p>
                {stop.pickupTime && (
                  <p className="mt-1 text-xs text-gray-500">
                    Pick-up: {stop.pickupTime}
                  </p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
