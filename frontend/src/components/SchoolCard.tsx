import { Link } from "react-router-dom";

interface SchoolCardProps {
  id?: number;
  name: string;
  type: string;
  ofstedRating: string;
  ofstedDate?: string | null;
  distance: string;
  isPrivate?: boolean;
  hasBreakfastClub?: boolean;
  hasAfterSchoolClub?: boolean;
  ethos?: string | null;
}

const RATING_COLORS: Record<string, string> = {
  Outstanding: "bg-green-100 text-green-800",
  Good: "bg-blue-100 text-blue-800",
  "Requires Improvement": "bg-amber-100 text-amber-800",
  Inadequate: "bg-red-100 text-red-800",
};

export default function SchoolCard({
  id,
  name,
  type,
  ofstedRating,
  ofstedDate,
  distance,
  isPrivate = false,
  hasBreakfastClub = false,
  hasAfterSchoolClub = false,
  ethos,
}: SchoolCardProps) {
  const badgeColor = RATING_COLORS[ofstedRating] ?? "bg-gray-100 text-gray-800";
  const linkTo = id
    ? isPrivate
      ? `/private-schools/${id}`
      : `/schools/${id}`
    : "#";

  return (
    <Link
      to={linkTo}
      className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{name}</h3>
          <p className="mt-0.5 text-sm text-gray-500">{type}</p>
          {ethos && (
            <p className="mt-1 text-sm italic text-gray-600">{ethos}</p>
          )}
        </div>
        {!isPrivate && (
          <div className="flex flex-col items-end gap-1">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeColor}`}
            >
              {ofstedRating}
            </span>
            {ofstedDate && (
              <span className="text-xs text-gray-400">
                Inspected: {ofstedDate}
              </span>
            )}
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center gap-2 text-sm text-gray-500">
        <span className="flex items-center">
          <svg
            className="mr-1 h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          {distance}
        </span>
        {hasBreakfastClub && (
          <span className="inline-flex items-center rounded-full bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-700">
            Breakfast
          </span>
        )}
        {hasAfterSchoolClub && (
          <span className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700">
            After-school
          </span>
        )}
      </div>
    </Link>
  );
}
