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

type FilterValue = boolean | null;

const FILTER_OPTIONS: { label: string; value: FilterValue; countFn: (clubs: HolidayClub[]) => number }[] = [
  { label: "All", value: null, countFn: (clubs) => clubs.length },
  { label: "School-run", value: true, countFn: (clubs) => clubs.filter((c) => c.is_school_run).length },
  { label: "External", value: false, countFn: (clubs) => clubs.filter((c) => !c.is_school_run).length },
];

export default function HolidayClubsList({ clubs, schoolName }: HolidayClubsListProps) {
  const [filterSchoolRun, setFilterSchoolRun] = useState<FilterValue>(null);

  if (!clubs || clubs.length === 0) {
    return (
      <div className="flex flex-col items-center rounded-xl border border-gray-200 bg-white py-12 px-6 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gray-100">
          <svg
            className="h-7 w-7 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="mt-4 text-base font-semibold text-gray-900">
          No holiday clubs listed
        </h3>
        <p className="mt-1.5 max-w-sm text-sm text-gray-500">
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
    <div className="space-y-5">
      {/* Header and Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Holiday Clubs{schoolName ? ` at ${schoolName}` : ""}
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Childcare provision during school holidays
          </p>
        </div>

        {/* Filter Toggle */}
        <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-1" role="group" aria-label="Filter holiday clubs">
          {FILTER_OPTIONS.map((option) => {
            const count = option.countFn(clubs);
            const isActive = filterSchoolRun === option.value;
            return (
              <button
                key={option.label}
                type="button"
                onClick={() => setFilterSchoolRun(option.value)}
                aria-pressed={isActive}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {option.label} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Info Box */}
      <details className="rounded-lg border border-blue-200 bg-blue-50">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-blue-900 hover:text-blue-700">
          What is the difference between school-run and external clubs?
        </summary>
        <div className="px-4 pb-3 text-sm text-blue-800">
          <strong>School-run clubs</strong> are operated by the school itself, while{' '}
          <strong>external providers</strong> rent the premises. Booking procedures
          and policies may differ.
        </div>
      </details>

      {/* Clubs Grid */}
      <div aria-live="polite">
        {filteredClubs.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {filteredClubs.map((club) => (
              <HolidayClubCard key={club.id} club={club} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center rounded-xl border border-gray-200 bg-white py-8 px-6 text-center">
            <p className="text-sm text-gray-500">
              No {filterSchoolRun ? 'school-run' : 'external'} holiday clubs found.
            </p>
            <button
              type="button"
              onClick={() => setFilterSchoolRun(null)}
              className="mt-3 text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
            >
              View all clubs
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
