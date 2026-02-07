import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Route as RouteIcon,
  Footprints,
  Bike,
  Car,
  Bus,
  Search,
  Loader2,
  MapPin,
  AlertCircle,
} from "lucide-react";
import Map, { type School } from "../components/Map";
import JourneyCard, { type SchoolJourney } from "../components/JourneyCard";
import BusRouteCard, { type BusRoute, type NearbyBusStop } from "../components/BusRouteCard";
import { get } from "../api/client";

/** Transport mode options displayed to the user. */
const TRANSPORT_MODES = [
  { label: "Walking", value: "walking", Icon: Footprints },
  { label: "Cycling", value: "cycling", Icon: Bike },
  { label: "Driving", value: "driving", Icon: Car },
  { label: "Public Transport", value: "transit", Icon: Bus },
] as const;

/** API response shape for the compare endpoint. */
interface CompareJourneysResponse {
  from_postcode: string;
  mode: string;
  journeys: SchoolJourney[];
}

export default function Journey() {
  const [postcode, setPostcode] = useState("");
  const [mode, setMode] = useState("driving");
  const [schools, setSchools] = useState<School[]>([]);
  const [selectedSchoolIds, setSelectedSchoolIds] = useState<number[]>([]);
  const [journeys, setJourneys] = useState<SchoolJourney[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingSchools, setLoadingSchools] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const [busRoutes, setBusRoutes] = useState<Record<number, BusRoute[]>>({});
  const [nearbyBusStops, setNearbyBusStops] = useState<NearbyBusStop[]>([]);
  const [loadingBusData, setLoadingBusData] = useState(false);

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
    setBusRoutes({});
    setNearbyBusStops([]);

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

      // Fetch bus routes for each school and nearby stops
      setLoadingBusData(true);
      try {
        // Fetch bus routes for each selected school
        const routePromises = selectedSchoolIds.map(async (schoolId) => {
          try {
            const routeData = await get<{ school_id: number; school_name: string; routes: BusRoute[] }>(
              `/schools/${schoolId}/bus-routes`
            );
            return { schoolId, routes: routeData.routes };
          } catch {
            return { schoolId, routes: [] };
          }
        });
        const routeResults = await Promise.all(routePromises);
        const routesMap: Record<number, BusRoute[]> = {};
        for (const { schoolId, routes } of routeResults) {
          routesMap[schoolId] = routes;
        }
        setBusRoutes(routesMap);

        // Fetch nearby bus stops
        try {
          const nearbyData = await get<NearbyBusStop[]>("/bus-routes/nearby", {
            lat: geo.lat,
            lng: geo.lng,
            max_distance_km: 0.5,
          });
          setNearbyBusStops(nearbyData);
        } catch {
          setNearbyBusStops([]);
        }
      } finally {
        setLoadingBusData(false);
      }
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      setError(apiErr.detail ?? "Could not calculate journey times. Please check your postcode and try again.");
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

  // Format bus stops for the map
  const busStopsForMap = useMemo(() => {
    return nearbyBusStops
      .filter((ns) => ns.stop.lat !== null && ns.stop.lng !== null)
      .map((ns) => ({
        id: ns.stop.id,
        name: ns.stop.stop_name,
        lat: ns.stop.lat!,
        lng: ns.stop.lng!,
        pickupTime: ns.stop.morning_pickup_time,
        schoolName: ns.school_name,
      }));
  }, [nearbyBusStops]);

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

  const canCalculate = postcode.trim().length > 0 && selectedSchoolIds.length > 0;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600 sm:h-12 sm:w-12">
          <RouteIcon className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden="true" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">
            School Run Planner
          </h1>
          <p className="mt-1 text-sm leading-relaxed text-stone-600 sm:text-base">
            Compare realistic travel times to your shortlisted schools. Estimates
            account for drop-off (8:00-8:45am) and pick-up (5:00-5:30pm) peak
            traffic.
          </p>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:mt-8 sm:gap-6 lg:grid-cols-12">
        {/* Controls */}
        <aside className="space-y-4 lg:col-span-4" aria-label="Journey settings">
          {/* Route Settings */}
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-stone-900">
              Route settings
            </h2>

            <div className="mt-4 space-y-5">
              {/* Postcode */}
              <div>
                <label
                  htmlFor="journeyPostcode"
                  className="block text-sm font-medium text-stone-700"
                >
                  Your postcode
                </label>
                <div className="relative mt-1.5">
                  <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" aria-hidden="true" />
                  <input
                    id="journeyPostcode"
                    type="text"
                    placeholder="e.g. MK9 1AB"
                    value={postcode}
                    onChange={(e) => setPostcode(e.target.value.toUpperCase())}
                    className="block w-full rounded-lg border border-stone-300 py-3 pl-9 pr-3 text-sm shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1"
                  />
                </div>
              </div>

              {/* Transport Mode */}
              <div>
                <label className="block text-sm font-medium text-stone-700">
                  How will you travel?
                </label>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
                  {TRANSPORT_MODES.map((m) => {
                    const isActive = mode === m.value;
                    return (
                      <button
                        key={m.value}
                        onClick={() => setMode(m.value)}
                        aria-pressed={isActive}
                        aria-label={`Transport mode: ${m.label}`}
                        className={`flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-3 py-2.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
                          isActive
                            ? "bg-brand-600 text-white shadow-sm"
                            : "border border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                        }`}
                      >
                        <m.Icon className="h-4 w-4" aria-hidden="true" />
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* School Selector */}
              <div>
                <label className="block text-sm font-medium text-stone-700">
                  Pick schools to compare (up to 5)
                </label>
                <div className="relative mt-1.5">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" aria-hidden="true" />
                  <input
                    type="text"
                    placeholder="Search by name or postcode..."
                    value={schoolSearch}
                    onChange={(e) => setSchoolSearch(e.target.value)}
                    aria-label="Search schools to add"
                    className="block w-full rounded-lg border border-stone-300 py-2.5 pl-9 pr-3 text-sm shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
                <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-stone-200">
                  {loadingSchools && (
                    <div className="flex items-center justify-center py-6 text-xs text-stone-400">
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                      Loading schools...
                    </div>
                  )}
                  {!loadingSchools && filteredSchools.length === 0 && (
                    <p className="py-4 text-center text-xs text-stone-400">
                      No schools match your search
                    </p>
                  )}
                  {filteredSchools.map((school) => {
                    const isSelected = selectedSchoolIds.includes(school.id);
                    const isDisabled = !isSelected && selectedSchoolIds.length >= 5;
                    return (
                      <button
                        key={school.id}
                        onClick={() => toggleSchool(school.id)}
                        disabled={isDisabled}
                        className={`flex w-full min-h-[44px] items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors ${
                          isSelected
                            ? "bg-brand-50 font-medium text-brand-800"
                            : isDisabled
                              ? "cursor-not-allowed bg-stone-50 text-stone-300"
                              : "text-stone-700 hover:bg-stone-50"
                        }`}
                      >
                        <span
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors ${
                            isSelected
                              ? "border-brand-600 bg-brand-600 text-white"
                              : "border-stone-300"
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
                  <p className="mt-1.5 text-xs text-stone-500">
                    {selectedSchoolIds.length} school{selectedSchoolIds.length !== 1 ? "s" : ""} selected
                    {selectedSchoolIds.length >= 5 && " (maximum reached)"}
                  </p>
                )}
              </div>

              {/* Calculate button */}
              <button
                onClick={handleCalculate}
                disabled={loading || !canCalculate}
                aria-label="Calculate journey times for selected schools"
                className="flex w-full min-h-[48px] items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Calculating...
                  </>
                ) : (
                  <>
                    <RouteIcon className="h-4 w-4" aria-hidden="true" />
                    Calculate journey times
                  </>
                )}
              </button>
              {!canCalculate && !loading && (
                <p className="text-xs text-stone-400">
                  {!postcode.trim()
                    ? "Enter your postcode above to get started."
                    : "Select at least one school to compare."}
                </p>
              )}
            </div>
          </section>

          {/* Error */}
          {error && (
            <div
              className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
              role="alert"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          {/* Journey Results */}
          {journeys.length > 0 && (
            <section className="space-y-3">
              <div>
                <h2 className="text-lg font-semibold text-stone-900">
                  Travel times
                </h2>
                <p className="mt-0.5 text-xs leading-relaxed text-stone-500">
                  Sorted by drop-off time (quickest first). Pick-up times are
                  for 5:00-5:30pm after work.
                </p>
              </div>
              {journeys.map((journey, idx) => (
                <JourneyCard
                  key={journey.school_id}
                  journey={journey}
                  isQuickest={journey.school_id === quickestId}
                  rank={idx + 1}
                />
              ))}
              <p className="rounded-lg bg-stone-50 p-3 text-xs leading-relaxed text-stone-400">
                These are estimates using straight-line distance with a route
                factor. Actual times will vary based on road conditions, school
                parking, and drop-off restrictions.
              </p>
            </section>
          )}

          {/* Bus Routes Section */}
          {journeys.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-lg font-semibold text-stone-900">
                School bus routes
              </h2>
              {loadingBusData && (
                <div className="flex items-center gap-2 py-4 text-sm text-stone-500">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Loading bus route information...
                </div>
              )}
              {!loadingBusData && Object.keys(busRoutes).length === 0 && (
                <p className="rounded-lg border border-dashed border-stone-200 p-4 text-center text-sm text-stone-500">
                  No bus routes available for selected schools.
                </p>
              )}
              {!loadingBusData && Object.entries(busRoutes).map(([schoolIdStr, routes]) => {
                const schoolId = parseInt(schoolIdStr, 10);
                const school = schools.find((s) => s.id === schoolId);
                if (!school || routes.length === 0) return null;
                return (
                  <div key={schoolId} className="space-y-2">
                    <h3 className="text-sm font-semibold text-stone-800">
                      {school.name}
                    </h3>
                    {routes.map((route) => (
                      <BusRouteCard
                        key={route.id}
                        route={route}
                        nearbyStops={nearbyBusStops}
                      />
                    ))}
                  </div>
                );
              })}
            </section>
          )}

          {/* Empty state */}
          {journeys.length === 0 && !loading && !error && (
            <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
              <h2 className="text-base font-semibold text-stone-900">
                Travel times
              </h2>
              <div className="mt-3 rounded-lg border-2 border-dashed border-stone-200 px-4 py-8 text-center">
                <RouteIcon className="mx-auto h-8 w-8 text-stone-300" aria-hidden="true" />
                <p className="mt-2 text-sm font-medium text-stone-600">
                  Ready to plan your school run
                </p>
                <p className="mt-1 text-xs text-stone-400">
                  Enter your postcode, pick up to 5 schools, and tap "Calculate
                  journey times" to compare travel options.
                </p>
              </div>
            </section>
          )}
        </aside>

        {/* Map */}
        <section
          className="h-[400px] sm:h-[500px] lg:col-span-8 lg:h-auto lg:min-h-[600px]"
          aria-label="Journey map"
        >
          <Map
            center={mapCenter}
            schools={mapSchools}
            busStops={busStopsForMap}
          />
        </section>
      </div>
    </main>
  );
}
