import { useCallback, useEffect, useMemo, useState } from "react";
import { GraduationCap, SlidersHorizontal, X } from "lucide-react";
import SchoolCard from "../components/SchoolCard";
import Map, { type School } from "../components/Map";
import { get } from "../api/client";

/** Private detail (fee info) as attached to an individual school response. */
interface PrivateDetailSummary {
  termly_fee: number | null;
  annual_fee: number | null;
  fee_age_group: string | null;
}

/** Extended school with optional private_details for fee previews. */
interface PrivateSchoolListItem extends School {
  private_details?: PrivateDetailSummary[];
  boarding_provision?: string | null;
  admissions_policy?: string | null;
  number_of_pupils?: number | null;
  has_sixth_form?: boolean | null;
  has_nursery?: boolean | null;
}

/** Format a currency amount as GBP with no decimals. */
function formatFeeShort(amount: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Derive a "fee range" display string from private_details, or null. */
function feeRangeLabel(details?: PrivateDetailSummary[]): string | null {
  if (!details || details.length === 0) return null;
  const termlyFees = details
    .map((d) => d.termly_fee)
    .filter((f): f is number => f != null);
  if (termlyFees.length === 0) return null;
  const min = Math.min(...termlyFees);
  const max = Math.max(...termlyFees);
  if (min === max) return `${formatFeeShort(min)}/term`;
  return `${formatFeeShort(min)} \u2013 ${formatFeeShort(max)}/term`;
}

/** Skeleton loader for school cards during loading. */
function SchoolCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-stone-200 border-l-4 border-l-private-200 bg-white p-4">
      <div className="flex items-start gap-2.5">
        <div className="h-8 w-8 rounded-lg bg-private-50" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded bg-stone-200" />
          <div className="h-3 w-1/2 rounded bg-stone-100" />
        </div>
        <div className="h-6 w-20 rounded-full bg-private-50" />
      </div>
      <div className="mt-3 h-3 w-2/3 rounded bg-stone-100" />
      <div className="mt-2 h-5 w-36 rounded bg-private-50/50" />
    </div>
  );
}

