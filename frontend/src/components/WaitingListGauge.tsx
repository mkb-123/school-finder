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
  allocation_description: string | null;
  had_vacancies: boolean | null;
  intake_year: string | null;
  source_url: string | null;
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
  { bgColor: string; textColor: string; barWidth: string; ringColor: string; description: string }
> = {
  "Very likely": {
    bgColor: "bg-green-50",
    textColor: "text-green-700",
    barWidth: "w-full",
    ringColor: "ring-green-600/20",
    description: "Based on historical data, your distance falls well within the typical admission range.",
  },
  Likely: {
    bgColor: "bg-blue-50",
    textColor: "text-blue-700",
    barWidth: "w-3/4",
    ringColor: "ring-blue-600/20",
    description: "Your distance is within the range that has usually been offered places in previous years.",
  },
  Unlikely: {
    bgColor: "bg-amber-50",
    textColor: "text-amber-700",
    barWidth: "w-1/2",
    ringColor: "ring-amber-600/20",
    description: "Your distance is near or beyond the typical cutoff. You may want to consider alternatives.",
  },
  "Very unlikely": {
    bgColor: "bg-red-50",
    textColor: "text-red-700",
    barWidth: "w-1/4",
    ringColor: "ring-red-600/20",
    description: "Historical data suggests places are rarely offered at this distance from the school.",
  },
};

const GAUGE_STEPS = ["Very unlikely", "Unlikely", "Likely", "Very likely"];

