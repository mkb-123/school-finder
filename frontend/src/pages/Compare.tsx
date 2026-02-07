import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { get } from "../api/client";
import {
  ArrowLeft,
  GitCompareArrows,
  X,
  Trophy,
  ExternalLink,
} from "lucide-react";

interface Performance {
  id: number;
  school_id: number;
  metric_type: string;
  metric_value: string;
  year: number;
  source_url: string | null;
}

interface Club {
  id: number;
  club_type: string;
  name: string;
}

interface CompareSchool {
  id: number;
  name: string;
  type: string | null;
  ofsted_rating: string | null;
  ofsted_date: string | null;
  age_range_from: number | null;
  age_range_to: number | null;
  gender_policy: string | null;
  faith: string | null;
  distance_km: number | null;
  catchment_radius_km: number | null;
  is_private: boolean;
  clubs: Club[];
  performance: Performance[];
  ethos: string | null;
}

interface CompareResponse {
  schools: CompareSchool[];
}

const OFSTED_RANK: Record<string, number> = {
  Outstanding: 4,
  Good: 3,
  "Requires improvement": 2,
  Inadequate: 1,
};

const RATING_STYLES: Record<string, string> = {
  Outstanding: "text-green-700 font-semibold",
  Good: "text-blue-700 font-semibold",
  "Requires improvement": "text-amber-700 font-semibold",
  Inadequate: "text-red-700 font-semibold",
};

const RATING_BADGES: Record<string, string> = {
  Outstanding: "bg-green-100 text-green-800 ring-1 ring-green-600/20",
  Good: "bg-blue-100 text-blue-800 ring-1 ring-blue-600/20",
  "Requires improvement": "bg-amber-100 text-amber-800 ring-1 ring-amber-600/20",
  Inadequate: "bg-red-100 text-red-800 ring-1 ring-red-600/20",
};

/** Get the latest year's metric value for a given metric type. */
function latestMetric(
  performance: Performance[],
  metricType: string,
): string | null {
  const matches = performance
    .filter((p) => p.metric_type === metricType)
    .sort((a, b) => b.year - a.year);
  return matches.length > 0 ? matches[0].metric_value : null;
}

/** Colour Progress 8 values: green if positive, red if negative. */
function Progress8Cell({ value }: { value: string | null }) {
  if (!value) return <span className="text-gray-400">&mdash;</span>;
  const num = parseFloat(value);
  let cls = "text-gray-900";
  if (!isNaN(num)) {
    if (num > 0) cls = "text-green-700 font-semibold";
    else if (num < 0) cls = "text-red-700 font-semibold";
  }
  return <span className={cls}>{value}</span>;
}

/**
 * Determine if a value is the "best" in its row for highlighting.
 * Returns true if this school has the best (or tied-best) value.
 */
function isBestOfsted(school: CompareSchool, schools: CompareSchool[]): boolean {
  const rank = OFSTED_RANK[school.ofsted_rating ?? ""] ?? 0;
  if (rank === 0) return false;
  const maxRank = Math.max(...schools.map((s) => OFSTED_RANK[s.ofsted_rating ?? ""] ?? 0));
  return rank === maxRank && maxRank > 0;
}

function isClosest(school: CompareSchool, schools: CompareSchool[]): boolean {
  if (school.distance_km == null) return false;
  const distances = schools
    .map((s) => s.distance_km)
    .filter((d): d is number => d != null);
  if (distances.length === 0) return false;
  return school.distance_km === Math.min(...distances);
}

/** Skeleton loading rows for the comparison table. */
function CompareSkeletonRow({ colCount }: { colCount: number }) {
  return (
    <tr>
      <td className="whitespace-nowrap px-4 py-3">
        <div className="h-4 w-28 animate-pulse rounded bg-gray-200" />
      </td>
      {Array.from({ length: colCount }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-20 animate-pulse rounded bg-gray-200" />
        </td>
      ))}
    </tr>
  );
}

