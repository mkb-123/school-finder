import { type FC } from "react";

export interface BusStop {
  id: number;
  stop_name: string;
  stop_location: string | null;
  lat: number | null;
  lng: number | null;
  morning_pickup_time: string | null;
  afternoon_dropoff_time: string | null;
  stop_order: number;
}

export interface BusRoute {
  id: number;
  route_name: string;
  provider: string | null;
  route_type: string;
  distance_eligibility_km: number | null;
  year_groups_eligible: string | null;
  eligibility_notes: string | null;
  is_free: boolean;
  cost_per_term: number | null;
  cost_per_year: number | null;
  cost_notes: string | null;
  operates_days: string | null;
  morning_departure_time: string | null;
  afternoon_departure_time: string | null;
  booking_url: string | null;
  notes: string | null;
  stops: BusStop[];
}

export interface NearbyBusStop {
  stop: BusStop;
  route_name: string;
  route_type: string;
  is_free: boolean;
  cost_per_term: number | null;
  school_id: number;
  school_name: string;
  distance_km: number;
}

interface BusRouteCardProps {
  route: BusRoute;
  nearbyStops?: NearbyBusStop[];
}

const formatTime = (timeStr: string | null): string => {
  if (!timeStr) return "N/A";
  // Time comes as HH:MM:SS from API
  const parts = timeStr.split(":");
  if (parts.length >= 2) {
    return `${parts[0]}:${parts[1]}`;
  }
  return timeStr;
};

const BusRouteCard: FC<BusRouteCardProps> = ({ route, nearbyStops }) => {
  const routeTypeLabel =
    route.route_type === "dedicated" ? "Council Bus" : "Private Coach";

  const nearbyStopsForRoute = nearbyStops?.filter(
    (ns) => route.stops.some((s) => s.id === ns.stop.id)
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {route.route_name}
          </h3>
          <div className="mt-1 flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
              {routeTypeLabel}
            </span>
            {route.is_free ? (
              <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                Free
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                Paid
              </span>
            )}
          </div>
        </div>
        {route.provider && (
          <p className="text-sm text-gray-500">{route.provider}</p>
        )}
      </div>

      {/* Cost Information */}
      {!route.is_free && (route.cost_per_term || route.cost_per_year) && (
        <div className="mt-3 rounded-md bg-gray-50 p-3">
          <p className="text-sm font-medium text-gray-700">Cost</p>
          <div className="mt-1 flex flex-wrap gap-x-4 text-sm text-gray-600">
            {route.cost_per_term && (
              <span>£{route.cost_per_term.toFixed(2)}/term</span>
            )}
            {route.cost_per_year && (
              <span>£{route.cost_per_year.toFixed(2)}/year</span>
            )}
          </div>
          {route.cost_notes && (
            <p className="mt-1 text-xs text-gray-500">{route.cost_notes}</p>
          )}
        </div>
      )}

      {/* Eligibility */}
      {(route.distance_eligibility_km ||
        route.year_groups_eligible ||
        route.eligibility_notes) && (
        <div className="mt-3">
          <p className="text-sm font-medium text-gray-700">Eligibility</p>
          <ul className="mt-1 space-y-1 text-sm text-gray-600">
            {route.distance_eligibility_km && (
              <li>
                • Must live {route.distance_eligibility_km}+ km from school
              </li>
            )}
            {route.year_groups_eligible && (
              <li>• Year groups: {route.year_groups_eligible}</li>
            )}
            {route.eligibility_notes && <li>• {route.eligibility_notes}</li>}
          </ul>
        </div>
      )}

      {/* Schedule */}
      {(route.operates_days ||
        route.morning_departure_time ||
        route.afternoon_departure_time) && (
        <div className="mt-3">
          <p className="text-sm font-medium text-gray-700">Schedule</p>
          <div className="mt-1 text-sm text-gray-600">
            {route.operates_days && <p>Operates: {route.operates_days}</p>}
            <div className="mt-1 flex gap-4">
              {route.morning_departure_time && (
                <span>
                  Morning: {formatTime(route.morning_departure_time)}
                </span>
              )}
              {route.afternoon_departure_time && (
                <span>
                  Afternoon: {formatTime(route.afternoon_departure_time)}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Nearby Stops Highlight */}
      {nearbyStopsForRoute && nearbyStopsForRoute.length > 0 && (
        <div className="mt-3 rounded-md bg-green-50 p-3">
          <p className="text-sm font-semibold text-green-900">
            Bus stop within walking distance
          </p>
          {nearbyStopsForRoute.map((ns) => (
            <p key={ns.stop.id} className="mt-1 text-sm text-green-800">
              {ns.stop.stop_name} ({ns.distance_km.toFixed(2)} km away)
              {ns.stop.morning_pickup_time &&
                ` • Pick-up: ${formatTime(ns.stop.morning_pickup_time)}`}
            </p>
          ))}
        </div>
      )}

      {/* Stops */}
      {route.stops.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900">
            View all stops ({route.stops.length})
          </summary>
          <div className="mt-2 space-y-2">
            {route.stops.map((stop) => (
              <div
                key={stop.id}
                className="rounded-md bg-gray-50 p-2 text-sm"
              >
                <p className="font-medium text-gray-900">{stop.stop_name}</p>
                {stop.stop_location && (
                  <p className="text-xs text-gray-600">{stop.stop_location}</p>
                )}
                {(stop.morning_pickup_time || stop.afternoon_dropoff_time) && (
                  <div className="mt-1 flex gap-3 text-xs text-gray-600">
                    {stop.morning_pickup_time && (
                      <span>
                        Morning: {formatTime(stop.morning_pickup_time)}
                      </span>
                    )}
                    {stop.afternoon_dropoff_time && (
                      <span>
                        Afternoon: {formatTime(stop.afternoon_dropoff_time)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Notes */}
      {route.notes && (
        <p className="mt-3 text-xs text-gray-500 italic">{route.notes}</p>
      )}

      {/* Booking Link */}
      {route.booking_url && (
        <div className="mt-3">
          <a
            href={route.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Booking information →
          </a>
        </div>
      )}
    </div>
  );
};

export default BusRouteCard;
