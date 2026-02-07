import { Link } from "react-router-dom";
import { MapPin, ChevronRight, Sun, BookOpen } from "lucide-react";

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
  ageRange?: string | null;
}

const RATING_STYLES: Record<string, { badge: string; dot: string }> = {
  Outstanding: {
    badge: "bg-green-100 text-green-800 ring-1 ring-green-600/20",
    dot: "bg-green-500",
  },
  Good: {
    badge: "bg-blue-100 text-blue-800 ring-1 ring-blue-600/20",
    dot: "bg-blue-500",
  },
  "Requires Improvement": {
    badge: "bg-amber-100 text-amber-800 ring-1 ring-amber-600/20",
    dot: "bg-amber-500",
  },
  Inadequate: {
    badge: "bg-red-100 text-red-800 ring-1 ring-red-600/20",
    dot: "bg-red-500",
  },
};

const DEFAULT_STYLE = {
  badge: "bg-gray-100 text-gray-600 ring-1 ring-gray-300/50",
  dot: "bg-gray-400",
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
  ageRange,
}: SchoolCardProps) {
  const ratingStyle = RATING_STYLES[ofstedRating] ?? DEFAULT_STYLE;
  const linkTo = id
    ? isPrivate
      ? `/private-schools/${id}`
      : `/schools/${id}`
    : "#";

  return (
    <Link
      to={linkTo}
      className="group block rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-all hover:border-gray-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
    >
      {/* Top row: name + Ofsted badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold leading-snug text-gray-900 group-hover:text-blue-700 transition-colors">
            {name}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
            <span>{type}</span>
            {ageRange && (
              <>
                <span aria-hidden="true" className="text-gray-300">|</span>
                <span>Ages {ageRange}</span>
              </>
            )}
          </div>
        </div>

        {/* Ofsted badge - prominent placement */}
        <div className="flex flex-shrink-0 flex-col items-end gap-1">
          {!isPrivate && (
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${ratingStyle.badge}`}
            >
              {ofstedRating}
            </span>
          )}
          {isPrivate && (
            <span className="inline-flex items-center rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700 ring-1 ring-violet-600/20">
              Independent
            </span>
          )}
        </div>
      </div>

      {/* Ethos - readable, not italic */}
      {ethos && (
        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-gray-600">
          {ethos}
        </p>
      )}

      {/* Bottom row: distance, clubs, chevron */}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {/* Distance */}
          <span className="inline-flex items-center gap-1 text-sm text-gray-600">
            <MapPin className="h-3.5 w-3.5 text-gray-400" aria-hidden="true" />
            {distance}
          </span>

          {/* Club badges */}
          {hasBreakfastClub && (
            <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-700 ring-1 ring-orange-600/10">
              <Sun className="h-3 w-3" aria-hidden="true" />
              Breakfast club
            </span>
          )}
          {hasAfterSchoolClub && (
            <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 ring-1 ring-purple-600/10">
              <BookOpen className="h-3 w-3" aria-hidden="true" />
              After-school
            </span>
          )}
        </div>

        {/* Chevron - visual affordance for clickability */}
        <ChevronRight
          className="h-4 w-4 flex-shrink-0 text-gray-300 transition-transform group-hover:translate-x-0.5 group-hover:text-gray-500"
          aria-hidden="true"
        />
      </div>

      {/* Ofsted inspection date - subtle */}
      {!isPrivate && ofstedDate && (
        <p className="mt-2 text-xs text-gray-400">
          Last inspected {ofstedDate}
        </p>
      )}
    </Link>
  );
}
