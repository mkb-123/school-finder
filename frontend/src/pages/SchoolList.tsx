import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import FilterPanel, {
  DEFAULT_FILTERS,
  type Filters,
} from "../components/FilterPanel";
import SchoolCard from "../components/SchoolCard";
import Map, { type School } from "../components/Map";
import { get } from "../api/client";

/** Ofsted rating ordinal for filtering. */
const RATING_ORDER: Record<string, number> = {
  Outstanding: 4,
  Good: 3,
  "Requires improvement": 2,
  Inadequate: 1,
};

function meetsMinRating(
  rating: string | null,
  minRating: string,
): boolean {
  if (!minRating) return true;
  if (!rating) return false;
  return (RATING_ORDER[rating] ?? 0) >= (RATING_ORDER[minRating] ?? 0);
}

export default function SchoolList() {
  const [searchParams] = useSearchParams();
  const council = searchParams.get("council") ?? "";
  const postcode = searchParams.get("postcode") ?? "";

  const [schools, setSchools] = useState<School[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selectedSchoolId, setSelectedSchoolId] = useState<number | null>(null);
  const [userLocation, setUserLocation] = useState<[number, number] | null>(
    null,
  );

  // Fetch schools when council/postcode change
  useEffect(() => {
    if (!council) return;
    setLoading(true);
    setError(null);

    const params: Record<string, string> = { council };
    if (postcode) params.postcode = postcode;

    get<School[]>("/schools", params)
      .then((data) => setSchools(data))
      .catch((err) => setError(err.detail ?? "Failed to load schools"))
      .finally(() => setLoading(false));
  }, [council, postcode]);

  // Geocode postcode for map centering
  useEffect(() => {
    if (!postcode) return;
    get<{ lat: number; lng: number }>("/geocode", { postcode })
      .then((data) => setUserLocation([data.lat, data.lng]))
      .catch(() => {});
  }, [postcode]);

  // Apply client-side filters
  const filteredSchools = useMemo(() => {
    return schools.filter((s) => {
      if (filters.age) {
        const age = parseInt(filters.age, 10);
        if (s.age_range_from > age || s.age_range_to < age) return false;
      }
      if (filters.gender === "male" && s.gender_policy === "Girls")
        return false;
      if (filters.gender === "female" && s.gender_policy === "Boys")
        return false;
      if (filters.schoolType === "state" && s.is_private) return false;
      if (filters.schoolType === "private" && !s.is_private) return false;
      if (!meetsMinRating(s.ofsted_rating, filters.minRating)) return false;
      if (filters.maxDistance && s.distance_km != null) {
        if (s.distance_km > parseFloat(filters.maxDistance)) return false;
      }
      return true;
    });
  }, [schools, filters]);

  const handleSchoolSelect = useCallback((id: number) => {
    setSelectedSchoolId((prev) => (prev === id ? null : id));
  }, []);

  const mapCenter = userLocation ?? ([52.0406, -0.7594] as [number, number]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">School Results</h1>
        <p className="mt-1 text-gray-600">
          {council && postcode
            ? `Showing schools near ${postcode} in ${council}`
            : "Search for schools by council and postcode from the home page."}
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Filter sidebar */}
        <aside className="lg:col-span-3">
          <FilterPanel
            filters={filters}
            onChange={setFilters}
            schoolCount={filteredSchools.length}
          />
        </aside>

        {/* School cards */}
        <section className="space-y-3 lg:col-span-4">
          {loading && (
            <p className="text-sm text-gray-500">Loading schools...</p>
          )}
          {!loading && filteredSchools.length === 0 && council && (
            <p className="text-sm text-gray-500">
              No schools match your filters. Try widening your criteria.
            </p>
          )}
          {filteredSchools.map((s) => (
            <div
              key={s.id}
              onClick={() => handleSchoolSelect(s.id)}
              className={`cursor-pointer rounded-lg transition ${
                selectedSchoolId === s.id
                  ? "ring-2 ring-blue-500 ring-offset-1"
                  : ""
              }`}
            >
              <SchoolCard
                id={s.id}
                name={s.name}
                type={s.is_private ? "Private" : "State"}
                ofstedRating={s.ofsted_rating ?? "Not rated"}
                distance={
                  s.distance_km != null
                    ? `${s.distance_km.toFixed(1)} km`
                    : s.postcode
                }
                isPrivate={s.is_private}
              />
            </div>
          ))}
        </section>

        {/* Map */}
        <section className="h-[500px] lg:col-span-5 lg:h-auto lg:min-h-[600px]">
          <Map
            center={mapCenter}
            schools={filteredSchools}
            selectedSchoolId={selectedSchoolId}
            onSchoolSelect={handleSchoolSelect}
          />
        </section>
      </div>
    </main>
  );
}
