import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { get } from "../api/client";
import Map, { type School } from "../components/Map";

interface Club {
  id: number;
  school_id: number;
  club_type: string;
  name: string;
  description: string | null;
  days_available: string | null;
  start_time: string | null;
  end_time: string | null;
  cost_per_session: number | null;
}

interface SchoolWithClubs extends School {
  clubs: Club[];
}

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

function formatTime(t: string | null): string {
  if (!t) return "";
  // API may return "HH:MM:SS" or "HH:MM" - display as "HH:MM"
  return t.slice(0, 5);
}

function ClubSection({ title, clubs }: { title: string; clubs: Club[] }) {
  if (clubs.length === 0) return null;
  return (
    <div className="mt-4">
      <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
      <div className="mt-2 space-y-3">
        {clubs.map((club) => (
          <div
            key={club.id}
            className="rounded-lg border border-gray-100 bg-gray-50 p-4"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-gray-900">{club.name}</p>
                {club.description && (
                  <p className="mt-0.5 text-sm text-gray-600">{club.description}</p>
                )}
              </div>
              {club.cost_per_session != null && (
                <span className="whitespace-nowrap rounded bg-blue-50 px-2 py-1 text-sm font-medium text-blue-700">
                  &pound;{club.cost_per_session.toFixed(2)}/session
                </span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-sm text-gray-500">
              {club.days_available && (
                <span className="flex items-center gap-1">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  {club.days_available.replace(/,/g, ", ")}
                </span>
              )}
              {(club.start_time || club.end_time) && (
                <span className="flex items-center gap-1">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {formatTime(club.start_time)} &ndash; {formatTime(club.end_time)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ClubsTab({ clubs }: { clubs: Club[] }) {
  if (clubs.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-gray-900">
          Breakfast &amp; After-School Clubs
        </h2>
        <p className="mt-2 text-gray-600">No club data available yet.</p>
      </div>
    );
  }

  const breakfastClubs = clubs.filter((c) => c.club_type === "breakfast");
  const afterSchoolClubs = clubs.filter((c) => c.club_type === "after_school");

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="text-xl font-semibold text-gray-900">
        Breakfast &amp; After-School Clubs
      </h2>
      <ClubSection title="Breakfast Clubs" clubs={breakfastClubs} />
      <ClubSection title="After-School Clubs" clubs={afterSchoolClubs} />
    </div>
  );
}

export default function SchoolDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [school, setSchool] = useState<SchoolWithClubs | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    get<SchoolWithClubs>(`/schools/${id}`)
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
          <ClubsTab clubs={school.clubs ?? []} />
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
