import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { get } from "../api/client";
import Map, { type School } from "../components/Map";

/** Private school detail entry as returned by the API. */
interface PrivateDetail {
  id: number;
  school_id: number;
  termly_fee: number | null;
  annual_fee: number | null;
  fee_age_group: string | null;
  school_day_start: string | null;
  school_day_end: string | null;
  provides_transport: boolean | null;
  transport_notes: string | null;
  holiday_schedule_notes: string | null;
}

/** Extended school response with private details. */
interface PrivateSchoolResponse extends School {
  private_details: PrivateDetail[];
}

const RATING_COLORS: Record<string, string> = {
  Outstanding: "bg-green-100 text-green-800",
  Good: "bg-blue-100 text-blue-800",
  "Requires improvement": "bg-amber-100 text-amber-800",
  Inadequate: "bg-red-100 text-red-800",
};

/** Format a time string like "08:15:00" to "8:15 AM". */
function formatTime(timeStr: string | null): string {
  if (!timeStr) return "--";
  const parts = timeStr.split(":");
  if (parts.length < 2) return timeStr;
  const hours = parseInt(parts[0], 10);
  const minutes = parts[1];
  const ampm = hours >= 12 ? "PM" : "AM";
  const displayHour = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours;
  return `${displayHour}:${minutes} ${ampm}`;
}

/** Format currency amount. */
function formatFee(amount: number | null): string {
  if (amount == null) return "--";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function PrivateSchoolDetail() {
  const { id } = useParams<{ id: string }>();
  const [school, setSchool] = useState<PrivateSchoolResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    get<PrivateSchoolResponse>(`/private-schools/${id}`)
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
          No private school found with ID {id}.
        </p>
        <Link
          to="/private-schools"
          className="mt-4 inline-block text-blue-600 hover:underline"
        >
          Back to private schools
        </Link>
      </main>
    );
  }

  const badge =
    RATING_COLORS[school.ofsted_rating ?? ""] ?? "bg-gray-100 text-gray-800";
  const details = school.private_details ?? [];

  // Extract shared fields from the first detail entry (hours, transport, etc.)
  const firstDetail = details.length > 0 ? details[0] : null;
  const providesTransport = firstDetail?.provides_transport ?? null;
  const transportNotes = firstDetail?.transport_notes ?? null;
  const holidayNotes = firstDetail?.holiday_schedule_notes ?? null;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      {/* Back link */}
      <Link
        to="/private-schools"
        className="mb-4 inline-flex items-center text-sm text-blue-600 hover:underline"
      >
        <svg
          className="mr-1 h-4 w-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Back to private schools
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{school.name}</h1>
          <p className="mt-1 text-gray-600">{school.address}</p>
          <p className="text-sm text-gray-500">{school.postcode}</p>
        </div>
        {school.ofsted_rating && (
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${badge}`}
          >
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
        <span className="rounded bg-purple-100 px-2 py-1 text-purple-800">
          Independent
        </span>
        {school.faith && (
          <span className="rounded bg-gray-100 px-2 py-1">{school.faith}</span>
        )}
        <span className="rounded bg-gray-100 px-2 py-1">
          URN: {school.urn}
        </span>
      </div>

      {/* Content grid */}
      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Fees */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">Fees</h2>
          <p className="mt-1 text-sm text-gray-500">
            Termly and annual fee breakdowns by age group.
          </p>
          {details.length > 0 ? (
            <div className="mt-4 space-y-2">
              {details.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between border-b border-gray-100 py-2 text-sm"
                >
                  <span className="text-gray-600">
                    {d.fee_age_group ?? "General"}
                  </span>
                  <div className="text-right">
                    <span className="font-medium text-gray-900">
                      {formatFee(d.termly_fee)}
                    </span>
                    <span className="ml-1 text-gray-400">/term</span>
                    {d.annual_fee != null && (
                      <span className="ml-3 text-xs text-gray-500">
                        ({formatFee(d.annual_fee)}/yr)
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-gray-400">
              No fee data available yet.
            </p>
          )}
        </section>

        {/* School Hours */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">School Hours</h2>
          <p className="mt-1 text-sm text-gray-500">
            School day start and end times.
          </p>
          {firstDetail ? (
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">School day starts</span>
                <span className="font-medium text-gray-900">
                  {formatTime(firstDetail.school_day_start)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">School day ends</span>
                <span className="font-medium text-gray-900">
                  {formatTime(firstDetail.school_day_end)}
                </span>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-gray-400">
              No hours data available yet.
            </p>
          )}
        </section>

        {/* Transport */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">Transport</h2>
          <p className="mt-1 text-sm text-gray-500">
            School transport availability, routes, and eligibility.
          </p>
          {providesTransport != null ? (
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <span
                  className={`inline-block h-3 w-3 rounded-full ${providesTransport ? "bg-green-500" : "bg-red-400"}`}
                />
                <span className="font-medium text-gray-900">
                  {providesTransport
                    ? "Transport provided"
                    : "No school transport"}
                </span>
              </div>
              {transportNotes && (
                <p className="text-sm text-gray-600">{transportNotes}</p>
              )}
            </div>
          ) : (
            <p className="mt-4 text-sm text-gray-400">
              No transport data available yet.
            </p>
          )}
        </section>

        {/* Holiday Schedule */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">
            Holiday Schedule
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Private schools often have different term dates from state schools.
          </p>
          {holidayNotes ? (
            <p className="mt-4 text-sm text-gray-600">{holidayNotes}</p>
          ) : (
            <p className="mt-4 text-sm text-gray-400">
              No holiday schedule data available yet.
            </p>
          )}
        </section>

        {/* General Information */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">
            General Information
          </h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Address</dt>
              <dd className="text-right font-medium text-gray-900">
                {school.address}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Postcode</dt>
              <dd className="font-medium text-gray-900">{school.postcode}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Age Range</dt>
              <dd className="font-medium text-gray-900">
                {school.age_range_from}&ndash;{school.age_range_to}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Gender Policy</dt>
              <dd className="font-medium text-gray-900">
                {school.gender_policy}
              </dd>
            </div>
            {school.faith && (
              <div className="flex justify-between">
                <dt className="text-gray-500">Faith</dt>
                <dd className="font-medium text-gray-900">{school.faith}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-gray-500">Council</dt>
              <dd className="font-medium text-gray-900">{school.council}</dd>
            </div>
            {school.ofsted_date && (
              <div className="flex justify-between">
                <dt className="text-gray-500">Last Inspection</dt>
                <dd className="font-medium text-gray-900">
                  {school.ofsted_date}
                </dd>
              </div>
            )}
          </dl>
        </section>

        {/* Location Map */}
        <section className="rounded-lg border border-gray-200 bg-white">
          <div className="p-4">
            <h2 className="text-xl font-semibold text-gray-900">Location</h2>
          </div>
          <div className="h-[300px]">
            {school.lat != null && school.lng != null ? (
              <Map
                center={[school.lat, school.lng]}
                zoom={14}
                schools={[school]}
                selectedSchoolId={school.id}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-gray-400">
                No location data available
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
