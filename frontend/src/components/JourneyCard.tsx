import { Link } from "react-router-dom";

/** Journey estimate for a single time-of-day window. */
export interface JourneyEstimate {
  distance_km: number;
  duration_minutes: number;
  mode: string;
  time_of_day: string;
  is_rush_hour: boolean;
}

/** Full journey data for one school (drop-off, pick-up, off-peak). */
export interface SchoolJourney {
  school_id: number;
  school_name: string;
  distance_km: number;
  dropoff: JourneyEstimate;
  pickup: JourneyEstimate;
  off_peak: JourneyEstimate;
}

interface JourneyCardProps {
  journey: SchoolJourney;
  /** Whether this is the quickest option in the comparison set. */
  isQuickest?: boolean;
  rank?: number;
}

/** Mode icons rendered as inline SVG. */
function ModeIcon({ mode }: { mode: string }) {
  switch (mode) {
    case "walking":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <title>Walking</title>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 7a2 2 0 100-4 2 2 0 000 4zm-1.5 3.5L8 17l2 1 2-4 3 3v5h2v-6.5l-3-3 .75-3.5L16 10v3h2V8.5l-4.5-1.5L12 10.5z"
          />
        </svg>
      );
    case "cycling":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <title>Cycling</title>
          <circle cx="6" cy="17" r="3" strokeWidth={2} />
          <circle cx="18" cy="17" r="3" strokeWidth={2} />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 17l4-8h4l2 4h2M12 9l-2-4" />
        </svg>
      );
    case "driving":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <title>Driving</title>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 17h14M5 17a2 2 0 01-2-2v-3l2-5h10l2 5v3a2 2 0 01-2 2M5 17a1 1 0 100 2 1 1 0 000-2zm10 0a1 1 0 100 2 1 1 0 000-2z"
          />
        </svg>
      );
    case "transit":
      return (
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <title>Public Transport</title>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 21l2-2m4 2l-2-2M7 4h10a2 2 0 012 2v8a2 2 0 01-2 2H7a2 2 0 01-2-2V6a2 2 0 012-2zm0 6h10M9 14h.01M15 14h.01"
          />
        </svg>
      );
    default:
      return null;
  }
}

/** Return a colour class based on duration in minutes. */
function durationColor(minutes: number): string {
  if (minutes < 10) return "text-green-600";
  if (minutes <= 20) return "text-amber-600";
  return "text-red-600";
}

/** Return a background class based on duration in minutes. */
function durationBg(minutes: number): string {
  if (minutes < 10) return "bg-green-50 border-green-200";
  if (minutes <= 20) return "bg-amber-50 border-amber-200";
  return "bg-red-50 border-red-200";
}

function formatDuration(minutes: number): string {
  if (minutes < 1) return "<1 min";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

export default function JourneyCard({
  journey,
  isQuickest = false,
  rank,
}: JourneyCardProps) {
  const { school_id, school_name, distance_km, dropoff, pickup, off_peak } = journey;

  // Guard against negative rush hour deltas from rounding
  const dropoffDelta = Math.max(0, Math.round(dropoff.duration_minutes - off_peak.duration_minutes));
  const pickupDelta = Math.max(0, Math.round(pickup.duration_minutes - off_peak.duration_minutes));
  const hasRushDelta = dropoff.mode === "driving" && (dropoffDelta > 0 || pickupDelta > 0);

  return (
    <div
      className={`rounded-xl border bg-white p-4 sm:p-5 shadow-sm transition hover:shadow-md ${
        isQuickest ? "ring-2 ring-green-500 ring-offset-1" : ""
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {rank != null && (
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-stone-100 text-xs font-bold text-stone-600">
              {rank}
            </span>
          )}
          <div>
            <Link
              to={`/schools/${school_id}`}
              className="text-base font-semibold text-stone-900 hover:text-brand-700 hover:underline transition-colors"
            >
              {school_name}
            </Link>
            <div className="mt-1 flex items-center gap-2 text-sm text-stone-500">
              <ModeIcon mode={dropoff.mode} />
              <span>{distance_km.toFixed(1)} km away</span>
            </div>
          </div>
        </div>
        {isQuickest && (
          <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
            Quickest
          </span>
        )}
      </div>

      {/* Time estimates grid */}
      <div className="mt-4 grid grid-cols-3 gap-2 sm:gap-3">
        {/* Drop-off */}
        <div className={`rounded-lg border p-2.5 sm:p-3 text-center ${durationBg(dropoff.duration_minutes)}`}>
          <div className="text-xs font-medium uppercase tracking-wide text-stone-600">
            Drop-off
          </div>
          <div className="text-xs text-stone-500 mt-0.5">8:00-8:45am</div>
          <div className={`mt-1.5 text-lg font-bold sm:text-xl ${durationColor(dropoff.duration_minutes)}`}>
            {formatDuration(dropoff.duration_minutes)}
          </div>
          {dropoff.is_rush_hour && (
            <div className="mt-0.5 text-xs text-stone-500">rush hour</div>
          )}
        </div>

        {/* Pick-up */}
        <div className={`rounded-lg border p-2.5 sm:p-3 text-center ${durationBg(pickup.duration_minutes)}`}>
          <div className="text-xs font-medium uppercase tracking-wide text-stone-600">
            Pick-up
          </div>
          <div className="text-xs text-stone-500 mt-0.5">5:00-5:30pm</div>
          <div className={`mt-1.5 text-lg font-bold sm:text-xl ${durationColor(pickup.duration_minutes)}`}>
            {formatDuration(pickup.duration_minutes)}
          </div>
          {pickup.is_rush_hour && (
            <div className="mt-0.5 text-xs text-stone-500">rush hour</div>
          )}
        </div>

        {/* Off-peak */}
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-2.5 sm:p-3 text-center">
          <div className="text-xs font-medium uppercase tracking-wide text-stone-600">
            Off-peak
          </div>
          <div className="text-xs text-stone-500 mt-0.5">quiet times</div>
          <div className={`mt-1.5 text-lg font-bold sm:text-xl ${durationColor(off_peak.duration_minutes)}`}>
            {formatDuration(off_peak.duration_minutes)}
          </div>
        </div>
      </div>

      {/* Rush hour comparison -- only show if there's a meaningful difference */}
      {hasRushDelta && (
        <p className="mt-3 text-xs text-stone-500">
          Rush hour adds {dropoffDelta > 0 ? `~${dropoffDelta} min at drop-off` : ""}
          {dropoffDelta > 0 && pickupDelta > 0 ? " and " : ""}
          {pickupDelta > 0 ? `~${pickupDelta} min at pick-up` : ""} to your drive.
        </p>
      )}
    </div>
  );
}