export default function Compare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const ids = searchParams.get("ids")?.split(",").filter(Boolean) ?? [];
  const [schools, setSchools] = useState<CompareSchool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ids.length === 0) return;
    setLoading(true);
    setError(null);
    get<CompareResponse>(`/compare`, { ids: ids.join(",") })
      .then((data) => setSchools(data.schools))
      .catch(() => {
        setSchools([]);
        setError("Could not load comparison data. Please try again.");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);

  /** Remove a school from the comparison by filtering out its ID. */
  function removeSchool(schoolId: number) {
    const newIds = ids.filter((id) => id !== String(schoolId));
    if (newIds.length === 0) {
      setSearchParams({});
      setSchools([]);
    } else {
      setSearchParams({ ids: newIds.join(",") });
    }
  }

  // Determine whether to show primary or secondary metrics
  const hasPrimary = schools.some((s) =>
    s.performance.some((p) => p.metric_type === "SATs"),
  );
  const hasSecondary = schools.some((s) =>
    s.performance.some((p) => p.metric_type === "GCSE"),
  );
  const hasDistance = schools.some((s) => s.distance_km != null);

  /**
   * Render a comparison row with optional "best" highlighting.
   * The isBest callback determines which schools get the winner indicator.
   */
  function CompareRow({
    label,
    renderCell,
    isBest,
    isEven,
  }: {
    label: string;
    renderCell: (school: CompareSchool) => React.ReactNode;
    isBest?: (school: CompareSchool) => boolean;
    isEven: boolean;
  }) {
    return (
      <tr className={isEven ? "bg-gray-50/50" : "bg-white"}>
        <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900 sticky left-0 z-10 bg-inherit">
          {label}
        </td>
        {schools.map((s) => {
          const best = isBest?.(s) && schools.length > 1;
          return (
            <td
              key={s.id}
              className={`px-4 py-3 text-sm ${best ? "relative" : ""}`}
            >
              <div className="flex items-center gap-1.5">
                {renderCell(s)}
                {best && (
                  <Trophy
                    className="h-3.5 w-3.5 flex-shrink-0 text-amber-500"
                    aria-label="Best value"
                  />
                )}
              </div>
            </td>
          );
        })}
      </tr>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      {/* Back navigation */}
      <Link
        to="/schools"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to schools
      </Link>

      <div className="mt-4">
        <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">Compare schools</h1>
        <p className="mt-1 text-sm text-gray-600 sm:text-base">
          See how your shortlisted schools stack up side by side.
        </p>
      </div>

      {/* Empty state - no schools selected */}
      {ids.length === 0 && (
        <div className="mt-8 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <GitCompareArrows className="mx-auto h-12 w-12 text-gray-300" aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            No schools selected
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Head to the school list and tap on schools you&apos;d like to compare.
            You can compare up to 4 schools at a time.
          </p>
          <Link
            to="/schools"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Browse schools
          </Link>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && ids.length > 0 && (
        <div className="mt-8 overflow-hidden rounded-xl border border-gray-200 shadow-sm">
          <table className="min-w-full" aria-label="Loading comparison data">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3"><div className="h-4 w-16 animate-pulse rounded bg-gray-200" /></th>
                {ids.map((id) => (
                  <th key={id} className="px-4 py-3">
                    <div className="h-5 w-32 animate-pulse rounded bg-gray-200" />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {[1, 2, 3, 4, 5, 6].map((row) => (
                <CompareSkeletonRow key={row} colCount={ids.length} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Comparison table */}
      {!loading && schools.length > 0 && (
        <>
          {/* School header cards - above table on mobile for context */}
          <div className="mt-6 grid gap-3 sm:hidden" style={{ gridTemplateColumns: `repeat(${schools.length}, minmax(0, 1fr))` }}>
            {schools.map((s) => {
              const ratingBadge = RATING_BADGES[s.ofsted_rating ?? ""] ?? "bg-gray-100 text-gray-600 ring-1 ring-gray-300/50";
              return (
                <div key={s.id} className="rounded-lg border border-gray-200 bg-white p-3 text-center">
                  <Link
                    to={s.is_private ? `/private-schools/${s.id}` : `/schools/${s.id}`}
                    className="text-sm font-semibold text-gray-900 hover:text-blue-600 transition-colors"
                  >
                    {s.name}
                  </Link>
                  {s.ofsted_rating && (
                    <div className="mt-1.5">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${ratingBadge}`}>
                        {s.ofsted_rating}
                      </span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => removeSchool(s.id)}
                    className="mt-2 inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-500 transition-colors"
                    aria-label={`Remove ${s.name} from comparison`}
                  >
                    <X className="h-3 w-3" aria-hidden="true" />
                    Remove
                  </button>
                </div>
              );
            })}
          </div>

          {/* Scrollable table with sticky first column */}
          <div className="relative mt-4 sm:mt-8">
            {/* Scroll indicator fade on right edge */}
            <div className="pointer-events-none absolute right-0 top-0 bottom-0 z-20 w-6 bg-gradient-to-l from-gray-50 to-transparent sm:hidden" aria-hidden="true" />

            <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
              <table
                className="min-w-full divide-y divide-gray-200 overflow-hidden rounded-xl border border-gray-200 shadow-sm"
                aria-label="School comparison"
              >
                {/* Sticky header row with school names */}
                <thead className="bg-gray-50">
                  <tr>
                    <th className="sticky left-0 z-10 bg-gray-50 px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      <span className="sr-only">Metric</span>
                    </th>
                    {schools.map((s) => (
                      <th
                        key={s.id}
                        className="px-4 py-4 text-left"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <Link
                            to={s.is_private ? `/private-schools/${s.id}` : `/schools/${s.id}`}
                            className="group hidden sm:block"
                          >
                            <span className="text-sm font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                              {s.name}
                            </span>
                            <ExternalLink className="ml-1 inline h-3 w-3 text-gray-300 group-hover:text-blue-400" aria-hidden="true" />
                          </Link>
                          <button
                            type="button"
                            onClick={() => removeSchool(s.id)}
                            className="hidden flex-shrink-0 rounded p-1 text-gray-300 transition-colors hover:bg-red-50 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-red-500 sm:block"
                            aria-label={`Remove ${s.name} from comparison`}
                          >
                            <X className="h-4 w-4" aria-hidden="true" />
                          </button>
                        </div>
                        {/* Mobile: just show abbreviated name */}
                        <span className="text-xs font-semibold text-gray-900 sm:hidden">
                          {s.name}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {/* Ofsted Rating */}
                  <CompareRow
                    label="Ofsted rating"
                    isEven={false}
                    isBest={(s) => isBestOfsted(s, schools)}
                    renderCell={(s) => {
                      const style = RATING_STYLES[s.ofsted_rating ?? ""] ?? "text-gray-400";
                      return <span className={style}>{s.ofsted_rating ?? <>&mdash;</>}</span>;
                    }}
                  />

                  {/* Last Inspection */}
                  <CompareRow
                    label="Last inspection"
                    isEven={true}
                    renderCell={(s) => (
                      <span className="text-gray-600">{s.ofsted_date ?? <>&mdash;</>}</span>
                    )}
                  />

                  {/* School Type */}
                  <CompareRow
                    label="School type"
                    isEven={false}
                    renderCell={(s) => (
                      <span className="text-gray-600">
                        {s.is_private ? "Independent" : s.type ?? <>&mdash;</>}
                      </span>
                    )}
                  />

                  {/* Age Range */}
                  <CompareRow
                    label="Age range"
                    isEven={true}
                    renderCell={(s) => (
                      <span className="text-gray-600">
                        {s.age_range_from != null && s.age_range_to != null
                          ? `${s.age_range_from}\u2013${s.age_range_to} years`
                          : <>&mdash;</>}
                      </span>
                    )}
                  />

                  {/* Distance - with "closest" highlight */}
                  {hasDistance && (
                    <CompareRow
                      label="Distance"
                      isEven={false}
                      isBest={(s) => isClosest(s, schools)}
                      renderCell={(s) => (
                        <span className="text-gray-600">
                          {s.distance_km != null
                            ? `${s.distance_km.toFixed(1)} km`
                            : <>&mdash;</>}
                        </span>
                      )}
                    />
                  )}

                  {/* Catchment radius */}
                  <CompareRow
                    label="Catchment radius"
                    isEven={hasDistance ? true : false}
                    renderCell={(s) => (
                      <span className="text-gray-600">
                        {s.catchment_radius_km != null
                          ? `${s.catchment_radius_km} km`
                          : <>&mdash;</>}
                      </span>
                    )}
                  />

                  {/* Gender */}
                  <CompareRow
                    label="Gender policy"
                    isEven={hasDistance ? false : true}
                    renderCell={(s) => (
                      <span className="text-gray-600">{s.gender_policy ?? <>&mdash;</>}</span>
                    )}
                  />

                  {/* Faith */}
                  <CompareRow
                    label="Faith"
                    isEven={hasDistance ? true : false}
                    renderCell={(s) => (
                      <span className="text-gray-600">{s.faith ?? "None"}</span>
                    )}
                  />

                  {/* Ethos */}
                  <CompareRow
                    label="Ethos"
                    isEven={hasDistance ? false : true}
                    renderCell={(s) => (
                      <span className="text-gray-500 italic text-xs leading-relaxed">
                        {s.ethos ? `"${s.ethos}"` : <>&mdash;</>}
                      </span>
                    )}
                  />

                  {/* Breakfast Club */}
                  <CompareRow
                    label="Breakfast club"
                    isEven={hasDistance ? true : false}
                    renderCell={(s) => {
                      const has = s.clubs.some((c) => c.club_type === "breakfast");
                      return has ? (
                        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-600/10">
                          Available
                        </span>
                      ) : (
                        <span className="text-gray-400">&mdash;</span>
                      );
                    }}
                  />

                  {/* After-School Club */}
                  <CompareRow
                    label="After-school club"
                    isEven={hasDistance ? false : true}
                    renderCell={(s) => {
                      const has = s.clubs.some((c) => c.club_type === "after_school");
                      return has ? (
                        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-600/10">
                          Available
                        </span>
                      ) : (
                        <span className="text-gray-400">&mdash;</span>
                      );
                    }}
                  />

                  {/* Performance - SATs (primary) */}
                  {hasPrimary && (
                    <>
                      <CompareRow
                        label="SATs (Expected)"
                        isEven={true}
                        renderCell={(s) => (
                          <span className="text-gray-600">
                            {latestMetric(s.performance, "SATs") ?? <>&mdash;</>}
                          </span>
                        )}
                      />
                      <CompareRow
                        label="SATs (Higher)"
                        isEven={false}
                        renderCell={(s) => (
                          <span className="text-gray-600">
                            {latestMetric(s.performance, "SATs_Higher") ?? <>&mdash;</>}
                          </span>
                        )}
                      />
                    </>
                  )}

                  {/* Performance - GCSE (secondary) */}
                  {hasSecondary && (
                    <>
                      <CompareRow
                        label="GCSE results"
                        isEven={true}
                        renderCell={(s) => (
                          <span className="text-gray-600">
                            {latestMetric(s.performance, "GCSE") ?? <>&mdash;</>}
                          </span>
                        )}
                      />
                      <CompareRow
                        label="Progress 8"
                        isEven={false}
                        renderCell={(s) => (
                          <Progress8Cell value={latestMetric(s.performance, "Progress8")} />
                        )}
                      />
                      <CompareRow
                        label="Attainment 8"
                        isEven={true}
                        renderCell={(s) => (
                          <span className="text-gray-600">
                            {latestMetric(s.performance, "Attainment8") ?? <>&mdash;</>}
                          </span>
                        )}
                      />
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Helpful tip */}
          <p className="mt-4 text-center text-xs text-gray-400">
            <Trophy className="mr-1 inline h-3 w-3 text-amber-400" aria-hidden="true" />
            Trophy icon highlights the best value in each row across the schools being compared.
          </p>
        </>
      )}

      {/* No results for given IDs */}
      {!loading && ids.length > 0 && schools.length === 0 && !error && (
        <div className="mt-8 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <GitCompareArrows className="mx-auto h-10 w-10 text-gray-300" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-semibold text-gray-900">
            No matching schools found
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            We couldn&apos;t find any schools matching your selection.
            Try browsing schools and adding them to compare.
          </p>
          <Link
            to="/schools"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Browse schools
          </Link>
        </div>
      )}
    </main>
  );
}
