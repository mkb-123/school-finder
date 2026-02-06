import { useCallback, useEffect, useMemo, useState } from "react";
import SchoolCard from "../components/SchoolCard";
import Map, { type School } from "../components/Map";
import { get } from "../api/client";

export default function PrivateSchools() {
  const [schools, setSchools] = useState<School[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSchoolId, setSelectedSchoolId] = useState<number | null>(null);

  // Filter state
  const [maxFee, setMaxFee] = useState<string>("");
  const [ageRange, setAgeRange] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [transportOnly, setTransportOnly] = useState(false);

  // Fetch private schools from the API
  useEffect(() => {
    setLoading(true);
    setError(null);

    get<School[]>("/private-schools", { council: "Milton Keynes" })
      .then((data) => setSchools(data))
      .catch((err) => setError(err.detail ?? "Failed to load private schools"))
      .finally(() => setLoading(false));
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

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">Private Schools</h1>
        <p className="mt-1 text-sm text-gray-600 sm:text-base">
          Browse independent and private schools in Milton Keynes. Filter by
          fees, age range, transport availability, and more.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-12">
        {/* Filter sidebar */}
        <aside className="space-y-4 lg:col-span-3" aria-label="Private school filters">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-gray-900">Filters</h2>

            <div className="mt-4 space-y-4">
              <div>
                <label
                  htmlFor="maxFee"
                  className="block text-sm font-medium text-gray-700"
                >
                  Max Termly Fee
                </label>
                <input
                  id="maxFee"
                  type="number"
                  placeholder="e.g. 5000"
                  value={maxFee}
                  onChange={(e) => setMaxFee(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                {maxFee && (
                  <p className="mt-1 text-xs text-gray-500">
                    Fee filtering applies on the detail page where fee data is
                    available.
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="ageRange"
                  className="block text-sm font-medium text-gray-700"
                >
                  Age Range
                </label>
                <select
                  id="ageRange"
                  value={ageRange}
                  onChange={(e) => setAgeRange(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Any</option>
                  <option value="3-7">3-7 (Pre-prep)</option>
                  <option value="7-11">7-11 (Prep)</option>
                  <option value="11-16">11-16 (Senior)</option>
                  <option value="16-18">16-18 (Sixth Form)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="gender"
                  className="block text-sm font-medium text-gray-700"
                >
                  Gender Policy
                </label>
                <select
                  id="gender"
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Any</option>
                  <option value="co-ed">Co-educational</option>
                  <option value="boys">Boys only</option>
                  <option value="girls">Girls only</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <input
                  id="transport"
                  type="checkbox"
                  checked={transportOnly}
                  onChange={(e) => setTransportOnly(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                <label htmlFor="transport" className="text-sm text-gray-700">
                  Provides transport
                </label>
              </div>

              <div className="pt-2 text-xs text-gray-500">
                Showing {filteredSchools.length} of {schools.length} private
                schools
              </div>
            </div>
          </div>
        </aside>

        {/* School cards */}
        <section className="space-y-3 lg:col-span-4">
          {loading && (
            <p className="text-sm text-gray-500">Loading private schools...</p>
          )}
          {!loading && filteredSchools.length === 0 && (
            <p className="text-sm text-gray-500">
              No private schools match your filters. Try widening your criteria.
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
                type="Independent"
                ofstedRating={s.ofsted_rating ?? "Not rated"}
                distance={
                  s.postcode
                    ? s.postcode
                    : `Ages ${s.age_range_from}-${s.age_range_to}`
                }
                isPrivate={true}
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
