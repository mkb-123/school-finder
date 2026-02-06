import { useState } from 'react';
import HolidayClubCard from './HolidayClubCard';

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

interface HolidayClubsListProps {
  clubs: HolidayClub[];
  schoolName?: string;
}

export default function HolidayClubsList({ clubs, schoolName }: HolidayClubsListProps) {
  const [filterSchoolRun, setFilterSchoolRun] = useState<boolean | null>(null);

  if (!clubs || clubs.length === 0) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">
          No holiday clubs listed
        </h3>
        <p className="mt-1 text-sm text-gray-500">
          Holiday club information is not currently available for this school.
        </p>
      </div>
    );
  }

  const filteredClubs =
    filterSchoolRun === null
      ? clubs
      : clubs.filter((club) => club.is_school_run === filterSchoolRun);

  return (
    <div className="space-y-4">
      {/* Header and Filters */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Holiday Clubs {schoolName && `at ${schoolName}`}
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            Childcare provision during school holidays
          </p>
        </div>

        {/* Filter Toggle */}
        <div className="flex items-center space-x-2 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setFilterSchoolRun(null)}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              filterSchoolRun === null
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            All ({clubs.length})
          </button>
          <button
            onClick={() => setFilterSchoolRun(true)}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              filterSchoolRun === true
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            School-run ({clubs.filter((c) => c.is_school_run).length})
          </button>
          <button
            onClick={() => setFilterSchoolRun(false)}
            className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              filterSchoolRun === false
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            External ({clubs.filter((c) => !c.is_school_run).length})
          </button>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm">
        <p className="text-blue-900">
          <strong>School-run clubs</strong> are operated by the school itself, while{' '}
          <strong>external providers</strong> rent the premises. Booking procedures
          and policies may differ.
        </p>
      </div>

      {/* Clubs Grid */}
      {filteredClubs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredClubs.map((club) => (
            <HolidayClubCard key={club.id} club={club} />
          ))}
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p className="text-sm text-gray-600">
            No {filterSchoolRun ? 'school-run' : 'external'} holiday clubs found.
          </p>
        </div>
      )}
    </div>
  );
}
