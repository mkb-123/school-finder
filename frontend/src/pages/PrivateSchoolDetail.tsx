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
  fee_increase_pct: number | null;
  school_day_start: string | null;
  school_day_end: string | null;
  provides_transport: boolean | null;
  transport_notes: string | null;
  holiday_schedule_notes: string | null;

  // Hidden costs
  lunches_per_term: number | null;
  lunches_compulsory: boolean;
  trips_per_term: number | null;
  trips_compulsory: boolean;
  exam_fees_per_year: number | null;
  exam_fees_compulsory: boolean;
  textbooks_per_year: number | null;
  textbooks_compulsory: boolean;
  music_tuition_per_term: number | null;
  music_tuition_compulsory: boolean;
  sports_per_term: number | null;
  sports_compulsory: boolean;
  uniform_per_year: number | null;
  uniform_compulsory: boolean;
  registration_fee: number | null;
  deposit_fee: number | null;
  insurance_per_year: number | null;
  insurance_compulsory: boolean;
  building_fund_per_year: number | null;
  building_fund_compulsory: boolean;
  hidden_costs_notes: string | null;
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

/** Calculate true annual cost including compulsory hidden costs. */
function calculateTrueAnnualCost(detail: PrivateDetail): {
  headline: number;
  compulsory: number;
  optional: number;
  total: number;
} {
  const annualFee = detail.annual_fee || (detail.termly_fee ? detail.termly_fee * 3 : 0);
  let compulsory = 0;
  let optional = 0;

  // Lunches (3 terms per year)
  if (detail.lunches_per_term) {
    const annual = detail.lunches_per_term * 3;
    if (detail.lunches_compulsory) compulsory += annual;
    else optional += annual;
  }

  // Trips (3 terms per year)
  if (detail.trips_per_term) {
    const annual = detail.trips_per_term * 3;
    if (detail.trips_compulsory) compulsory += annual;
    else optional += annual;
  }

  // Exam fees (per year)
  if (detail.exam_fees_per_year) {
    if (detail.exam_fees_compulsory) compulsory += detail.exam_fees_per_year;
    else optional += detail.exam_fees_per_year;
  }

  // Textbooks (per year)
  if (detail.textbooks_per_year) {
    if (detail.textbooks_compulsory) compulsory += detail.textbooks_per_year;
    else optional += detail.textbooks_per_year;
  }

  // Music tuition (3 terms per year)
  if (detail.music_tuition_per_term) {
    const annual = detail.music_tuition_per_term * 3;
    if (detail.music_tuition_compulsory) compulsory += annual;
    else optional += annual;
  }

  // Sports (3 terms per year)
  if (detail.sports_per_term) {
    const annual = detail.sports_per_term * 3;
    if (detail.sports_compulsory) compulsory += annual;
    else optional += annual;
  }

  // Uniform (per year)
  if (detail.uniform_per_year) {
    if (detail.uniform_compulsory) compulsory += detail.uniform_per_year;
    else optional += detail.uniform_per_year;
  }

  // Insurance (per year)
  if (detail.insurance_per_year) {
    if (detail.insurance_compulsory) compulsory += detail.insurance_per_year;
    else optional += detail.insurance_per_year;
  }

  // Building fund (per year)
  if (detail.building_fund_per_year) {
    if (detail.building_fund_compulsory) compulsory += detail.building_fund_per_year;
    else optional += detail.building_fund_per_year;
  }

  return {
    headline: annualFee,
    compulsory,
    optional,
    total: annualFee + compulsory,
  };
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
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
        <p className="text-gray-500" aria-live="polite">Loading school details...</p>
      </main>
    );
  }

  if (!school) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
        <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">School Not Found</h1>
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

  // Fee range across all tiers
  const termlyFees = details.map((d) => d.termly_fee).filter((f): f is number => f != null);
  const feeMin = termlyFees.length > 0 ? Math.min(...termlyFees) : null;
  const feeMax = termlyFees.length > 0 ? Math.max(...termlyFees) : null;
  const feeIncreasePct = firstDetail?.fee_increase_pct ?? null;

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
      {/* Back link */}
      <Link
        to="/private-schools"
        className="mb-4 inline-flex items-center text-sm text-blue-600 hover:underline"
        aria-label="Back to private schools list"
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
          <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">{school.name}</h1>
          <p className="mt-1 text-sm text-gray-600 sm:text-base">{school.address}</p>
          <p className="text-xs text-gray-500 sm:text-sm">{school.postcode}</p>
          {school.ethos && (
            <p className="mt-2 text-sm italic text-gray-700">"{school.ethos}"</p>
          )}
        </div>
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
          {feeMin != null && feeMax != null && (
            <div className="mt-3 rounded-md bg-blue-50 px-3 py-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-blue-800">Fee range</span>
                <span className="font-semibold text-blue-900">
                  {feeMin === feeMax
                    ? `${formatFee(feeMin)}/term`
                    : `${formatFee(feeMin)} - ${formatFee(feeMax)}/term`}
                </span>
              </div>
              {feeIncreasePct != null && (
                <div className="mt-1 flex items-center justify-between text-xs text-blue-700">
                  <span>Est. annual increase</span>
                  <span className="font-medium">~{feeIncreasePct}% per year</span>
                </div>
              )}
            </div>
          )}
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

        {/* True Cost Breakdown */}
        {details.length > 0 && (
          <section className="rounded-lg border border-orange-200 bg-orange-50 p-6 md:col-span-2">
            <h2 className="text-xl font-semibold text-gray-900">True Annual Cost</h2>
            <p className="mt-1 text-sm text-gray-600">
              Headline fees don't tell the whole story. These are the additional costs that aren't included in the advertised fee.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {details.map((detail) => {
                const costs = calculateTrueAnnualCost(detail);
                return (
                  <div
                    key={detail.id}
                    className="rounded-lg border border-orange-300 bg-white p-5"
                  >
                    <h3 className="font-semibold text-gray-900">
                      {detail.fee_age_group || "General"}
                    </h3>

                    {/* Headline cost */}
                    <div className="mt-4 border-b border-gray-200 pb-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">Headline annual fee</span>
                        <span className="font-medium text-gray-900">
                          {formatFee(costs.headline)}
                        </span>
                      </div>
                    </div>

                    {/* Compulsory extras */}
                    <div className="mt-3 border-b border-gray-200 pb-3">
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="font-medium text-gray-700">Compulsory extras</span>
                        <span className="font-semibold text-orange-700">
                          +{formatFee(costs.compulsory)}
                        </span>
                      </div>

                      <div className="space-y-1 text-xs text-gray-600">
                        {detail.lunches_compulsory && detail.lunches_per_term && (
                          <div>• Lunches: {formatFee(detail.lunches_per_term * 3)}/yr</div>
                        )}
                        {detail.exam_fees_compulsory && detail.exam_fees_per_year && (
                          <div>• Exam fees: {formatFee(detail.exam_fees_per_year)}/yr</div>
                        )}
                        {detail.textbooks_compulsory && detail.textbooks_per_year && (
                          <div>• Textbooks: {formatFee(detail.textbooks_per_year)}/yr</div>
                        )}
                        {detail.uniform_compulsory && detail.uniform_per_year && (
                          <div>• Uniform: {formatFee(detail.uniform_per_year)}/yr</div>
                        )}
                        {detail.insurance_compulsory && detail.insurance_per_year && (
                          <div>• Insurance: {formatFee(detail.insurance_per_year)}/yr</div>
                        )}
                        {detail.building_fund_compulsory && detail.building_fund_per_year && (
                          <div>• Building fund: {formatFee(detail.building_fund_per_year)}/yr</div>
                        )}
                      </div>
                    </div>

                    {/* True annual cost */}
                    <div className="mt-3 rounded-md bg-orange-100 px-3 py-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-orange-900">True annual cost</span>
                        <span className="text-lg font-bold text-orange-900">
                          {formatFee(costs.total)}
                        </span>
                      </div>
                    </div>

                    {/* Optional extras */}
                    {costs.optional > 0 && (
                      <div className="mt-3 border-t border-gray-200 pt-3">
                        <div className="mb-2 flex items-center justify-between text-xs">
                          <span className="font-medium text-gray-600">Optional extras</span>
                          <span className="font-medium text-gray-700">
                            +{formatFee(costs.optional)}
                          </span>
                        </div>
                        <div className="space-y-1 text-xs text-gray-500">
                          {!detail.lunches_compulsory && detail.lunches_per_term && (
                            <div>• Lunches: {formatFee(detail.lunches_per_term * 3)}/yr</div>
                          )}
                          {detail.trips_per_term && (
                            <div>• Trips: {formatFee(detail.trips_per_term * 3)}/yr</div>
                          )}
                          {detail.music_tuition_per_term && (
                            <div>• Music tuition: {formatFee(detail.music_tuition_per_term * 3)}/yr</div>
                          )}
                          {detail.sports_per_term && (
                            <div>• Sports: {formatFee(detail.sports_per_term * 3)}/yr</div>
                          )}
                          {!detail.insurance_compulsory && detail.insurance_per_year && (
                            <div>• Insurance: {formatFee(detail.insurance_per_year)}/yr</div>
                          )}
                          {!detail.building_fund_compulsory && detail.building_fund_per_year && (
                            <div>• Building fund: {formatFee(detail.building_fund_per_year)}/yr</div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* One-time costs */}
                    {(detail.registration_fee || detail.deposit_fee) && (
                      <div className="mt-3 border-t border-gray-200 pt-3">
                        <div className="text-xs font-medium text-gray-600">One-time costs (first year):</div>
                        <div className="mt-1 space-y-1 text-xs text-gray-500">
                          {detail.registration_fee && (
                            <div>• Registration: {formatFee(detail.registration_fee)}</div>
                          )}
                          {detail.deposit_fee && (
                            <div>• Deposit (often refundable): {formatFee(detail.deposit_fee)}</div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {firstDetail?.hidden_costs_notes && (
              <p className="mt-4 text-xs text-gray-600 italic">
                {firstDetail.hidden_costs_notes}
              </p>
            )}
          </section>
        )}

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
