import { useState, useMemo } from "react";
import { SlidersHorizontal, X, ChevronDown, RotateCcw } from "lucide-react";
import SendToggle from "./SendToggle";

export interface Filters {
  age: string;
  gender: string;
  schoolType: string;
  minRating: string;
  maxDistance: string;
  hasBreakfastClub: boolean;
  hasAfterSchoolClub: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  age: "",
  gender: "",
  schoolType: "",
  minRating: "",
  maxDistance: "",
  hasBreakfastClub: false,
  hasAfterSchoolClub: false,
};

interface FilterPanelProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
  schoolCount?: number;
}

/** Human-readable labels for active filter pills. */
function getActiveFilterLabels(filters: Filters): { key: keyof Filters; label: string }[] {
  const labels: { key: keyof Filters; label: string }[] = [];

  if (filters.age) {
    const a = parseInt(filters.age, 10);
    labels.push({ key: "age", label: `Age ${a} (Year ${a <= 5 ? "R" : a - 5})` });
  }
  if (filters.gender) {
    labels.push({ key: "gender", label: filters.gender === "male" ? "Boy" : "Girl" });
  }
  if (filters.schoolType) {
    labels.push({
      key: "schoolType",
      label: filters.schoolType === "state" ? "State schools" : "Private schools",
    });
  }
  if (filters.minRating) {
    labels.push({ key: "minRating", label: `${filters.minRating}+` });
  }
  if (filters.maxDistance) {
    labels.push({ key: "maxDistance", label: `Within ${filters.maxDistance} km` });
  }
  if (filters.hasBreakfastClub) {
    labels.push({ key: "hasBreakfastClub", label: "Breakfast club" });
  }
  if (filters.hasAfterSchoolClub) {
    labels.push({ key: "hasAfterSchoolClub", label: "After-school club" });
  }
  return labels;
}

/** Clear a single filter back to its default. */
function clearFilter(filters: Filters, key: keyof Filters): Filters {
  return { ...filters, [key]: DEFAULT_FILTERS[key] };
}

