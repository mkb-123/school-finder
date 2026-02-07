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
  website: string | null;
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
  /** Whether to show the legend. Defaults to true. */
  showLegend?: boolean;
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

/** Ofsted legend items. */
const LEGEND_ITEMS = [
  { label: "Outstanding", color: "#16a34a" },
  { label: "Good", color: "#2563eb" },
  { label: "Requires improvement", color: "#d97706" },
  { label: "Inadequate", color: "#dc2626" },
  { label: "Not rated", color: "#6b7280" },
];

export default function Map({
  center = MILTON_KEYNES,
  zoom = 12,
  schools = [],
  selectedSchoolId = null,
  onSchoolSelect,
  busStops = [],
  showLegend = true,
}: MapProps) {
  const [currentZoom, setCurrentZoom] = useState(zoom);
  const [legendExpanded, setLegendExpanded] = useState(false);
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
      className="relative h-full w-full overflow-hidden rounded-xl border border-stone-200 shadow-sm"
      role="region"
      aria-label={`Interactive map showing ${schools.length} school${schools.length !== 1 ? "s" : ""}`}
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
                fillOpacity: 0.1,
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
                color: isSelected ? "#1e293b" : color,
                fillColor: color,
                fillOpacity: 0.9,
                weight: isSelected ? 3 : 2,
              }}
              eventHandlers={{
                click: () => onSchoolSelect?.(school.id),
              }}
            >
              <Popup>
                <div className="min-w-[200px] max-w-[260px]">
                  <Link
                    to={
                      school.is_private
                        ? `/private-schools/${school.id}`
                        : `/schools/${school.id}`
                    }
                    className="text-sm font-semibold text-brand-700 hover:underline"
                  >
                    {school.name}
                  </Link>
                  <p className="mt-1 text-xs text-stone-500">{school.postcode}</p>
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: color }}
                      aria-hidden="true"
                    />
                    <span className="text-xs font-medium text-stone-700">
                      {ofstedLabel(school.ofsted_rating)}
                    </span>
                  </div>
                  {school.distance_km != null && (
                    <p className="mt-1 text-xs text-stone-500">
                      {school.distance_km.toFixed(1)} km away
                    </p>
                  )}
                  <p className="mt-1 text-xs text-stone-500">
                    Ages {school.age_range_from}&ndash;{school.age_range_to}
                    <span className="mx-1 text-stone-300" aria-hidden="true">|</span>
                    {school.gender_policy}
                  </p>
                  <Link
                    to={
                      school.is_private
                        ? `/private-schools/${school.id}`
                        : `/schools/${school.id}`
                    }
                    className="mt-2 inline-block text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                  >
                    View full details
                  </Link>
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
                <div className="min-w-[200px] max-w-[260px]">
                  <p className="text-sm font-semibold text-stone-900">
                    {count} schools in this area
                  </p>
                  <ul className="mt-1.5 max-h-36 space-y-0.5 overflow-y-auto text-xs text-stone-600">
                    {cluster.schools.slice(0, 8).map((s) => (
                      <li key={s.id} className="py-0.5">
                        <Link
                          to={
                            s.is_private
                              ? `/private-schools/${s.id}`
                              : `/schools/${s.id}`
                          }
                          className="text-brand-700 hover:underline"
                        >
                          {s.name}
                        </Link>
                        <span className="ml-1 text-stone-400">
                          ({ofstedLabel(s.ofsted_rating)})
                        </span>
                      </li>
                    ))}
                    {count > 8 && (
                      <li className="py-0.5 text-stone-400">
                        and {count - 8} more
                      </li>
                    )}
                  </ul>
                  <p className="mt-2 text-xs font-medium text-brand-600">
                    Click to zoom in
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {/* Bus stop markers - slightly larger for mobile taps */}
        {busStops.map((stop) => (
          <CircleMarker
            key={`bus-stop-${stop.id}`}
            center={[stop.lat, stop.lng]}
            radius={8}
            pathOptions={{
              color: "#f59e0b",
              fillColor: "#fbbf24",
              fillOpacity: 0.85,
              weight: 2,
            }}
          >
            <Popup>
              <div className="min-w-[160px]">
                <p className="text-sm font-semibold text-stone-900">{stop.name}</p>
                <p className="mt-0.5 text-xs text-stone-600">{stop.schoolName}</p>
                {stop.pickupTime && (
                  <p className="mt-1 text-xs text-stone-500">
                    Pick-up: {stop.pickupTime}
                  </p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Ofsted colour legend - overlaid on map */}
      {showLegend && (
        <div className="absolute bottom-3 left-3 z-[1000]">
          <button
            onClick={() => setLegendExpanded(!legendExpanded)}
            className="flex items-center gap-1.5 rounded-lg bg-white/95 px-3 py-2 text-xs font-medium text-stone-700 shadow-md backdrop-blur-sm transition-colors hover:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            aria-expanded={legendExpanded}
            aria-label={legendExpanded ? "Hide map legend" : "Show map legend"}
          >
            {/* Colour dots preview when collapsed */}
            {!legendExpanded && (
              <span className="flex gap-0.5" aria-hidden="true">
                {LEGEND_ITEMS.slice(0, 4).map((item) => (
                  <span
                    key={item.label}
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                ))}
              </span>
            )}
            <span>{legendExpanded ? "Hide legend" : "Legend"}</span>
          </button>

          {legendExpanded && (
            <div className="mt-1.5 rounded-lg bg-white/95 p-3 shadow-md backdrop-blur-sm">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-stone-500">
                Ofsted rating
              </p>
              <ul className="mt-1.5 space-y-1.5">
                {LEGEND_ITEMS.map((item) => (
                  <li key={item.label} className="flex items-center gap-2">
                    <span
                      className="inline-block h-3 w-3 rounded-full"
                      style={{ backgroundColor: item.color }}
                      aria-hidden="true"
                    />
                    <span className="text-xs text-stone-700">{item.label}</span>
                  </li>
                ))}
              </ul>
              {busStops.length > 0 && (
                <>
                  <div className="my-2 border-t border-stone-200" />
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block h-3 w-3 rounded-full"
                      style={{ backgroundColor: "#fbbf24" }}
                      aria-hidden="true"
                    />
                    <span className="text-xs text-stone-700">Bus stop</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* School count badge */}
      {schools.length > 0 && (
        <div
          className="absolute right-3 top-3 z-[1000] rounded-lg bg-white/95 px-3 py-1.5 text-xs font-medium text-stone-600 shadow-md backdrop-blur-sm"
          aria-live="polite"
        >
          {schools.length} school{schools.length !== 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
