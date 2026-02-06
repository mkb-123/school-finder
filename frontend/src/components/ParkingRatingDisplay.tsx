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
  if (!score) return "text-gray-400";
  if (score <= 2) return "text-green-600";
  if (score <= 3.5) return "text-amber-600";
  return "text-red-600";
};

const getChaosLabel = (score: number | null | undefined): string => {
  if (!score) return "No data";
  if (score <= 2) return "Low chaos";
  if (score <= 3.5) return "Moderate";
  return "High chaos";
};

const formatScore = (score: number | null | undefined): string => {
  if (!score) return "N/A";
  return score.toFixed(1);
};

export default function ParkingRatingDisplay({ summary, compact = false }: ParkingRatingDisplayProps) {
  if (!summary || summary.total_ratings === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-center text-sm text-gray-500">
        <svg
          className="mx-auto h-8 w-8 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
          />
        </svg>
        <p className="mt-2">No parking ratings yet</p>
      </div>
    );
  }

  const overallColor = getChaosColor(summary.overall_chaos_score);
  const overallLabel = getChaosLabel(summary.overall_chaos_score);

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <svg
          className="h-5 w-5 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
          />
        </svg>
        <span className={`font-medium ${overallColor}`}>
          {overallLabel} ({formatScore(summary.overall_chaos_score)}/5)
        </span>
        <span className="text-gray-400">• {summary.total_ratings} ratings</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          Parking & Drop-off Chaos
        </h3>
        <span className="text-sm text-gray-500">
          {summary.total_ratings} parent rating{summary.total_ratings !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="mb-6 rounded-lg bg-gray-50 p-4">
        <div className="text-center">
          <div className={`text-4xl font-bold ${overallColor}`}>
            {formatScore(summary.overall_chaos_score)}
          </div>
          <div className="mt-1 text-sm text-gray-600">out of 5</div>
          <div className={`mt-2 text-sm font-medium ${overallColor}`}>
            {overallLabel}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {[
          { label: "Drop-off chaos", value: summary.avg_dropoff_chaos },
          { label: "Pick-up chaos", value: summary.avg_pickup_chaos },
          { label: "Parking difficulty", value: summary.avg_parking_availability },
          { label: "Road congestion", value: summary.avg_road_congestion },
          { label: "Restrictions/hazards", value: summary.avg_restrictions_hazards },
        ].map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between">
            <span className="text-sm text-gray-700">{label}</span>
            <div className="flex items-center gap-2">
              <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-200">
                <div
                  className={`h-full ${
                    value && value <= 2
                      ? "bg-green-500"
                      : value && value <= 3.5
                      ? "bg-amber-500"
                      : "bg-red-500"
                  }`}
                  style={{ width: value ? `${(value / 5) * 100}%` : "0%" }}
                />
              </div>
              <span className={`text-sm font-medium ${getChaosColor(value)}`}>
                {formatScore(value)}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 border-t border-gray-200 pt-4 text-xs text-gray-500">
        <p>
          Ratings are on a 1-5 scale where 5 is worst. Based on parent submissions
          about school gate congestion, parking availability, and safety concerns.
        </p>
      </div>
    </div>
  );
}
