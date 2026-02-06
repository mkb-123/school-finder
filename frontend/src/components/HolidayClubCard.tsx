import React from 'react';

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

  const formatCurrency = (amount: number | null) => {
    if (amount === null) return 'Contact for pricing';
    return `£${amount.toFixed(2)}`;
  };

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {club.provider_name}
          </h3>
          <span
            className={`inline-block px-2 py-1 text-xs font-medium rounded-full mt-1 ${
              club.is_school_run
                ? 'bg-blue-100 text-blue-800'
                : 'bg-purple-100 text-purple-800'
            }`}
          >
            {club.is_school_run ? 'School-run' : 'External Provider'}
          </span>
        </div>
      </div>

      {club.description && (
        <p className="text-sm text-gray-600 mb-3">{club.description}</p>
      )}

      <div className="grid grid-cols-2 gap-4 text-sm">
        {/* Age Range */}
        {(club.age_from !== null || club.age_to !== null) && (
          <div>
            <span className="font-medium text-gray-700">Ages:</span>{' '}
            <span className="text-gray-900">
              {club.age_from && club.age_to
                ? `${club.age_from}-${club.age_to}`
                : club.age_from
                ? `${club.age_from}+`
                : club.age_to
                ? `Up to ${club.age_to}`
                : 'All ages'}
            </span>
          </div>
        )}

        {/* Hours */}
        {(club.start_time || club.end_time) && (
          <div>
            <span className="font-medium text-gray-700">Hours:</span>{' '}
            <span className="text-gray-900">
              {formatTime(club.start_time)} - {formatTime(club.end_time)}
            </span>
          </div>
        )}

        {/* Daily Cost */}
        {club.cost_per_day !== null && (
          <div>
            <span className="font-medium text-gray-700">Daily:</span>{' '}
            <span className="text-gray-900">{formatCurrency(club.cost_per_day)}</span>
          </div>
        )}

        {/* Weekly Cost */}
        {club.cost_per_week !== null && (
          <div>
            <span className="font-medium text-gray-700">Weekly:</span>{' '}
            <span className="text-gray-900">
              {formatCurrency(club.cost_per_week)}
            </span>
          </div>
        )}
      </div>

      {/* Available Weeks */}
      {club.available_weeks && (
        <div className="mt-3 pt-3 border-t">
          <span className="font-medium text-gray-700 text-sm">Available:</span>
          <p className="text-sm text-gray-900 mt-1">{club.available_weeks}</p>
        </div>
      )}

      {/* Booking Link */}
      {club.booking_url && (
        <div className="mt-3">
          <a
            href={club.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            Book Online
            <svg
              className="ml-1 w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
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
    </div>
  );
}