export default function PrivateSchools() {
  const [schools, setSchools] = useState<PrivateSchoolListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSchoolId, setSelectedSchoolId] = useState<number | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Filter state
  const [maxFee, setMaxFee] = useState<string>("");
  const [ageRange, setAgeRange] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [transportOnly, setTransportOnly] = useState(false);
  const [boardingOnly, setBoardingOnly] = useState(false);
  const [selectiveOnly, setSelectiveOnly] = useState<string>("");

  // Fetch all nearby private schools (not scoped to a single council)
  useEffect(() => {
    setLoading(true);
    setError(null);

    get<PrivateSchoolListItem[]>("/private-schools")
      .then((data) => setSchools(data))
      .catch((err) => setError(err.detail ?? "Failed to load private schools"))
      .finally(() => setLoading(false));
  }, []);

  const hasActiveFilters = ageRange !== "" || gender !== "" || transportOnly || maxFee !== "" || boardingOnly || selectiveOnly !== "";

  const clearFilters = useCallback(() => {
    setAgeRange("");
    setGender("");
    setTransportOnly(false);
    setMaxFee("");
    setBoardingOnly(false);
    setSelectiveOnly("");
  }, []);

  // Client-side filtering
  const filteredSchools = useMemo(() => {
    return schools.filter((s) => {
      // Age range filter
      if (ageRange) {
        const [minAge, maxAge] = ageRange.split("-").map(Number);
        if (s.age_range_from > maxAge || s.age_range_to < minAge) return false;
      }

      // Gender filter
      if (gender === "co-ed" && s.gender_policy !== "Mixed") return false;
      if (gender === "boys" && s.gender_policy !== "Boys" && s.gender_policy !== "Mixed") return false;
      if (gender === "girls" && s.gender_policy !== "Girls" && s.gender_policy !== "Mixed") return false;

      // Boarding filter
      if (boardingOnly && s.boarding_provision !== "Boarding school") return false;

      // Admissions policy filter
      if (selectiveOnly === "selective" && s.admissions_policy !== "Selective") return false;
      if (selectiveOnly === "non-selective" && s.admissions_policy !== "Non-selective") return false;

      return true;
    });
  }, [schools, ageRange, gender, boardingOnly, selectiveOnly]);

  const handleSchoolSelect = useCallback((id: number) => {
    setSelectedSchoolId((prev) => (prev === id ? null : id));
  }, []);

  const activeFilterCount = [ageRange, gender, transportOnly ? "t" : "", maxFee, boardingOnly ? "b" : "", selectiveOnly].filter(Boolean).length;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      {/* Page header */}
      <div className="mb-6 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-private-100 text-private-600">
            <GraduationCap className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">Private Schools</h1>
            <p className="mt-0.5 text-sm text-stone-600 sm:text-base">
              Browse independent and private schools in your area.
            </p>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 animate-scale-in" role="alert">
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-red-800">Unable to load schools</p>
            <p className="mt-0.5 text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Sticky summary bar — shows result count while scrolling */}
      {!loading && schools.length > 0 && (
        <div className="sticky top-14 z-30 -mx-4 mb-4 border-b border-stone-200 bg-white/95 px-4 py-2.5 sticky-header-blur sm:top-16 lg:hidden">
          <div className="flex items-center justify-between">
            <p className="text-sm text-stone-600" aria-live="polite">
              <span className="font-semibold text-stone-900">{filteredSchools.length}</span>
              {" "}of {schools.length} school{schools.length !== 1 ? "s" : ""}
              {hasActiveFilters && (
                <span className="ml-1.5 text-stone-400">
                  (filtered)
                </span>
              )}
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-private-600 transition-colors hover:bg-private-50"
              >
                <X className="h-3 w-3" aria-hidden="true" />
                Clear filters
              </button>
            )}
          </div>
        </div>
      )}

      {/* Mobile filter toggle */}
      <div className="mb-4 lg:hidden">
        <button
          type="button"
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm font-medium text-stone-700 shadow-sm transition-all duration-200 hover:bg-stone-50 active:scale-[0.99]"
          aria-expanded={filtersOpen}
          aria-controls="filter-panel"
        >
          <SlidersHorizontal className="h-4 w-4 text-stone-500" aria-hidden="true" />
          Filters
          {activeFilterCount > 0 && (
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-private-600 text-xs font-bold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-12">
        {/* Filter sidebar */}
        <aside
          id="filter-panel"
          className={`lg:col-span-3 transition-all duration-300 ease-smooth ${
            filtersOpen
              ? "max-h-[800px] opacity-100"
              : "max-h-0 overflow-hidden opacity-0 lg:max-h-none lg:opacity-100 lg:overflow-visible"
          }`}
          aria-label="Private school filters"
        >
          <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-stone-900">Filters</h2>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-sm font-medium text-private-600 hover:text-private-800 transition-colors duration-200"
                >
                  Clear all
                </button>
              )}
            </div>

            <div className="mt-4 space-y-5">
              {/* Max Termly Fee */}
              <div>
                <label
                  htmlFor="maxFee"
                  className="block text-sm font-medium text-stone-700"
                >
                  Max Termly Fee
                </label>
                <div className="relative mt-1">
                  <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-stone-400 text-sm">
                    &pound;
                  </span>
                  <input
                    id="maxFee"
                    type="number"
                    placeholder="e.g. 5000"
                    value={maxFee}
                    onChange={(e) => setMaxFee(e.target.value)}
                    className="block w-full rounded-lg border border-stone-300 py-2.5 pl-7 pr-3 text-sm shadow-sm transition-colors duration-200 focus:border-private-500 focus:outline-none focus:ring-2 focus:ring-private-500/20"
                  />
                </div>
                {maxFee && (
                  <p className="mt-1.5 text-xs text-stone-500 animate-fade-in">
                    Fee filtering is applied on individual school pages where detailed fee data is available.
                  </p>
                )}
              </div>

              {/* Age Range */}
              <div>
                <label
                  htmlFor="ageRange"
                  className="block text-sm font-medium text-stone-700"
                >
                  Age Range
                </label>
                <select
                  id="ageRange"
                  value={ageRange}
                  onChange={(e) => setAgeRange(e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm shadow-sm transition-colors duration-200 focus:border-private-500 focus:outline-none focus:ring-2 focus:ring-private-500/20"
                >
                  <option value="">Any age</option>
                  <option value="3-7">3-7 (Pre-prep)</option>
                  <option value="7-11">7-11 (Prep)</option>
                  <option value="11-16">11-16 (Senior)</option>
                  <option value="16-18">16-18 (Sixth Form)</option>
                </select>
              </div>

              {/* Gender Policy */}
              <div>
                <label
                  htmlFor="gender"
                  className="block text-sm font-medium text-stone-700"
                >
                  Gender Policy
                </label>
                <select
                  id="gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm shadow-sm transition-colors duration-200 focus:border-private-500 focus:outline-none focus:ring-2 focus:ring-private-500/20"
                >
                  <option value="">Any</option>
                  <option value="co-ed">Co-educational</option>
                  <option value="boys">Boys only</option>
                  <option value="girls">Girls only</option>
                </select>
              </div>

              {/* Admissions Policy */}
              <div>
                <label
                  htmlFor="selective"
                  className="block text-sm font-medium text-stone-700"
                >
                  Admissions
                </label>
                <select
                  id="selective"
                  value={selectiveOnly}
                  onChange={(e) => setSelectiveOnly(e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm shadow-sm transition-colors duration-200 focus:border-private-500 focus:outline-none focus:ring-2 focus:ring-private-500/20"
                >
                  <option value="">Any</option>
                  <option value="selective">Selective</option>
                  <option value="non-selective">Non-selective</option>
                </select>
              </div>

              {/* Transport checkbox with proper touch target */}
              <label
                htmlFor="transport"
                className="flex cursor-pointer items-center gap-3 rounded-lg p-2 -mx-2 transition-colors duration-200 hover:bg-stone-50"
              >
                <input
                  id="transport"
                  type="checkbox"
                  checked={transportOnly}
                  onChange={(e) => setTransportOnly(e.target.checked)}
                  className="h-5 w-5 rounded border-stone-300 text-private-600 focus:ring-2 focus:ring-private-500"
                />
                <span className="text-sm text-stone-700">
                  Provides transport
                </span>
              </label>

              {/* Boarding checkbox */}
              <label
                htmlFor="boarding"
                className="flex cursor-pointer items-center gap-3 rounded-lg p-2 -mx-2 transition-colors duration-200 hover:bg-stone-50"
              >
                <input
                  id="boarding"
                  type="checkbox"
                  checked={boardingOnly}
                  onChange={(e) => setBoardingOnly(e.target.checked)}
                  className="h-5 w-5 rounded border-stone-300 text-private-600 focus:ring-2 focus:ring-private-500"
                />
                <span className="text-sm text-stone-700">
                  Boarding schools only
                </span>
              </label>

              {/* Result count in sidebar (desktop) */}
              <div
                className="rounded-lg bg-private-50/50 px-3 py-2.5 text-center text-sm text-stone-600 transition-all duration-200"
                aria-live="polite"
              >
                <span className="font-semibold text-private-900 animate-count-up">{filteredSchools.length}</span>
                {" "}of {schools.length} private school{schools.length !== 1 ? "s" : ""}
              </div>
            </div>
          </div>
        </aside>

        {/* School cards list */}
        <section className="space-y-3 lg:col-span-4" aria-label="Private school results" aria-live="polite">
          {/* Loading skeleton */}
          {loading && (
            <div className="space-y-3">
              <SchoolCardSkeleton />
              <SchoolCardSkeleton />
              <SchoolCardSkeleton />
              <SchoolCardSkeleton />
              <SchoolCardSkeleton />
            </div>
          )}

          {/* Empty state */}
          {!loading && filteredSchools.length === 0 && (
            <div className="flex flex-col items-center rounded-xl border border-dashed border-stone-300 bg-white py-14 px-6 text-center animate-fade-in-up">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-private-50">
                <GraduationCap className="h-8 w-8 text-private-300" aria-hidden="true" />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-stone-900">
                {schools.length === 0 ? "No private schools found" : "No schools match your filters"}
              </h3>
              <p className="mt-2 max-w-sm text-sm leading-relaxed text-stone-500">
                {schools.length === 0
                  ? "We haven't found any private schools in this area yet."
                  : "Try widening your search criteria or removing some filters to see more results."}
              </p>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="mt-5 rounded-lg bg-private-600 px-5 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:bg-private-700 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-private-500 focus:ring-offset-2"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}

          {/* School cards with staggered entrance */}
          {!loading && filteredSchools.map((s, idx) => (
            <div
              key={s.id}
              role="button"
              tabIndex={0}
              onClick={() => handleSchoolSelect(s.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleSchoolSelect(s.id);
                }
              }}
              aria-pressed={selectedSchoolId === s.id}
              className={`cursor-pointer rounded-xl transition-all duration-200 ease-smooth focus:outline-none focus:ring-2 focus:ring-private-500 focus:ring-offset-2 animate-fade-in-up ${
                selectedSchoolId === s.id
                  ? "ring-2 ring-private-500 ring-offset-1"
                  : ""
              }`}
              style={{ animationDelay: `${Math.min(idx * 0.04, 0.4)}s`, animationFillMode: 'both' }}
            >
              <SchoolCard
                id={s.id}
                name={s.name}
                type={s.type ?? "Independent"}
                ofstedRating={s.ofsted_rating ?? "Not rated"}
                distance={
                  s.postcode
                    ? s.postcode
                    : `Ages ${s.age_range_from}\u2013${s.age_range_to}`
                }
                isPrivate={true}
                ethos={s.ethos}
                ageRange={`${s.age_range_from}\u2013${s.age_range_to}`}
                feeRange={feeRangeLabel(s.private_details)}
                boarding={s.boarding_provision === "Boarding school"}
                selective={s.admissions_policy === "Selective"}
                pupils={s.number_of_pupils ?? undefined}
              />
            </div>
          ))}
        </section>

        {/* Map */}
        <section className="h-[350px] sm:h-[500px] lg:col-span-5 lg:h-auto lg:min-h-[600px] lg:sticky lg:top-20" aria-label="Private schools map">
          <Map
            schools={filteredSchools}
            selectedSchoolId={selectedSchoolId}
            onSchoolSelect={handleSchoolSelect}
          />
        </section>
      </div>
    </main>
  );
}
