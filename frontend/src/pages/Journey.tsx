import { useCallback, useEffect, useMemo, useState } from "react";
import Map, { type School } from "../components/Map";
import JourneyCard, { type SchoolJourney } from "../components/JourneyCard";
import { get } from "../api/client";

/** Transport mode options displayed to the user. */
const TRANSPORT_MODES = [
  { label: "Walking", value: "walking" },
  { label: "Cycling", value: "cycling" },
  { label: "Driving", value: "driving" },
  { label: "Public Transport", value: "transit" },
] as const;

/** API response shape for the compare endpoint. */
interface CompareJourneysResponse {
  from_postcode: string;
  mode: string;
  journeys: SchoolJourney[];
}

export default function Journey() {
  const [postcode, setPostcode] = useState("");
  const [mode, setMode] = useState("walking");
  const [schools, setSchools] = useState<School[]>([]);
  const [selectedSchoolIds, setSelectedSchoolIds] = useState<number[]>([]);
  const [journeys, setJourneys] = useState<SchoolJourney[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingSchools, setLoadingSchools] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);

  // Load all Milton Keynes schools for the selector
  useEffect(() => {
    setLoadingSchools(true);
    get<School[]>("/schools", { council: "Milton Keynes" })
      .then((data) => setSchools(data))
      .catch(() => setSchools([]))
      .finally(() => setLoadingSchools(false));
  }, []);

  // Toggle a school in the selection (max 5)
  const toggleSchool = useCallback((schoolId: number) => {
    setSelectedSchoolIds((prev) => {
      if (prev.includes(schoolId)) {
        return prev.filter((id) => id !== schoolId);
      }
      if (prev.length >= 5) return prev; // Max 5 schools
      return [...prev, schoolId];
    });
  }, []);

  // Calculate journeys
  const handleCalculate = useCallback(async () => {
    if (!postcode.trim() || selectedSchoolIds.length === 0) return;

    setLoading(true);
    setError(null);
    setJourneys([]);

    try {
      const data = await get<CompareJourneysResponse>("/journey/compare", {
        from_postcode: postcode.trim(),
        school_ids: selectedSchoolIds.join(","),
        mode,
      });
      setJourneys(data.journeys);

      // Also geocode for the map
      const geo = await get<{ lat: number; lng: number }>("/geocode", {
        postcode: postcode.trim(),
      });
      setUserLocation([geo.lat, geo.lng]);
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      setError(apiErr.detail ?? "Failed to calculate journeys");
    } finally {
      setLoading(false);
    }
  }, [postcode, selectedSchoolIds, mode]);

  // The selected schools for the map
  const mapSchools = useMemo(() => {
    if (journeys.length > 0) {
      return schools.filter((s) =>
        journeys.some((j) => j.school_id === s.id),
      );
    }
    return schools.filter((s) => selectedSchoolIds.includes(s.id));
  }, [schools, selectedSchoolIds, journeys]);

  // Find the quickest school
  const quickestId = useMemo(() => {
    if (journeys.length === 0) return null;
    return journeys[0].school_id; // Already sorted by drop-off time from API
  }, [journeys]);

  const mapCenter = userLocation ?? ([52.0406, -0.7594] as [number, number]);

  // School search filter
  const [schoolSearch, setSchoolSearch] = useState("");
  const filteredSchools = useMemo(() => {
    if (!schoolSearch.trim()) return schools;
    const q = schoolSearch.toLowerCase();
    return schools.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.postcode && s.postcode.toLowerCase().includes(q)),
    );
  }, [schools, schoolSearch]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">
        School Run Planner
      </h1>
      <p className="mt-1 text-gray-600">
        Plan the school run with realistic travel time estimates. Times are
        calculated for drop-off (8:00-8:45am) and pick-up (5:00-5:30pm) to
        account for peak traffic conditions.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Controls */}
        <aside className="space-y-4 lg:col-span-4">
          {/* Route Settings */}
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Route Settings
            </h2>

            <div className="mt-4 space-y-4">
              {/* Postcode */}
              <div>
                <label
                  htmlFor="journeyPostcode"
                  className="block text-sm font-medium text-gray-700"
                >
                  Your Postcode
                </label>
                <input
                  id="journeyPostcode"
                  type="text"
                  placeholder="e.g. MK9 1AB"
                  value={postcode}
                  onChange={(e) => setPostcode(e.target.value.toUpperCase())}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              {/* Transport Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Transport Mode
                </label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {TRANSPORT_MODES.map((m) => (
                    <button
                      key={m.value}
                      onClick={() => setMode(m.value)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                        mode === m.value
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* School Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Select Schools (up to 5)
                </label>
                <input
                  type="text"
                  placeholder="Search schools..."
                  value={schoolSearch}
                  onChange={(e) => setSchoolSearch(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <div className="mt-2 max-h-48 overflow-y-auto rounded-md border border-gray-200">
                  {loadingSchools && (
                    <p className="p-2 text-xs text-gray-400">Loading schools...</p>
                  )}
                  {filteredSchools.map((school) => {
                    const isSelected = selectedSchoolIds.includes(school.id);
                    const isDisabled = !isSelected && selectedSchoolIds.length >= 5;
                    return (
                      <button
                        key={school.id}
                        onClick={() => toggleSchool(school.id)}
                        disabled={isDisabled}
                        className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition ${
                          isSelected
                            ? "bg-blue-50 font-medium text-blue-800"
                            : isDisabled
                              ? "cursor-not-allowed bg-gray-50 text-gray-300"
                              : "text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        <span
                          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                            isSelected
                              ? "border-blue-600 bg-blue-600 text-white"
                              : "border-gray-300"
                          }`}
                        >
                          {isSelected && (
                            <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                              <path
                                fillRule="evenodd"
                                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                clipRule="evenodd"
                              />
                            </svg>
                          )}
                        </span>
                        <span className="truncate">{school.name}</span>
                      </button>
                    );
                  })}
                </div>
                {selectedSchoolIds.length > 0 && (
                  <p className="mt-1 text-xs text-gray-500">
                    {selectedSchoolIds.length} school{selectedSchoolIds.length !== 1 ? "s" : ""} selected
                  </p>
                )}
              </div>

              {/* Calculate button */}
              <button
                onClick={handleCalculate}
                disabled={loading || !postcode.trim() || selectedSchoolIds.length === 0}
                className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {loading ? "Calculating..." : "Calculate Journey Times"}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Journey Results */}
          {journeys.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-gray-900">
                Travel Times
              </h2>
              <p className="text-xs text-gray-500">
                Sorted by drop-off time (quickest first). Times estimated for
                peak hours. Pick-up times are for 5:00-5:30pm (after work).
              </p>
              {journeys.map((journey, idx) => (
                <JourneyCard
                  key={journey.school_id}
                  journey={journey}
                  isQuickest={journey.school_id === quickestId}
                  rank={idx + 1}
                />
              ))}
              <p className="text-xs text-gray-400">
                Note: estimates use straight-line distance with a route factor.
                Actual times may vary based on road conditions, school
                parking, and drop-off restrictions.
              </p>
            </div>
          )}

          {/* Empty state */}
          {journeys.length === 0 && !loading && !error && (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Travel Times
              </h2>
              <p className="mt-2 text-sm text-gray-500">
                Enter your postcode, select up to 5 schools, and click
                &quot;Calculate Journey Times&quot; to see estimates for
                drop-off and pick-up.
              </p>
            </div>
          )}
        </aside>

        {/* Map */}
        <section className="h-[500px] lg:col-span-8 lg:h-auto lg:min-h-[600px]">
          <Map
            center={mapCenter}
            schools={mapSchools}
          />
        </section>
      </div>
    </main>
  );
}
