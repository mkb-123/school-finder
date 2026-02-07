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
  if (!timeStr) return "Not listed";
  // Time comes as HH:MM:SS from API
  const parts = timeStr.split(":");
  if (parts.length >= 2) {
    return `${parts[0]}:${parts[1]}`;
  }
  return timeStr;
};

const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
};

const BusRouteCard: FC<BusRouteCardProps> = ({ route, nearbyStops }) => {
  const routeTypeLabel =
    route.route_type === "dedicated" ? "Council Bus" : "Private Coach";

  const nearbyStopsForRoute = nearbyStops?.filter(
    (ns) => route.stops.some((s) => s.id === ns.stop.id)
  );

  return (
    <article className="rounded-xl border border-stone-200 bg-white p-4 sm:p-5 shadow-sm">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-stone-900">
            {route.route_name}
          </h3>
          <div className="mt-1.5 flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-800 ring-1 ring-brand-600/20">
              {routeTypeLabel}
            </span>
            {route.is_free ? (
              <span className="inline-flex items-center rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-800 ring-1 ring-green-600/20">
                Free
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-600/20">
                Paid
              </span>
            )}
          </div>
        </div>
        {route.provider && (
          <p className="text-sm text-stone-500">Operated by {route.provider}</p>
        )}
      </div>

      {/* Cost Information */}
      {!route.is_free && (route.cost_per_term || route.cost_per_year) && (
        <div className="mt-4 rounded-lg bg-stone-50 border border-stone-100 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Cost</p>
          <div className="mt-1.5 flex flex-wrap gap-x-6 gap-y-1">
            {route.cost_per_term != null && (
              <div className="text-sm">
                <span className="font-semibold text-stone-900">{formatCurrency(route.cost_per_term)}</span>
                <span className="text-stone-500">/term</span>
              </div>
            )}
            {route.cost_per_year != null && (
              <div className="text-sm">
                <span className="font-semibold text-stone-900">{formatCurrency(route.cost_per_year)}</span>
                <span className="text-stone-500">/year</span>
              </div>
            )}
          </div>
          {route.cost_notes && (
            <p className="mt-1.5 text-xs text-stone-500">{route.cost_notes}</p>
          )}
        </div>
      )}

      {/* Eligibility */}
      {(route.distance_eligibility_km ||
        route.year_groups_eligible ||
        route.eligibility_notes) && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Eligibility</p>
          <ul className="mt-1.5 space-y-1 text-sm text-stone-700">
            {route.distance_eligibility_km && (
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-stone-400" aria-hidden="true" />
                Must live {route.distance_eligibility_km}+ km from school
              </li>
            )}
            {route.year_groups_eligible && (
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-stone-400" aria-hidden="true" />
                Year groups: {route.year_groups_eligible}
              </li>
            )}
            {route.eligibility_notes && (
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-stone-400" aria-hidden="true" />
                {route.eligibility_notes}
              </li>
            )}
          </ul>
        </div>
      )}

      {/* Schedule */}
      {(route.operates_days ||
        route.morning_departure_time ||
        route.afternoon_departure_time) && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Schedule</p>
          <div className="mt-1.5 space-y-1.5 text-sm text-stone-700">
            {route.operates_days && <p>Operates: {route.operates_days}</p>}
            <div className="flex flex-col gap-1 sm:flex-row sm:gap-4">
              {route.morning_departure_time && (
                <div className="flex items-center gap-1.5">
                  <svg className="h-4 w-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707" />
                  </svg>
                  <span>Morning: <span className="font-medium">{formatTime(route.morning_departure_time)}</span></span>
                </div>
              )}
              {route.afternoon_departure_time && (
                <div className="flex items-center gap-1.5">
                  <svg className="h-4 w-4 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                  <span>Afternoon: <span className="font-medium">{formatTime(route.afternoon_departure_time)}</span></span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Nearby Stops Highlight */}
      {nearbyStopsForRoute && nearbyStopsForRoute.length > 0 && (
        <div className="mt-4 rounded-lg border border-green-200 bg-green-50 p-3">
          <p className="text-sm font-semibold text-green-900">
            Bus stop within walking distance
          </p>
          {nearbyStopsForRoute.map((ns) => (
            <div key={ns.stop.id} className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-green-800">
              <span className="font-medium">{ns.stop.stop_name}</span>
              <span className="text-green-700">({ns.distance_km.toFixed(2)} km away)</span>
              {ns.stop.morning_pickup_time && (
                <span className="text-green-700">Pick-up: {formatTime(ns.stop.morning_pickup_time)}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Stops list (progressive disclosure) */}
      {route.stops.length > 0 && (
        <details className="mt-4 group">
          <summary className="flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-2 -mx-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 focus:outline-none focus:ring-2 focus:ring-brand-500">
            <svg className="h-4 w-4 text-stone-400 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            View all {route.stops.length} stops
          </summary>
          <ol className="mt-2 space-y-1.5 ml-1">
            {route.stops.map((stop, index) => (
              <li
                key={stop.id}
                className="flex items-start gap-3 rounded-lg bg-stone-50 p-2.5 text-sm"
              >
                <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-stone-200 text-xs font-bold text-stone-600">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-stone-900">{stop.stop_name}</p>
                  {stop.stop_location && (
                    <p className="text-xs text-stone-500">{stop.stop_location}</p>
                  )}
                  {(stop.morning_pickup_time || stop.afternoon_dropoff_time) && (
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-stone-600">
                      {stop.morning_pickup_time && (
                        <span>Morning: {formatTime(stop.morning_pickup_time)}</span>
                      )}
                      {stop.afternoon_dropoff_time && (
                        <span>Afternoon: {formatTime(stop.afternoon_dropoff_time)}</span>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </details>
      )}

      {/* Notes */}
      {route.notes && (
        <p className="mt-4 text-xs italic text-stone-500">{route.notes}</p>
      )}

      {/* Booking Link */}
      {route.booking_url && (
        <div className="mt-4">
          <a
            href={route.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5 text-sm font-medium text-brand-700 transition hover:bg-brand-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            Booking information
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      )}
    </article>
  );
};

export default BusRouteCard;
