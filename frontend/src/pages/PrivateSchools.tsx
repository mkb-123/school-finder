import { useCallback, useEffect, useMemo, useState } from "react";
import SchoolCard from "../components/SchoolCard";
import Map, { type School } from "../components/Map";
import { get } from "../api/client";

/** Skeleton loader for school cards during loading. */
function SchoolCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-stone-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded bg-stone-200" />
          <div className="h-3 w-1/2 rounded bg-stone-100" />
        </div>
        <div className="h-6 w-20 rounded-full bg-violet-100" />
      </div>
      <div className="mt-3 h-3 w-2/3 rounded bg-stone-100" />
    </div>
  );
}

export default function PrivateSchools() {
  const [schools, setSchools] = useState<School[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSchoolId, setSelectedSchoolId] = useState<number | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Council selection
  const [councils, setCouncils] = useState<string[]>([]);
  const [selectedCouncil, setSelectedCouncil] = useState<string>("Milton Keynes");

  // Filter state
  const [maxFee, setMaxFee] = useState<string>("");
  const [ageRange, setAgeRange] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [transportOnly, setTransportOnly] = useState(false);

  // Fetch available councils
  useEffect(() => {
    get<string[]>("/councils")
      .then(setCouncils)
      .catch(() => {});
  }, []);

  // Fetch private schools from the API
  useEffect(() => {
    if (!selectedCouncil) return;
    setLoading(true);
    setError(null);

    get<School[]>("/private-schools", { council: selectedCouncil })
      .then((data) => setSchools(data))
      .catch((err) => setError(err.detail ?? "Failed to load private schools"))
      .finally(() => setLoading(false));
  }, [selectedCouncil]);

  const hasActiveFilters = ageRange !== "" || gender !== "" || transportOnly || maxFee !== "";

  const clearFilters = useCallback(() => {
    setAgeRange("");
    setGender("");
    setTransportOnly(false);
    setMaxFee("");
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

      return true;
    });
  }, [schools, ageRange, gender]);

  const handleSchoolSelect = useCallback((id: number) => {
    setSelectedSchoolId((prev) => (prev === id ? null : id));
  }, []);

  const activeFilterCount = [ageRange, gender, transportOnly ? "t" : "", maxFee].filter(Boolean).length;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">Private Schools</h1>
        <p className="mt-1 text-sm text-stone-600 sm:text-base">
          Browse independent and private schools in {selectedCouncil || "your area"}. Filter by
          fees, age range, transport availability, and more.
        </p>
      </div>

      {/* Council selector */}
      <div className="mb-6 rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
        <label htmlFor="council-select-private" className="block text-sm font-medium text-stone-700 mb-2">
          Select Council
        </label>
        <select
          id="council-select-private"
          value={selectedCouncil}
          onChange={(e) => setSelectedCouncil(e.target.value)}
          className="w-full max-w-md rounded-lg border border-stone-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        >
          <option value="">Select a council</option>
          {councils.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4" role="alert">
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-red-800">Unable to load schools</p>
            <p className="mt-0.5 text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Mobile filter toggle */}
      <div className="mb-4 lg:hidden">
        <button
          type="button"
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-stone-300 bg-white px-4 py-3 text-sm font-medium text-stone-700 shadow-sm transition hover:bg-stone-50 active:bg-stone-100"
          aria-expanded={filtersOpen}
          aria-controls="filter-panel"
        >
          <svg className="h-5 w-5 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          Filters
          {activeFilterCount > 0 && (
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-12">
        {/* Filter sidebar */}
        <aside
          id="filter-panel"
          className={`space-y-4 lg:col-span-3 ${filtersOpen ? "block" : "hidden lg:block"}`}
          aria-label="Private school filters"
        >
          <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-stone-900">Filters</h2>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-sm font-medium text-brand-600 hover:text-brand-800 transition-colors"
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
                    className="block w-full rounded-lg border border-stone-300 py-2.5 pl-7 pr-3 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  />
                </div>
                {maxFee && (
                  <p className="mt-1.5 text-xs text-stone-500">
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
                  className="mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
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
                  className="mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                >
                  <option value="">Any</option>
                  <option value="co-ed">Co-educational</option>
                  <option value="boys">Boys only</option>
                  <option value="girls">Girls only</option>
                </select>
              </div>

              {/* Transport checkbox with proper touch target */}
              <label
                htmlFor="transport"
                className="flex cursor-pointer items-center gap-3 rounded-lg p-2 -mx-2 transition hover:bg-stone-50"
              >
                <input
                  id="transport"
                  type="checkbox"
                  checked={transportOnly}
                  onChange={(e) => setTransportOnly(e.target.checked)}
                  className="h-5 w-5 rounded border-stone-300 text-brand-600 focus:ring-2 focus:ring-brand-500"
                />
                <span className="text-sm text-stone-700">
                  Provides transport
                </span>
              </label>

              {/* Result count */}
              <div
                className="rounded-md bg-stone-50 px-3 py-2 text-center text-sm text-stone-600"
                aria-live="polite"
              >
                <span className="font-semibold text-stone-900">{filteredSchools.length}</span>
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
            </div>
          )}

          {/* Empty state */}
          {!loading && filteredSchools.length === 0 && (
            <div className="flex flex-col items-center rounded-xl border border-stone-200 bg-white py-12 px-6 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-stone-100">
                <svg className="h-7 w-7 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="mt-4 text-base font-semibold text-stone-900">
                No schools match your filters
              </h3>
              <p className="mt-1.5 max-w-sm text-sm text-stone-500">
                Try widening your search criteria or removing some filters to see more results.
              </p>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="mt-4 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}

          {/* School cards */}
          {!loading && filteredSchools.map((s) => (
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
              className={`cursor-pointer rounded-xl transition-all focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 ${
                selectedSchoolId === s.id
                  ? "ring-2 ring-brand-500 ring-offset-1"
                  : ""
              }`}
            >
              <SchoolCard
                id={s.id}
                name={s.name}
                type="Independent"
                ofstedRating={s.ofsted_rating ?? "Not rated"}
                distance={
                  s.postcode
                    ? s.postcode
                    : `Ages ${s.age_range_from}-${s.age_range_to}`
                }
                isPrivate={true}
                ethos={s.ethos}
              />
            </div>
          ))}
        </section>

        {/* Map */}
        <section className="h-[350px] sm:h-[500px] lg:col-span-5 lg:h-auto lg:min-h-[600px]" aria-label="Private schools map">
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
