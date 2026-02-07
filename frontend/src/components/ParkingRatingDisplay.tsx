interface ParkingRatingSummary {
  school_id: number;
  total_ratings: number;
  avg_dropoff_chaos?: number | null;
  avg_pickup_chaos?: number | null;
  avg_parking_availability?: number | null;
  avg_road_congestion?: number | null;
  avg_restrictions_hazards?: number | null;
  overall_chaos_score?: number | null;
}

interface ParkingRatingDisplayProps {
  summary: ParkingRatingSummary | null | undefined;
  compact?: boolean;
}

const getChaosColor = (score: number | null | undefined): string => {
  if (score === null || score === undefined) return "text-stone-400";
  if (score <= 2) return "text-green-600";
  if (score <= 3.5) return "text-amber-600";
  return "text-red-600";
};

const getChaosLabel = (score: number | null | undefined): string => {
  if (score === null || score === undefined) return "No data";
  if (score <= 2) return "Easy";
  if (score <= 3.5) return "Moderate";
  return "Difficult";
};

const getChaosBarColor = (score: number | null | undefined): string => {
  if (score === null || score === undefined) return "bg-stone-300";
  if (score <= 2) return "bg-green-500";
  if (score <= 3.5) return "bg-amber-500";
  return "bg-red-500";
};

const formatScore = (score: number | null | undefined): string => {
  if (score === null || score === undefined) return "--";
  return score.toFixed(1);
};

const METRICS = [
  { label: "Drop-off", key: "avg_dropoff_chaos" as const, description: "Morning drop-off congestion" },
  { label: "Pick-up", key: "avg_pickup_chaos" as const, description: "Afternoon pick-up congestion" },
  { label: "Parking", key: "avg_parking_availability" as const, description: "Difficulty finding parking" },
  { label: "Traffic", key: "avg_road_congestion" as const, description: "Surrounding road congestion" },
  { label: "Hazards", key: "avg_restrictions_hazards" as const, description: "Restrictions and safety concerns" },
];

export default function ParkingRatingDisplay({ summary, compact = false }: ParkingRatingDisplayProps) {
  if (!summary || summary.total_ratings === 0) {
    return (
      <div className="flex flex-col items-center rounded-xl border border-stone-200 bg-white py-8 px-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-stone-100">
          <svg
            className="h-6 w-6 text-stone-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
            />
          </svg>
        </div>
        <p className="mt-3 text-sm font-medium text-stone-900">No parking ratings yet</p>
        <p className="mt-1 text-xs text-stone-500">Be the first parent to rate the school run here.</p>
      </div>
    );
  }

  const overallColor = getChaosColor(summary.overall_chaos_score);
  const overallLabel = getChaosLabel(summary.overall_chaos_score);

  if (compact) {
    return (
      <div className="flex items-center gap-2.5 text-sm">
        <svg
          className="h-5 w-5 text-stone-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
          />
        </svg>
        <span className={`font-medium ${overallColor}`}>
          {overallLabel} ({formatScore(summary.overall_chaos_score)}/5)
        </span>
        <span className="text-stone-400">{summary.total_ratings} rating{summary.total_ratings !== 1 ? "s" : ""}</span>
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6" aria-labelledby="parking-heading">
      <div className="flex items-center justify-between">
        <h3 id="parking-heading" className="text-lg font-semibold text-stone-900">
          School Run Experience
        </h3>
        <span className="text-sm text-stone-500">
          {summary.total_ratings} parent rating{summary.total_ratings !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Overall score */}
      <div className="mt-4 rounded-xl bg-stone-50 border border-stone-100 p-4 sm:p-5">
        <div className="text-center">
          <div className={`text-4xl font-bold ${overallColor}`}>
            {formatScore(summary.overall_chaos_score)}
          </div>
          <div className="mt-1 text-sm text-stone-500">out of 5</div>
          <div className={`mt-1.5 inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${
            (summary.overall_chaos_score ?? 0) <= 2
              ? "bg-green-50 text-green-700"
              : (summary.overall_chaos_score ?? 0) <= 3.5
              ? "bg-amber-50 text-amber-700"
              : "bg-red-50 text-red-700"
          }`}>
            {overallLabel}
          </div>
        </div>
      </div>

      {/* Scale explanation */}
      <div className="mt-4 flex items-center justify-between text-xs text-stone-500">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-green-500" aria-hidden="true" />
          1 = Easy, no issues
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
          5 = Very difficult
        </span>
      </div>

      {/* Individual metrics */}
      <div className="mt-5 space-y-3">
        {METRICS.map(({ label, key }) => {
          const value = summary[key];
          return (
            <div key={key} className="flex items-center justify-between gap-4">
              <span className="text-sm text-stone-700 flex-shrink-0">{label}</span>
              <div className="flex items-center gap-2 flex-1 justify-end">
                <div className="h-2 w-24 sm:w-32 overflow-hidden rounded-full bg-stone-200">
                  <div
                    className={`h-full rounded-full transition-all ${getChaosBarColor(value)}`}
                    style={{ width: value != null ? `${(value / 5) * 100}%` : "0%" }}
                  />
                </div>
                <span className={`w-8 text-right text-sm font-medium ${getChaosColor(value)}`}>
                  {formatScore(value)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-5 rounded-lg bg-stone-50 border border-stone-100 p-3 text-xs text-stone-600">
        <p>
          <span className="font-medium">How to read these ratings:</span> Scores range from 1 (easy, no issues) to 5 (very
          difficult). Based on anonymous parent submissions about congestion, parking, and safety.
        </p>
      </div>
    </section>
  );
}