export default function FilterPanel({
  filters,
  onChange,
  schoolCount,
}: FilterPanelProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    onChange({ ...filters, [key]: value });
  }

  const activeLabels = useMemo(() => getActiveFilterLabels(filters), [filters]);
  const activeCount = activeLabels.length;
  const hasActiveFilters = activeCount > 0;

  function clearAll() {
    onChange({ ...DEFAULT_FILTERS });
  }

  const selectClasses =
    "mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

  const filterContent = (
    <div className="mt-4 space-y-5">
      {/* Active filter pills */}
      {hasActiveFilters && (
        <div className="flex flex-wrap gap-1.5">
          {activeLabels.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => onChange(clearFilter(filters, key))}
              className="group inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 ring-1 ring-brand-600/10 transition-colors hover:bg-brand-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
              aria-label={`Remove filter: ${label}`}
            >
              {label}
              <X className="h-3 w-3 text-brand-400 group-hover:text-brand-600" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}

      {/* Primary filters - always visible */}
      <fieldset>
        <legend className="sr-only">Primary filters</legend>

        {/* Child's age */}
        <div>
          <label
            htmlFor="filter-age"
            className="block text-sm font-medium text-stone-700"
          >
            Child&apos;s age
          </label>
          <select
            id="filter-age"
            value={filters.age}
            onChange={(e) => set("age", e.target.value)}
            className={selectClasses}
          >
            <option value="">Any age</option>
            {Array.from({ length: 14 }, (_, i) => i + 4).map((a) => (
              <option key={a} value={String(a)}>
                {a} years old (Year {a <= 5 ? "R" : a - 5})
              </option>
            ))}
          </select>
        </div>

        {/* Gender */}
        <div className="mt-4">
          <label
            htmlFor="filter-gender"
            className="block text-sm font-medium text-stone-700"
          >
            Child&apos;s gender
          </label>
          <select
            id="filter-gender"
            value={filters.gender}
            onChange={(e) => set("gender", e.target.value)}
            className={selectClasses}
          >
            <option value="">Any</option>
            <option value="male">Boy</option>
            <option value="female">Girl</option>
          </select>
        </div>

        {/* School type */}
        <div className="mt-4">
          <label
            htmlFor="filter-type"
            className="block text-sm font-medium text-stone-700"
          >
            School type
          </label>
          <select
            id="filter-type"
            value={filters.schoolType}
            onChange={(e) => set("schoolType", e.target.value)}
            className={selectClasses}
          >
            <option value="">All types</option>
            <option value="state">State schools</option>
            <option value="private">Private / independent</option>
          </select>
        </div>

        {/* Ofsted rating */}
        <div className="mt-4">
          <label
            htmlFor="filter-rating"
            className="block text-sm font-medium text-stone-700"
          >
            Minimum Ofsted rating
          </label>
          <select
            id="filter-rating"
            value={filters.minRating}
            onChange={(e) => set("minRating", e.target.value)}
            className={selectClasses}
          >
            <option value="">Any rating</option>
            <option value="Outstanding">Outstanding only</option>
            <option value="Good">Good or better</option>
            <option value="Requires improvement">Requires Improvement or better</option>
          </select>
        </div>
      </fieldset>

      {/* Distance */}
      <div className="border-t border-stone-100 pt-4">
        <label
          htmlFor="filter-distance"
          className="block text-sm font-medium text-stone-700"
        >
          Maximum distance
        </label>
        <div className="relative mt-1">
          <input
            id="filter-distance"
            type="number"
            placeholder="e.g. 3"
            min="0"
            step="0.5"
            value={filters.maxDistance}
            onChange={(e) => set("maxDistance", e.target.value)}
            aria-label="Maximum distance in kilometres"
            className="block w-full rounded-lg border border-stone-300 py-2.5 pl-3 pr-10 text-sm shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-stone-400">
            km
          </span>
        </div>
      </div>

      {/* Club filters - larger touch targets */}
      <fieldset className="border-t border-stone-100 pt-4">
        <legend className="text-sm font-medium text-stone-700">Wraparound care</legend>
        <div className="mt-2 space-y-1">
          <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm text-stone-700 transition-colors hover:bg-stone-50">
            <input
              type="checkbox"
              checked={filters.hasBreakfastClub}
              onChange={(e) => set("hasBreakfastClub", e.target.checked)}
              className="h-4 w-4 rounded border-stone-300 text-brand-600 focus:ring-2 focus:ring-brand-500"
            />
            <span>Has breakfast club</span>
          </label>
          <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm text-stone-700 transition-colors hover:bg-stone-50">
            <input
              type="checkbox"
              checked={filters.hasAfterSchoolClub}
              onChange={(e) => set("hasAfterSchoolClub", e.target.checked)}
              className="h-4 w-4 rounded border-stone-300 text-brand-600 focus:ring-2 focus:ring-brand-500"
            />
            <span>Has after-school club</span>
          </label>
        </div>
      </fieldset>

      {/* Map legend - collapsible, less prominent */}
      <details className="border-t border-stone-100 pt-4">
        <summary className="cursor-pointer text-xs font-medium text-stone-500 hover:text-stone-700 transition-colors">
          Map colour key
        </summary>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-stone-600">
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-600" aria-hidden="true" />
            Outstanding
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-600" aria-hidden="true" />
            Good
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" aria-hidden="true" />
            Requires Improvement
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-600" aria-hidden="true" />
            Inadequate
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-stone-400" aria-hidden="true" />
            Not yet rated
          </div>
        </div>
      </details>

      {/* SEND toggle */}
      <div className="border-t border-stone-100 pt-4">
        <SendToggle />
      </div>
    </div>
  );

  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-stone-500" aria-hidden="true" />
          <h2 className="text-base font-semibold text-stone-900">Filters</h2>
          {activeCount > 0 && (
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-white">
              {activeCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {schoolCount !== undefined && (
            <span
              className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700"
              aria-live="polite"
              aria-atomic="true"
            >
              {schoolCount} {schoolCount === 1 ? "school" : "schools"}
            </span>
          )}
          {/* Clear all button - only when filters are active */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearAll}
              className="hidden items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-700 focus:outline-none focus:ring-2 focus:ring-brand-500 lg:inline-flex"
              aria-label="Clear all filters"
            >
              <RotateCcw className="h-3 w-3" aria-hidden="true" />
              Clear
            </button>
          )}
          {/* Mobile toggle button - larger touch target */}
          <button
            type="button"
            onClick={() => setMobileOpen(!mobileOpen)}
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-stone-500 transition-colors hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-brand-500 lg:hidden"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Collapse filters" : "Expand filters"}
          >
            <ChevronDown
              className={`h-5 w-5 transition-transform duration-200 ${mobileOpen ? "rotate-180" : ""}`}
              aria-hidden="true"
            />
          </button>
        </div>
      </div>

      {/* Summary line: show active filter count when collapsed on mobile */}
      {!mobileOpen && activeCount > 0 && (
        <p className="mt-1 text-xs text-brand-600 lg:hidden">
          {activeCount} {activeCount === 1 ? "filter" : "filters"} active
        </p>
      )}
      {!mobileOpen && activeCount === 0 && (
        <p className="mt-1 text-xs text-stone-400 lg:hidden">
          Tap to narrow your search
        </p>
      )}
      <p className="mt-1 hidden text-xs text-stone-400 lg:block">
        Narrow your search by age, type, and more.
      </p>

      {/* Mobile: clear all button inline */}
      {mobileOpen && hasActiveFilters && (
        <div className="mt-2 flex lg:hidden">
          <button
            type="button"
            onClick={clearAll}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
            aria-label="Clear all filters"
          >
            <RotateCcw className="h-3 w-3" aria-hidden="true" />
            Clear all filters
          </button>
        </div>
      )}

      {/* Desktop: always visible. Mobile: collapsible with animation */}
      <div className="hidden lg:block">{filterContent}</div>
      {mobileOpen && (
        <div className="lg:hidden animate-in fade-in slide-in-from-top-2 duration-200">
          {filterContent}
        </div>
      )}
    </div>
  );
}
