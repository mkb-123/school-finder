import { Link } from "react-router-dom";
import { MapPin, ChevronRight, Sun, BookOpen, GraduationCap, School } from "lucide-react";

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
  postcode?: string;
  /** Fee range string for private schools, e.g. "3,500 - 6,200 per term" */
  feeRange?: string | null;
  /** Whether the school offers boarding */
  boarding?: boolean;
  /** Whether the school is academically selective */
  selective?: boolean;
  /** Number of pupils on roll */
  pupils?: number;
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
  badge: "bg-stone-100 text-stone-600 ring-1 ring-stone-300/50",
  dot: "bg-stone-400",
};

const RATING_BORDER: Record<string, string> = {
  Outstanding: "border-l-green-500",
  Good: "border-l-blue-500",
  "Requires Improvement": "border-l-amber-500",
  Inadequate: "border-l-red-500",
};

const DEFAULT_BORDER = "border-l-stone-300";

/** Border colour for private school cards — always violet */
const PRIVATE_BORDER = "border-l-private-500";

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
  postcode,
  feeRange,
  boarding,
  selective,
  pupils,
}: SchoolCardProps) {
  const ratingStyle = RATING_STYLES[ofstedRating] ?? DEFAULT_STYLE;
  const borderColor = isPrivate
    ? PRIVATE_BORDER
    : (RATING_BORDER[ofstedRating] ?? DEFAULT_BORDER);
  const basePath = id
    ? isPrivate
      ? `/private-schools/${id}`
      : `/schools/${id}`
    : "#";
  const linkTo = postcode ? `${basePath}?postcode=${encodeURIComponent(postcode)}` : basePath;

  // Private schools get a violet-tinted hover; state schools use brand teal
  const hoverAccent = isPrivate
    ? "hover:border-private-300 hover:shadow-md hover:shadow-private-100/50"
    : "hover:border-stone-300 hover:shadow-md";

  const nameHoverColor = isPrivate
    ? "group-hover:text-private-700"
    : "group-hover:text-brand-700";

  return (
    <Link
      to={linkTo}
      className={`group block rounded-xl border border-stone-200 border-l-4 ${borderColor} bg-white p-4 shadow-sm transition-all duration-200 ease-smooth ${hoverAccent} focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2`}
    >
      {/* Top row: type icon + name + badges */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2.5">
            {/* School type icon */}
            <div
              className={`mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg transition-colors duration-200 ${
                isPrivate
                  ? "bg-private-50 text-private-500 group-hover:bg-private-100"
                  : "bg-stone-100 text-stone-400 group-hover:bg-brand-50 group-hover:text-brand-500"
              }`}
              aria-hidden="true"
            >
              {isPrivate ? (
                <GraduationCap className="h-4 w-4" />
              ) : (
                <School className="h-4 w-4" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <h3 className={`text-base font-semibold leading-snug text-stone-900 ${nameHoverColor} transition-colors duration-200`}>
                {name}
              </h3>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-stone-500">
                <span>{type}</span>
                {ageRange && (
                  <>
                    <span aria-hidden="true" className="text-stone-300">|</span>
                    <span>Ages {ageRange}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Badges — Ofsted rating (state schools only) */}
        {!isPrivate && (
          <div className="flex flex-shrink-0 flex-col items-end gap-1.5">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${ratingStyle.badge}`}
            >
              {ofstedRating}
            </span>
          </div>
        )}
      </div>

      {/* Ethos — readable, not italic */}
      {ethos && (
        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-stone-600">
          {ethos}
        </p>
      )}

      {/* Fee range and tags for private schools */}
      {isPrivate && (feeRange || boarding || selective != null || pupils != null) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {feeRange && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-private-50/70 px-2.5 py-1 text-xs font-medium text-private-800">
              <svg className="h-3.5 w-3.5 text-private-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {feeRange}
            </span>
          )}
          {boarding && (
            <span className="inline-flex items-center rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-600/20">
              Boarding
            </span>
          )}
          {selective && (
            <span className="inline-flex items-center rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-600/20">
              Selective
            </span>
          )}
          {pupils != null && (
            <span className="inline-flex items-center rounded-md bg-stone-50 px-2 py-1 text-xs text-stone-500">
              {pupils.toLocaleString()} pupils
            </span>
          )}
        </div>
      )}

      {/* Bottom row: distance, clubs, chevron */}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {/* Distance */}
          <span className="inline-flex items-center gap-1 text-sm text-stone-600">
            <MapPin className="h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
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

        {/* Chevron — visual affordance for clickability */}
        <ChevronRight
          className={`h-4 w-4 flex-shrink-0 transition-all duration-200 ${
            isPrivate
              ? "text-private-200 group-hover:translate-x-0.5 group-hover:text-private-500"
              : "text-stone-300 group-hover:translate-x-0.5 group-hover:text-stone-500"
          }`}
          aria-hidden="true"
        />
      </div>

      {/* Ofsted inspection date — subtle */}
      {!isPrivate && ofstedDate && (
        <p className="mt-2 text-xs text-stone-400">
          Last inspected {ofstedDate}
        </p>
      )}
    </Link>
  );
}
