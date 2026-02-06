import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { get } from "../api/client";
import Map, { type School } from "../components/Map";

const TABS = [
  "Overview",
  "Clubs",
  "Performance",
  "Term Dates",
  "Admissions",
] as const;
type Tab = (typeof TABS)[number];

const RATING_COLORS: Record<string, string> = {
  Outstanding: "bg-green-100 text-green-800",
  Good: "bg-blue-100 text-blue-800",
  "Requires improvement": "bg-amber-100 text-amber-800",
  Inadequate: "bg-red-100 text-red-800",
};

export default function SchoolDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [school, setSchool] = useState<School | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    get<School>(`/schools/${id}`)
      .then(setSchool)
      .catch(() => setSchool(null))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <p className="text-gray-500">Loading school details...</p>
      </main>
    );
  }

  if (!school) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-3xl font-bold text-gray-900">School Not Found</h1>
        <p className="mt-2 text-gray-600">
          No school found with ID {id}.
        </p>
      </main>
    );
  }

  const badge = RATING_COLORS[school.ofsted_rating ?? ""] ?? "bg-gray-100 text-gray-800";

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{school.name}</h1>
          <p className="mt-1 text-gray-600">{school.address}</p>
          <p className="text-sm text-gray-500">{school.postcode}</p>
        </div>
        {school.ofsted_rating && (
          <span className={`rounded-full px-3 py-1 text-sm font-medium ${badge}`}>
            {school.ofsted_rating}
          </span>
        )}
      </div>

      {/* Quick facts */}
      <div className="mt-4 flex flex-wrap gap-3 text-sm text-gray-600">
        <span className="rounded bg-gray-100 px-2 py-1">
          Ages {school.age_range_from}&ndash;{school.age_range_to}
        </span>
        <span className="rounded bg-gray-100 px-2 py-1">
          {school.gender_policy}
        </span>
        <span className="rounded bg-gray-100 px-2 py-1">
          {school.is_private ? "Private" : "State"}
        </span>
        {school.faith && (
          <span className="rounded bg-gray-100 px-2 py-1">{school.faith}</span>
        )}
        <span className="rounded bg-gray-100 px-2 py-1">
          URN: {school.urn}
        </span>
      </div>

      {/* Tab navigation */}
      <div className="mt-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-6" aria-label="Tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium ${
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="mt-6">
        {activeTab === "Overview" && (
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h2 className="text-xl font-semibold text-gray-900">Details</h2>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Type</dt>
                  <dd className="font-medium text-gray-900">{school.type}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Council</dt>
                  <dd className="font-medium text-gray-900">{school.council}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Catchment Radius</dt>
                  <dd className="font-medium text-gray-900">
                    {school.catchment_radius_km} km
                  </dd>
                </div>
                {school.ofsted_date && (
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Last Ofsted</dt>
                    <dd className="font-medium text-gray-900">
                      {school.ofsted_date}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
            {/* Catchment map */}
            <div className="h-[350px] rounded-lg border border-gray-200 bg-white">
              {school.lat != null && school.lng != null ? (
                <Map
                  center={[school.lat, school.lng]}
                  zoom={14}
                  schools={[school]}
                  selectedSchoolId={school.id}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-gray-400">
                  No location data
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "Clubs" && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-gray-900">
              Breakfast &amp; After-School Clubs
            </h2>
            <p className="mt-2 text-gray-600">
              Club data will be populated by the clubs data-collection agent.
            </p>
          </div>
        )}

        {activeTab === "Performance" && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-gray-900">
              Performance &amp; Ratings
            </h2>
            <p className="mt-2 text-gray-600">
              Academic performance data will be populated by the reviews agent.
            </p>
          </div>
        )}

        {activeTab === "Term Dates" && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-gray-900">Term Dates</h2>
            <p className="mt-2 text-gray-600">
              Term dates will be populated by the term times agent.
            </p>
          </div>
        )}

        {activeTab === "Admissions" && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-gray-900">
              Admissions &amp; Waiting List
            </h2>
            <p className="mt-2 text-gray-600">
              Historical admissions data will be populated once available.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
