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

/** Format a time string like "08:15:00" to "8:15 AM". */
function formatTime(timeStr: string | null): string {
  if (!timeStr) return "Not available";
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
  if (amount == null) return "Not available";
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

/** Skeleton loading state for the detail page. */
function DetailSkeleton() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
      <div className="animate-pulse">
        {/* Back link skeleton */}
        <div className="mb-6 h-4 w-40 rounded bg-stone-200" />

        {/* Header skeleton */}
        <div className="space-y-3">
          <div className="h-8 w-3/4 rounded bg-stone-200" />
          <div className="h-4 w-1/2 rounded bg-stone-100" />
          <div className="flex gap-2">
            <div className="h-7 w-20 rounded-full bg-stone-100" />
            <div className="h-7 w-16 rounded-full bg-stone-100" />
            <div className="h-7 w-24 rounded-full bg-violet-100" />
          </div>
        </div>

        {/* Content grid skeleton */}
        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="h-64 rounded-lg border border-stone-200 bg-white" />
          <div className="h-64 rounded-lg border border-stone-200 bg-white" />
          <div className="h-48 rounded-lg border border-stone-200 bg-white" />
          <div className="h-48 rounded-lg border border-stone-200 bg-white" />
        </div>
      </div>
    </main>
  );
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
    return <DetailSkeleton />;
  }

  if (!school) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
        <div className="flex flex-col items-center py-16 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-stone-100">
            <svg className="h-8 w-8 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <h1 className="mt-4 text-xl font-bold text-stone-900 sm:text-2xl">School not found</h1>
          <p className="mt-2 max-w-md text-sm text-stone-500">
            We couldn't find this school. It may have been removed or the link may be incorrect.
          </p>
          <Link
            to="/private-schools"
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Browse private schools
          </Link>
        </div>
      </main>
    );
  }

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
      {/* Back link with proper touch target */}
      <Link
        to="/private-schools"
        className="mb-6 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 -ml-3 text-sm font-medium text-stone-600 transition hover:bg-stone-100 hover:text-stone-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
        aria-label="Back to private schools list"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
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
          <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">{school.name}</h1>
          <p className="mt-1 text-sm text-stone-600 sm:text-base">{school.address}</p>
          <p className="text-xs text-stone-500 sm:text-sm">{school.postcode}</p>
          {school.ethos && (
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-stone-600">
              {school.ethos}
            </p>
          )}
        </div>
      </div>

      {/* Quick facts */}
      <div className="mt-4 flex flex-wrap gap-2 text-sm" aria-label="School quick facts">
        <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-700">
          Ages {school.age_range_from}&ndash;{school.age_range_to}
        </span>
        <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-700">
          {school.gender_policy}
        </span>
        <span className="inline-flex items-center rounded-full bg-violet-50 px-3 py-1 font-medium text-violet-700 ring-1 ring-violet-600/20">
          Independent
        </span>
        {school.faith && (
          <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-700">{school.faith}</span>
        )}
        <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-500 text-xs">
          URN: {school.urn}
        </span>
      </div>

      {/* Fee summary banner */}
      {feeMin != null && feeMax != null && (
        <div className="mt-6 rounded-xl bg-gradient-to-r from-brand-50 to-indigo-50 border border-brand-200 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-brand-800">Termly fees</p>
              <p className="mt-0.5 text-xl font-bold text-brand-900 sm:text-2xl">
                {feeMin === feeMax
                  ? `${formatFee(feeMin)} per term`
                  : `${formatFee(feeMin)} -- ${formatFee(feeMax)} per term`}
              </p>
            </div>
            {feeIncreasePct != null && (
              <div className="rounded-lg bg-white/60 px-3 py-2 text-right">
                <p className="text-xs text-brand-700">Est. annual increase</p>
                <p className="text-sm font-semibold text-brand-900">~{feeIncreasePct}%</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Content grid */}
      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Fees per age group */}
        <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">Fee Breakdown</h2>
          <p className="mt-1 text-sm text-stone-500">
            Fees by age group, shown per term and per year.
          </p>
          {details.length > 0 ? (
            <div className="mt-4 divide-y divide-stone-100">
              {details.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between py-3 text-sm"
                >
                  <span className="font-medium text-stone-700">
                    {d.fee_age_group ?? "General"}
                  </span>
                  <div className="text-right">
                    <span className="font-semibold text-stone-900">
                      {formatFee(d.termly_fee)}
                    </span>
                    <span className="ml-1 text-stone-400">/term</span>
                    {d.annual_fee != null && (
                      <span className="ml-3 text-xs text-stone-500">
                        ({formatFee(d.annual_fee)}/yr)
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 flex items-center gap-3 rounded-lg bg-stone-50 p-4 text-sm text-stone-500">
              <svg className="h-5 w-5 flex-shrink-0 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              No fee data available yet.
            </div>
          )}
        </section>

        {/* School Hours */}
        <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">School Hours</h2>
          <p className="mt-1 text-sm text-stone-500">
            Daily start and end times for the school day.
          </p>
          {firstDetail && (firstDetail.school_day_start || firstDetail.school_day_end) ? (
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-green-700">Start</p>
                <p className="mt-1 text-xl font-bold text-green-900">
                  {formatTime(firstDetail.school_day_start)}
                </p>
              </div>
              <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-amber-700">End</p>
                <p className="mt-1 text-xl font-bold text-amber-900">
                  {formatTime(firstDetail.school_day_end)}
                </p>
              </div>
            </div>
          ) : (
            <div className="mt-4 flex items-center gap-3 rounded-lg bg-stone-50 p-4 text-sm text-stone-500">
              <svg className="h-5 w-5 flex-shrink-0 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              No hours data available yet.
            </div>
          )}
        </section>

        {/* True Cost Breakdown */}
        {details.length > 0 && (
          <section className="rounded-xl border border-orange-200 bg-orange-50/50 p-5 sm:p-6 md:col-span-2">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-orange-100">
                <svg className="h-5 w-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-semibold text-stone-900">True Annual Cost</h2>
                <p className="mt-0.5 text-sm text-stone-600">
                  The headline fee is just the starting point. These are the additional compulsory and optional costs you should budget for.
                </p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {details.map((detail) => {
                const costs = calculateTrueAnnualCost(detail);
                return (
                  <div
                    key={detail.id}
                    className="rounded-xl border border-orange-200 bg-white p-5"
                  >
                    <h3 className="font-semibold text-stone-900">
                      {detail.fee_age_group || "General"}
                    </h3>

                    {/* Headline cost */}
                    <div className="mt-4 border-b border-stone-200 pb-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-stone-600">Headline annual fee</span>
                        <span className="font-medium text-stone-900">
                          {formatFee(costs.headline)}
                        </span>
                      </div>
                    </div>

                    {/* Compulsory extras */}
                    <div className="mt-3 border-b border-stone-200 pb-3">
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="font-medium text-stone-700">Compulsory extras</span>
                        <span className="font-semibold text-orange-700">
                          +{formatFee(costs.compulsory)}
                        </span>
                      </div>

                      <div className="space-y-1 text-xs text-stone-600">
                        {detail.lunches_compulsory && detail.lunches_per_term && (
                          <div className="flex justify-between">
                            <span>Lunches</span>
                            <span>{formatFee(detail.lunches_per_term * 3)}/yr</span>
                          </div>
                        )}
                        {detail.exam_fees_compulsory && detail.exam_fees_per_year && (
                          <div className="flex justify-between">
                            <span>Exam fees</span>
                            <span>{formatFee(detail.exam_fees_per_year)}/yr</span>
                          </div>
                        )}
                        {detail.textbooks_compulsory && detail.textbooks_per_year && (
                          <div className="flex justify-between">
                            <span>Textbooks</span>
                            <span>{formatFee(detail.textbooks_per_year)}/yr</span>
                          </div>
                        )}
                        {detail.uniform_compulsory && detail.uniform_per_year && (
                          <div className="flex justify-between">
                            <span>Uniform</span>
                            <span>{formatFee(detail.uniform_per_year)}/yr</span>
                          </div>
                        )}
                        {detail.insurance_compulsory && detail.insurance_per_year && (
                          <div className="flex justify-between">
                            <span>Insurance</span>
                            <span>{formatFee(detail.insurance_per_year)}/yr</span>
                          </div>
                        )}
                        {detail.building_fund_compulsory && detail.building_fund_per_year && (
                          <div className="flex justify-between">
                            <span>Building fund</span>
                            <span>{formatFee(detail.building_fund_per_year)}/yr</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* True annual cost */}
                    <div className="mt-3 rounded-lg bg-orange-100 px-4 py-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-orange-900">True annual cost</span>
                        <span className="text-xl font-bold text-orange-900">
                          {formatFee(costs.total)}
                        </span>
                      </div>
                    </div>

                    {/* Optional extras */}
                    {costs.optional > 0 && (
                      <details className="mt-3 border-t border-stone-200 pt-3">
                        <summary className="flex cursor-pointer items-center justify-between text-xs font-medium text-stone-600 hover:text-stone-900">
                          <span>Optional extras</span>
                          <span className="font-medium text-stone-700">
                            +{formatFee(costs.optional)}
                          </span>
                        </summary>
                        <div className="mt-2 space-y-1 text-xs text-stone-500">
                          {!detail.lunches_compulsory && detail.lunches_per_term && (
                            <div className="flex justify-between">
                              <span>Lunches</span>
                              <span>{formatFee(detail.lunches_per_term * 3)}/yr</span>
                            </div>
                          )}
                          {detail.trips_per_term && (
                            <div className="flex justify-between">
                              <span>Trips</span>
                              <span>{formatFee(detail.trips_per_term * 3)}/yr</span>
                            </div>
                          )}
                          {detail.music_tuition_per_term && (
                            <div className="flex justify-between">
                              <span>Music tuition</span>
                              <span>{formatFee(detail.music_tuition_per_term * 3)}/yr</span>
                            </div>
                          )}
                          {detail.sports_per_term && (
                            <div className="flex justify-between">
                              <span>Sports</span>
                              <span>{formatFee(detail.sports_per_term * 3)}/yr</span>
                            </div>
                          )}
                          {!detail.insurance_compulsory && detail.insurance_per_year && (
                            <div className="flex justify-between">
                              <span>Insurance</span>
                              <span>{formatFee(detail.insurance_per_year)}/yr</span>
                            </div>
                          )}
                          {!detail.building_fund_compulsory && detail.building_fund_per_year && (
                            <div className="flex justify-between">
                              <span>Building fund</span>
                              <span>{formatFee(detail.building_fund_per_year)}/yr</span>
                            </div>
                          )}
                        </div>
                      </details>
                    )}

                    {/* One-time costs */}
                    {(detail.registration_fee || detail.deposit_fee) && (
                      <div className="mt-3 border-t border-stone-200 pt-3">
                        <p className="text-xs font-medium text-stone-600">One-time costs (first year)</p>
                        <div className="mt-1 space-y-1 text-xs text-stone-500">
                          {detail.registration_fee && (
                            <div className="flex justify-between">
                              <span>Registration</span>
                              <span>{formatFee(detail.registration_fee)}</span>
                            </div>
                          )}
                          {detail.deposit_fee && (
                            <div className="flex justify-between">
                              <span>Deposit (often refundable)</span>
                              <span>{formatFee(detail.deposit_fee)}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {firstDetail?.hidden_costs_notes && (
              <p className="mt-4 text-xs text-stone-600 italic">
                {firstDetail.hidden_costs_notes}
              </p>
            )}
          </section>
        )}

        {/* Transport */}
        <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">Transport</h2>
          <p className="mt-1 text-sm text-stone-500">
            School transport availability and details.
          </p>
          {providesTransport != null ? (
            <div className="mt-4 space-y-3">
              <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ${
                providesTransport
                  ? "bg-green-50 text-green-800 ring-1 ring-green-600/20"
                  : "bg-stone-100 text-stone-700"
              }`}>
                <span
                  className={`inline-block h-2 w-2 rounded-full ${providesTransport ? "bg-green-500" : "bg-stone-400"}`}
                  aria-hidden="true"
                />
                {providesTransport ? "Transport provided" : "No school transport"}
              </div>
              {transportNotes && (
                <p className="text-sm leading-relaxed text-stone-600">{transportNotes}</p>
              )}
            </div>
          ) : (
            <div className="mt-4 flex items-center gap-3 rounded-lg bg-stone-50 p-4 text-sm text-stone-500">
              <svg className="h-5 w-5 flex-shrink-0 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              No transport data available yet.
            </div>
          )}
        </section>

        {/* Holiday Schedule */}
        <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">
            Holiday Schedule
          </h2>
          <p className="mt-1 text-sm text-stone-500">
            Private schools often have different term dates from state schools.
          </p>
          {holidayNotes ? (
            <p className="mt-4 text-sm leading-relaxed text-stone-600">{holidayNotes}</p>
          ) : (
            <div className="mt-4 flex items-center gap-3 rounded-lg bg-stone-50 p-4 text-sm text-stone-500">
              <svg className="h-5 w-5 flex-shrink-0 text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              No holiday schedule data available yet.
            </div>
          )}
        </section>

        {/* General Information */}
        <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">
            General Information
          </h2>
          <dl className="mt-4 divide-y divide-stone-100 text-sm">
            <div className="flex justify-between py-2.5">
              <dt className="text-stone-500">Address</dt>
              <dd className="max-w-[60%] text-right font-medium text-stone-900">
                {school.address}
              </dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-stone-500">Postcode</dt>
              <dd className="font-medium text-stone-900">{school.postcode}</dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-stone-500">Age Range</dt>
              <dd className="font-medium text-stone-900">
                {school.age_range_from}&ndash;{school.age_range_to}
              </dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-stone-500">Gender Policy</dt>
              <dd className="font-medium text-stone-900">
                {school.gender_policy}
              </dd>
            </div>
            {school.faith && (
              <div className="flex justify-between py-2.5">
                <dt className="text-stone-500">Faith</dt>
                <dd className="font-medium text-stone-900">{school.faith}</dd>
              </div>
            )}
            <div className="flex justify-between py-2.5">
              <dt className="text-stone-500">Council</dt>
              <dd className="font-medium text-stone-900">{school.council}</dd>
            </div>
          </dl>
        </section>

        {/* Location Map */}
        <section className="overflow-hidden rounded-xl border border-stone-200 bg-white">
          <div className="p-5 sm:p-6 pb-0 sm:pb-0">
            <h2 className="text-lg font-semibold text-stone-900">Location</h2>
          </div>
          <div className="mt-4 h-[300px]">
            {school.lat != null && school.lng != null ? (
              <Map
                center={[school.lat, school.lng]}
                zoom={14}
                schools={[school]}
                selectedSchoolId={school.id}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-stone-400">
                No location data available
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
