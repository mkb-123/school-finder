/**
 * WaitingListGauge - Visual component for admissions likelihood estimation.
 *
 * Displays:
 * - Likelihood indicator (colour-coded gauge)
 * - Last distance offered vs user distance
 * - Trend arrow (shrinking/stable/growing catchment)
 * - Historical chart showing last_distance_offered over years
 */

interface AdmissionsRecord {
  id: number;
  school_id: number;
  academic_year: string;
  places_offered: number | null;
  applications_received: number | null;
  last_distance_offered_km: number | null;
  waiting_list_offers: number | null;
  appeals_heard: number | null;
  appeals_upheld: number | null;
}

interface AdmissionsEstimate {
  likelihood: string;
  trend: string;
  avg_last_distance_km: number | null;
  min_last_distance_km: number | null;
  max_last_distance_km: number | null;
  latest_last_distance_km: number | null;
  avg_oversubscription_ratio: number | null;
  years_of_data: number;
}

interface WaitingListGaugeProps {
  estimate: AdmissionsEstimate | null;
  admissionsHistory: AdmissionsRecord[];
  userDistanceKm?: number | null;
}

const LIKELIHOOD_CONFIG: Record<
  string,
  { color: string; bgColor: string; textColor: string; barWidth: string }
> = {
  "Very likely": {
    color: "#16a34a",
    bgColor: "bg-green-50",
    textColor: "text-green-700",
    barWidth: "w-full",
  },
  Likely: {
    color: "#2563eb",
    bgColor: "bg-blue-50",
    textColor: "text-blue-700",
    barWidth: "w-3/4",
  },
  Unlikely: {
    color: "#d97706",
    bgColor: "bg-amber-50",
    textColor: "text-amber-700",
    barWidth: "w-1/2",
  },
  "Very unlikely": {
    color: "#dc2626",
    bgColor: "bg-red-50",
    textColor: "text-red-700",
    barWidth: "w-1/4",
  },
};

