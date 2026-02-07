interface HolidayClub {
  id: number;
  school_id: number;
  provider_name: string;
  is_school_run: boolean;
  description: string | null;
  age_from: number | null;
  age_to: number | null;
  start_time: string | null;
  end_time: string | null;
  cost_per_day: number | null;
  cost_per_week: number | null;
  available_weeks: string | null;
  booking_url: string | null;
}

interface HolidayClubCardProps {
  club: HolidayClub;
}

export default function HolidayClubCard({ club }: HolidayClubCardProps) {
  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return '';
    const [hours, minutes] = timeStr.split(':');
    return `${hours}:${minutes}`;
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const hasAgeInfo = club.age_from !== null || club.age_to !== null;
  const hasTimeInfo = club.start_time || club.end_time;
  const hasCostInfo = club.cost_per_day !== null || club.cost_per_week !== null;

  return (
    <article className="rounded-xl border border-gray-200 bg-white p-4 sm:p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-gray-900">
            {club.provider_name}
          </h3>
          <span
            className={`mt-1.5 inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${
              club.is_school_run
                ? 'bg-blue-50 text-blue-800 ring-blue-600/20'
                : 'bg-purple-50 text-purple-800 ring-purple-600/20'
            }`}
          >
            {club.is_school_run ? 'School-run' : 'External provider'}
          </span>
        </div>
      </div>

      {club.description && (
        <p className="mt-3 text-sm leading-relaxed text-gray-600">{club.description}</p>
      )}

      {/* Details grid */}
      {(hasAgeInfo || hasTimeInfo || hasCostInfo) && (
        <div className="mt-4 space-y-3">
          {/* Age and Hours row */}
          <div className="flex flex-wrap gap-4">
            {hasAgeInfo && (
              <div className="text-sm">
                <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Ages</span>
                <p className="mt-0.5 font-medium text-gray-900">
                  {club.age_from && club.age_to
                    ? `${club.age_from}-${club.age_to}`
                    : club.age_from
                    ? `${club.age_from}+`
                    : club.age_to
                    ? `Up to ${club.age_to}`
                    : 'All ages'}
                </p>
              </div>
            )}

            {hasTimeInfo && (
              <div className="text-sm">
                <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Hours</span>
                <p className="mt-0.5 font-medium text-gray-900">
                  {formatTime(club.start_time)} - {formatTime(club.end_time)}
                </p>
              </div>
            )}
          </div>

          {/* Cost row */}
          {hasCostInfo && (
            <div className="flex flex-wrap gap-4 rounded-lg bg-gray-50 border border-gray-100 p-3">
              {club.cost_per_day !== null && (
                <div className="text-sm">
                  <span className="text-xs font-medium text-gray-500">Daily</span>
                  <p className="mt-0.5 font-semibold text-gray-900">{formatCurrency(club.cost_per_day)}</p>
                </div>
              )}
              {club.cost_per_week !== null && (
                <div className="text-sm">
                  <span className="text-xs font-medium text-gray-500">Weekly</span>
                  <p className="mt-0.5 font-semibold text-gray-900">{formatCurrency(club.cost_per_week)}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Available Weeks */}
      {club.available_weeks && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Availability</p>
          <p className="mt-1 text-sm text-gray-700">{club.available_weeks}</p>
        </div>
      )}

      {/* Booking Link */}
      {club.booking_url && (
        <div className="mt-4">
          <a
            href={club.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Book online with ${club.provider_name}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 transition hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Book online
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>
      )}
    </article>
  );
}