function TrendIndicator({ trend }: { trend: string }) {
  if (trend === "shrinking") {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3">
        <svg
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"
          />
        </svg>
        <div>
          <p className="text-sm font-medium text-red-800">Getting harder to get in</p>
          <p className="mt-0.5 text-xs text-red-700">
            The maximum distance offered has been shrinking, which means demand is increasing.
          </p>
        </div>
      </div>
    );
  }
  if (trend === "growing") {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-3">
        <svg
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
          />
        </svg>
        <div>
          <p className="text-sm font-medium text-green-800">Getting easier to get in</p>
          <p className="mt-0.5 text-xs text-green-700">
            The maximum distance offered has been growing, which means demand is easing.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3 rounded-lg border border-stone-200 bg-stone-50 p-3">
      <svg
        className="mt-0.5 h-5 w-5 flex-shrink-0 text-stone-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 12h14"
        />
      </svg>
      <div>
        <p className="text-sm font-medium text-stone-700">Demand is stable</p>
        <p className="mt-0.5 text-xs text-stone-600">
          The admission distance has been relatively consistent across recent years.
        </p>
      </div>
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
  const chartHeight = 180;

  return (
    <div className="mt-5">
      <h4 className="text-sm font-medium text-stone-700">
        Maximum Distance Offered Over Time
      </h4>
      <p className="mt-0.5 text-xs text-stone-500">
        The furthest distance that received an offer each year
      </p>
      <div
        className="mt-3 flex items-end gap-1.5 sm:gap-2"
        style={{ height: chartHeight }}
        role="img"
        aria-label={`Bar chart showing last distance offered over ${sorted.length} years`}
      >
        {sorted.map((record) => {
          const dist = record.last_distance_offered_km!;
          const height = maxVal > 0 ? (dist / maxVal) * chartHeight : 0;
          const yearLabel = record.academic_year.replace("/", "/\u200B");
          return (
            <div
              key={record.academic_year}
              className="flex flex-1 flex-col items-center gap-1"
              style={{ minWidth: "2.5rem" }}
            >
              <span className="text-xs font-medium text-stone-600">
                {dist.toFixed(2)}
              </span>
              <div
                className="w-full max-w-[3rem] rounded-t bg-blue-400 transition-all"
                style={{ height: `${height}px` }}
                title={`${record.academic_year}: ${dist.toFixed(2)} km`}
              />
              <span className="text-[11px] text-stone-500">{yearLabel}</span>
            </div>
          );
        })}
        {userDistanceKm != null && (
          <div
            className="flex flex-1 flex-col items-center gap-1"
            style={{ minWidth: "2.5rem" }}
          >
            <span className="text-xs font-semibold text-amber-700">
              {userDistanceKm.toFixed(2)}
            </span>
            <div
              className="w-full max-w-[3rem] rounded-t border-2 border-dashed border-amber-400 bg-amber-100 transition-all"
              style={{
                height: `${maxVal > 0 ? (userDistanceKm / maxVal) * chartHeight : 0}px`,
              }}
              title={`Your distance: ${userDistanceKm.toFixed(2)} km`}
            />
            <span className="text-[11px] font-semibold text-amber-700">You</span>
          </div>
        )}
      </div>
      <p className="mt-1 text-right text-[10px] text-stone-400">Distance in km</p>
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
      <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6" aria-labelledby="wl-heading">
        <h3 id="wl-heading" className="text-lg font-semibold text-stone-900">
          Admissions Likelihood
        </h3>
        <div className="mt-4 flex items-center gap-3 rounded-lg bg-stone-50 p-4 text-sm text-stone-500">
          <svg className="h-5 w-5 flex-shrink-0 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          No historical admissions data available for this school.
        </div>
      </section>
    );
  }

  const config = LIKELIHOOD_CONFIG[estimate.likelihood] ?? {
    bgColor: "bg-stone-50",
    textColor: "text-stone-700",
    barWidth: "w-1/2",
    ringColor: "ring-stone-300/50",
    description: "We could not determine a likelihood based on available data.",
  };

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6" aria-labelledby="wl-heading">
      <h3 id="wl-heading" className="text-lg font-semibold text-stone-900">
        Admissions Likelihood
      </h3>

      {/* Likelihood display */}
      <div className={`mt-4 rounded-xl ${config.bgColor} p-4 sm:p-5`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-stone-600">
              Chance of getting a place
            </p>
            <p className={`mt-1 text-2xl font-bold ${config.textColor}`}>
              {estimate.likelihood}
            </p>
          </div>
          <span
            className={`self-start inline-flex items-center rounded-full ${config.bgColor} px-3 py-1.5 text-sm font-semibold ${config.textColor} ring-1 ${config.ringColor}`}
            aria-hidden="true"
          >
            {estimate.likelihood}
          </span>
        </div>

        {/* Description */}
        <p className="mt-3 text-sm text-stone-600">
          {config.description}
        </p>

        {/* Gauge bar */}
        <div className="mt-4" role="meter" aria-label="Likelihood gauge" aria-valuenow={GAUGE_STEPS.indexOf(estimate.likelihood) + 1} aria-valuemin={1} aria-valuemax={4}>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-stone-200">
            <div
              className={`h-full rounded-full ${config.barWidth} transition-all duration-500`}
              style={{
                backgroundColor:
                  estimate.likelihood === "Very likely" ? "#16a34a"
                  : estimate.likelihood === "Likely" ? "#2563eb"
                  : estimate.likelihood === "Unlikely" ? "#d97706"
                  : "#dc2626",
              }}
            />
          </div>
          <div className="mt-1.5 flex justify-between text-[11px] font-medium text-stone-500">
            {GAUGE_STEPS.map((step) => (
              <span
                key={step}
                className={step === estimate.likelihood ? `${config.textColor} font-bold` : ""}
              >
                {step}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Distance comparison */}
      {(estimate.latest_last_distance_km != null ||
        userDistanceKm != null) && (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {estimate.latest_last_distance_km != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">
                Last distance offered
              </p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {estimate.latest_last_distance_km.toFixed(2)} km
              </p>
            </div>
          )}
          {userDistanceKm != null && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-medium text-amber-700">Your distance</p>
              <p className="mt-1 text-lg font-semibold text-amber-900">
                {userDistanceKm.toFixed(2)} km
              </p>
            </div>
          )}
          {estimate.avg_last_distance_km != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">
                Average (all years)
              </p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {estimate.avg_last_distance_km.toFixed(2)} km
              </p>
            </div>
          )}
          {estimate.avg_oversubscription_ratio != null && (
            <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">
                Oversubscription
              </p>
              <p className="mt-1 text-lg font-semibold text-stone-900">
                {estimate.avg_oversubscription_ratio.toFixed(1)}x
              </p>
            </div>
          )}
        </div>
      )}

      {/* Trend indicator */}
      <div className="mt-5">
        <TrendIndicator trend={estimate.trend} />
      </div>

      {/* Historical distance chart */}
      <DistanceChart
        admissionsHistory={admissionsHistory}
        userDistanceKm={userDistanceKm}
      />

      {/* Disclaimer -- more visible */}
      <div className="mt-5 rounded-lg bg-stone-50 border border-stone-200 p-3">
        <p className="text-xs text-stone-600">
          <span className="font-medium">Please note:</span> This estimate is based on {estimate.years_of_data} year(s) of historical admissions data
          and is indicative only. It does not guarantee a school place. Actual admissions
          are determined by the school's oversubscription criteria.
        </p>
      </div>
    </section>
  );
}

export type { AdmissionsRecord, AdmissionsEstimate };