function TrendIndicator({ trend }: { trend: string }) {
  if (trend === "shrinking") {
    return (
      <div className="flex items-center gap-1.5 text-sm">
        <svg
          className="h-4 w-4 text-red-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"
          />
        </svg>
        <span className="font-medium text-red-600">Catchment shrinking</span>
        <span className="text-stone-500">
          &mdash; demand increasing, harder to get in
        </span>
      </div>
    );
  }
  if (trend === "growing") {
    return (
      <div className="flex items-center gap-1.5 text-sm">
        <svg
          className="h-4 w-4 text-green-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
          />
        </svg>
        <span className="font-medium text-green-600">Catchment growing</span>
        <span className="text-stone-500">
          &mdash; demand easing, easier to get in
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5 text-sm">
      <svg
        className="h-4 w-4 text-stone-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 12h14"
        />
      </svg>
      <span className="font-medium text-stone-600">Catchment stable</span>
      <span className="text-stone-500">
        &mdash; demand relatively consistent
      </span>
    </div>
  );
}

function DistanceChart({
  admissionsHistory,
  userDistanceKm,
}: {
  admissionsHistory: AdmissionsRecord[];
  userDistanceKm?: number | null;
}) {
  // Sort by academic year
  const sorted = [...admissionsHistory]
    .filter((r) => r.last_distance_offered_km != null)
    .sort((a, b) => a.academic_year.localeCompare(b.academic_year));

  if (sorted.length === 0) return null;

  const distances = sorted.map((r) => r.last_distance_offered_km!);
  const allValues = [...distances];
  if (userDistanceKm != null) allValues.push(userDistanceKm);
  const maxVal = Math.max(...allValues) * 1.15;
  const chartHeight = 160;

  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-stone-700">
        Last Distance Offered Over Time
      </h4>
      <div className="mt-2 flex items-end gap-2" style={{ height: chartHeight }}>
        {sorted.map((record) => {
          const dist = record.last_distance_offered_km!;
          const height = maxVal > 0 ? (dist / maxVal) * chartHeight : 0;
          const yearLabel = record.academic_year.replace("/", "/\u200B");
          return (
            <div
              key={record.academic_year}
              className="flex flex-1 flex-col items-center gap-1"
            >
              <span className="text-xs font-medium text-stone-600">
                {dist.toFixed(2)} km
              </span>
              <div
                className="w-full rounded-t bg-blue-400 transition-all"
                style={{ height: `${height}px` }}
                title={`${record.academic_year}: ${dist.toFixed(2)} km`}
              />
              <span className="text-xs text-stone-500">{yearLabel}</span>
            </div>
          );
        })}
        {userDistanceKm != null && (
          <div className="flex flex-1 flex-col items-center gap-1">
            <span className="text-xs font-medium text-amber-600">
              {userDistanceKm.toFixed(2)} km
            </span>
            <div
              className="w-full rounded-t border-2 border-dashed border-amber-400 bg-amber-100 transition-all"
              style={{
                height: `${maxVal > 0 ? (userDistanceKm / maxVal) * chartHeight : 0}px`,
              }}
              title={`Your distance: ${userDistanceKm.toFixed(2)} km`}
            />
            <span className="text-xs font-medium text-amber-600">You</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function WaitingListGauge({
  estimate,
  admissionsHistory,
  userDistanceKm,
}: WaitingListGaugeProps) {
  if (!estimate || estimate.years_of_data === 0) {
    return (
      <div className="rounded-lg border border-stone-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-stone-900">
          Waiting List Estimator
        </h3>
        <p className="mt-2 text-sm text-stone-500">
          No historical admissions data available for this school.
        </p>
      </div>
    );
  }

  const config = LIKELIHOOD_CONFIG[estimate.likelihood] ?? {
    color: "#6b7280",
    bgColor: "bg-stone-50",
    textColor: "text-stone-700",
    barWidth: "w-1/2",
  };

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-stone-900">
        Waiting List Estimator
      </h3>

      {/* Likelihood gauge */}
      <div className={`mt-4 rounded-lg ${config.bgColor} p-4`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-stone-600">
              Likelihood of getting a place
            </p>
            <p className={`mt-1 text-2xl font-bold ${config.textColor}`}>
              {estimate.likelihood}
            </p>
          </div>
          <div
            className="flex h-16 w-16 items-center justify-center rounded-full border-4"
            style={{ borderColor: config.color }}
          >
            <span
              className="text-xs font-bold"
              style={{ color: config.color }}
            >
              {estimate.likelihood === "Very likely"
                ? "90%+"
                : estimate.likelihood === "Likely"
                  ? "60-90%"
                  : estimate.likelihood === "Unlikely"
                    ? "30-60%"
                    : "<30%"}
            </span>
          </div>
        </div>

        {/* Gauge bar */}
        <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-stone-200">
          <div
            className={`h-full rounded-full ${config.barWidth} transition-all`}
            style={{ backgroundColor: config.color }}
          />
        </div>
        <div className="mt-1 flex justify-between text-xs text-stone-400">
          <span>Very unlikely</span>
          <span>Unlikely</span>
          <span>Likely</span>
          <span>Very likely</span>
        </div>
      </div>

      {/* Distance comparison */}
      {(estimate.latest_last_distance_km != null ||
        userDistanceKm != null) && (
        <div className="mt-4 grid grid-cols-2 gap-4">
          {estimate.latest_last_distance_km != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">
                Last distance offered (latest)
              </p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {estimate.latest_last_distance_km.toFixed(2)} km
              </p>
            </div>
          )}
          {userDistanceKm != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">Your distance</p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {userDistanceKm.toFixed(2)} km
              </p>
            </div>
          )}
          {estimate.avg_last_distance_km != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">
                Average last distance (all years)
              </p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {estimate.avg_last_distance_km.toFixed(2)} km
              </p>
            </div>
          )}
          {estimate.avg_oversubscription_ratio != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">
                Avg. oversubscription ratio
              </p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {estimate.avg_oversubscription_ratio.toFixed(1)}x
              </p>
            </div>
          )}
        </div>
      )}

      {/* Trend indicator */}
      <div className="mt-4">
        <TrendIndicator trend={estimate.trend} />
      </div>

      {/* Historical distance chart */}
      <DistanceChart
        admissionsHistory={admissionsHistory}
        userDistanceKm={userDistanceKm}
      />

      <p className="mt-3 text-xs text-stone-400">
        Based on {estimate.years_of_data} year(s) of historical admissions data.
        This estimate is indicative only and does not guarantee a place.
      </p>
    </div>
  );
}

export type { AdmissionsRecord, AdmissionsEstimate };
