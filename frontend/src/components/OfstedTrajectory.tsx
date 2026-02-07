import { TrendingUp, TrendingDown, Minus, AlertCircle, Clock } from 'lucide-react';

interface OfstedInspection {
  id: number;
  inspection_date: string;
  rating: string;
  strengths_quote?: string | null;
  improvements_quote?: string | null;
  report_url?: string | null;
}

interface OfstedTrajectoryData {
  trajectory: 'improving' | 'stable' | 'declining' | 'unknown';
  current_rating?: string | null;
  previous_rating?: string | null;
  inspection_age_years?: number | null;
  is_stale: boolean;
  history: OfstedInspection[];
}

interface OfstedTrajectoryProps {
  trajectory: OfstedTrajectoryData;
}

const ratingColors: Record<string, string> = {
  'Outstanding': 'text-green-700 bg-green-50 border-green-200',
  'Good': 'text-blue-700 bg-blue-50 border-blue-200',
  'Requires Improvement': 'text-amber-700 bg-amber-50 border-amber-200',
  'Inadequate': 'text-red-700 bg-red-50 border-red-200',
};

const trajectoryConfig: Record<string, { icon: typeof TrendingUp; color: string; label: string }> = {
  improving: { icon: TrendingUp, color: 'text-green-700 bg-green-50 border-green-200', label: 'Improving' },
  declining: { icon: TrendingDown, color: 'text-red-700 bg-red-50 border-red-200', label: 'Declining' },
  stable: { icon: Minus, color: 'text-blue-700 bg-blue-50 border-blue-200', label: 'Stable' },
  unknown: { icon: Minus, color: 'text-stone-700 bg-stone-50 border-stone-200', label: 'Unknown' },
};

export function OfstedTrajectory({ trajectory }: OfstedTrajectoryProps) {
  const config = trajectoryConfig[trajectory.trajectory] ?? trajectoryConfig.unknown;
  const TrajectoryIcon = config.icon;

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  // Empty state when there is no history
  if (trajectory.history.length === 0) {
    return (
      <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6" aria-labelledby="ofsted-heading">
        <h2 id="ofsted-heading" className="text-lg font-semibold text-stone-900">Ofsted Rating History</h2>
        <div className="mt-4 flex items-center gap-3 rounded-lg bg-stone-50 p-4 text-sm text-stone-500">
          <svg className="h-5 w-5 flex-shrink-0 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          No Ofsted inspection history available for this school.
        </div>
      </section>
    );
  }

  const inspectionAgeYears = trajectory.inspection_age_years;

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6 space-y-6" aria-labelledby="ofsted-heading">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="ofsted-heading" className="text-lg font-semibold text-stone-900">Ofsted Rating History</h2>
          <p className="text-sm text-stone-500 mt-1">
            How this school's Ofsted rating has changed over time
          </p>
        </div>
        <div
          className={`inline-flex items-center gap-2 self-start rounded-full border px-3 py-1.5 text-sm font-semibold ${config.color}`}
          aria-label={`Rating trend: ${config.label}`}
        >
          <TrajectoryIcon className="h-4 w-4" aria-hidden="true" />
          {config.label}
        </div>
      </div>

      {/* Stale rating warning */}
      {trajectory.is_stale && inspectionAgeYears != null && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4" role="alert">
          <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-amber-900">Rating may be outdated</p>
            <p className="mt-0.5 text-sm text-amber-800">
              The last inspection was {inspectionAgeYears.toFixed(1)} years ago (over 5 years).
              A new inspection may be due soon.
            </p>
          </div>
        </div>
      )}

      {/* Last inspected note */}
      {inspectionAgeYears != null && !trajectory.is_stale && (
        <div className="flex items-center gap-2 text-sm text-stone-500">
          <Clock className="h-4 w-4" aria-hidden="true" />
          <span>Last inspected {inspectionAgeYears.toFixed(1)} years ago</span>
        </div>
      )}

      {/* Inspection Timeline */}
      <div>
        <h3 className="text-base font-semibold text-stone-900">Inspection History</h3>
        <ol className="mt-4 space-y-4" aria-label="Ofsted inspection timeline">
          {trajectory.history.map((inspection, index) => {
            const ratingStyle = ratingColors[inspection.rating] ?? 'text-stone-700 bg-stone-50 border-stone-200';
            const isCurrent = index === 0;

            return (
              <li
                key={inspection.id}
                className={`rounded-xl border p-4 ${isCurrent ? 'border-stone-300 bg-white' : 'border-stone-200 bg-white'}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`inline-block rounded-full border px-3 py-1 text-sm font-semibold ${ratingStyle}`}>
                      {inspection.rating}
                    </span>
                    {isCurrent && (
                      <span className="inline-flex items-center rounded-full bg-stone-900 px-2 py-0.5 text-xs font-medium text-white">
                        Current
                      </span>
                    )}
                  </div>
                  {inspection.report_url && (
                    <a
                      href={inspection.report_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-sm font-medium text-brand-600 transition hover:bg-brand-50 focus:outline-none focus:ring-2 focus:ring-brand-500"
                    >
                      View report
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  )}
                </div>

                <p className="text-sm text-stone-500">
                  Inspected {formatDate(inspection.inspection_date)}
                </p>

                {inspection.strengths_quote && (
                  <div className="mt-3 rounded-lg bg-green-50 border border-green-100 p-3">
                    <p className="text-xs font-semibold text-green-800 mb-1">Strengths</p>
                    <p className="text-sm text-green-900 leading-relaxed">"{inspection.strengths_quote}"</p>
                  </div>
                )}

                {inspection.improvements_quote && (
                  <div className="mt-2 rounded-lg bg-amber-50 border border-amber-100 p-3">
                    <p className="text-xs font-semibold text-amber-800 mb-1">Areas for improvement</p>
                    <p className="text-sm text-amber-900 leading-relaxed">"{inspection.improvements_quote}"</p>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
