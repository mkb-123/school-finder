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

export function OfstedTrajectory({ trajectory }: OfstedTrajectoryProps) {
  const getTrajectoryIcon = () => {
    switch (trajectory.trajectory) {
      case 'improving':
        return <TrendingUp className="w-5 h-5 text-green-600" />;
      case 'declining':
        return <TrendingDown className="w-5 h-5 text-red-600" />;
      case 'stable':
        return <Minus className="w-5 h-5 text-blue-600" />;
      default:
        return null;
    }
  };

  const getTrajectoryText = () => {
    switch (trajectory.trajectory) {
      case 'improving':
        return 'Improving';
      case 'declining':
        return 'Declining';
      case 'stable':
        return 'Stable';
      default:
        return 'Unknown';
    }
  };

  const getTrajectoryColor = () => {
    switch (trajectory.trajectory) {
      case 'improving':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'declining':
        return 'text-red-700 bg-red-50 border-red-200';
      case 'stable':
        return 'text-blue-700 bg-blue-50 border-blue-200';
      default:
        return 'text-stone-700 bg-stone-50 border-stone-200';
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-stone-900">Ofsted Trajectory</h2>
          <p className="text-sm text-stone-600 mt-1">
            Inspection history and direction of travel
          </p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${getTrajectoryColor()}`}>
          {getTrajectoryIcon()}
          <span className="font-semibold">{getTrajectoryText()}</span>
        </div>
      </div>

      {trajectory.is_stale && trajectory.inspection_age_years && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-amber-900">Rating may be stale</p>
            <p className="text-sm text-amber-800 mt-1">
              The last inspection was {trajectory.inspection_age_years!.toFixed(1)} years ago (over 5 years).
              A new inspection may be due soon.
            </p>
          </div>
        </div>
      )}

      {trajectory.inspection_age_years !== null && trajectory.inspection_age_years !== undefined && !trajectory.is_stale && (
        <div className="flex items-center gap-2 text-sm text-stone-600">
          <Clock className="w-4 h-4" />
          <span>
            Last inspected {trajectory.inspection_age_years!.toFixed(1)} years ago
          </span>
        </div>
      )}

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-stone-900">Inspection History</h3>
        <div className="space-y-4">
          {trajectory.history.map((inspection, index) => (
            <div
              key={inspection.id}
              className="border border-stone-200 rounded-lg p-4 hover:border-stone-300 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold border ${ratingColors[inspection.rating]}`}>
                      {inspection.rating}
                    </span>
                    {index === 0 && (
                      <span className="text-xs text-stone-500 font-medium">Current</span>
                    )}
                  </div>
                  <p className="text-sm text-stone-600">
                    Inspected {formatDate(inspection.inspection_date)}
                  </p>
                </div>
                {inspection.report_url && (
                  <a
                    href={inspection.report_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-brand-600 hover:text-brand-700 underline"
                  >
                    View report
                  </a>
                )}
              </div>

              {inspection.strengths_quote && (
                <div className="mb-2">
                  <p className="text-xs font-semibold text-stone-700 mb-1">Strengths:</p>
                  <p className="text-sm text-stone-600 italic">"{inspection.strengths_quote}"</p>
                </div>
              )}

              {inspection.improvements_quote && (
                <div>
                  <p className="text-xs font-semibold text-stone-700 mb-1">Areas for improvement:</p>
                  <p className="text-sm text-stone-600 italic">"{inspection.improvements_quote}"</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
