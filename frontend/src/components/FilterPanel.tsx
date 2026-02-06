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

export default function FilterPanel({
  filters,
  onChange,
  schoolCount,
}: FilterPanelProps) {
  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
        {schoolCount !== undefined && (
          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
            {schoolCount} schools
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-gray-500">
        Set constraints to narrow your results.
      </p>

      <div className="mt-4 space-y-4">
        {/* Child's age */}
        <div>
          <label
            htmlFor="filter-age"
            className="block text-sm font-medium text-gray-700"
          >
            Child&apos;s Age
          </label>
          <select
            id="filter-age"
            value={filters.age}
            onChange={(e) => set("age", e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            {Array.from({ length: 14 }, (_, i) => i + 4).map((a) => (
              <option key={a} value={String(a)}>
                {a} (Year {a <= 5 ? "R" : a - 5})
              </option>
            ))}
          </select>
        </div>

        {/* Gender */}
        <div>
          <label
            htmlFor="filter-gender"
            className="block text-sm font-medium text-gray-700"
          >
            Child&apos;s Gender
          </label>
          <select
            id="filter-gender"
            value={filters.gender}
            onChange={(e) => set("gender", e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>

        {/* School type */}
        <div>
          <label
            htmlFor="filter-type"
            className="block text-sm font-medium text-gray-700"
          >
            School Type
          </label>
          <select
            id="filter-type"
            value={filters.schoolType}
            onChange={(e) => set("schoolType", e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="state">State</option>
            <option value="private">Private</option>
          </select>
        </div>

        {/* Ofsted rating */}
        <div>
          <label
            htmlFor="filter-rating"
            className="block text-sm font-medium text-gray-700"
          >
            Minimum Ofsted Rating
          </label>
          <select
            id="filter-rating"
            value={filters.minRating}
            onChange={(e) => set("minRating", e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="Outstanding">Outstanding only</option>
            <option value="Good">Good or better</option>
            <option value="Requires improvement">Requires Improvement+</option>
          </select>
        </div>

        {/* Distance */}
        <div>
          <label
            htmlFor="filter-distance"
            className="block text-sm font-medium text-gray-700"
          >
            Max Distance (km)
          </label>
          <input
            id="filter-distance"
            type="number"
            placeholder="e.g. 3"
            min="0"
            step="0.5"
            value={filters.maxDistance}
            onChange={(e) => set("maxDistance", e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Club filters */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">Clubs</p>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={filters.hasBreakfastClub}
              onChange={(e) => set("hasBreakfastClub", e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600"
            />
            Has breakfast club
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={filters.hasAfterSchoolClub}
              onChange={(e) => set("hasAfterSchoolClub", e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600"
            />
            Has after-school club
          </label>
        </div>

        {/* Map legend */}
        <div className="border-t border-gray-200 pt-4">
          <p className="text-sm font-medium text-gray-700">Ofsted Colours</p>
          <div className="mt-2 space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full bg-green-600" />
              Outstanding
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full bg-blue-600" />
              Good
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full bg-amber-500" />
              Requires Improvement
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full bg-red-600" />
              Inadequate
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full bg-gray-500" />
              Not rated
            </div>
          </div>
        </div>

        {/* SEND toggle */}
        <div className="border-t border-gray-200 pt-4">
          <SendToggle />
        </div>
      </div>
    </div>
  );
}
