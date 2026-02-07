import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { get } from "../api/client";
import Map, { type School } from "../components/Map";
import WaitingListGauge from "../components/WaitingListGauge";
import type {
  AdmissionsRecord,
  AdmissionsEstimate,
} from "../components/WaitingListGauge";
import SendToggle, { useSendEnabled, SendInfoPanel } from "../components/SendToggle";
import { OfstedTrajectory } from "../components/OfstedTrajectory";
import {
  ArrowLeft,
  Globe,
  BookOpen,
  Calendar,
  Clock,
  MapPin,
  Users,
  ExternalLink,
  AlertCircle,
} from "lucide-react";

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

interface Performance {
  id: number;
  school_id: number;
  metric_type: string;
  metric_value: string;
  year: number;
  source_url: string | null;
}

interface ClassSize {
  id: number;
  school_id: number;
  academic_year: string;
  year_group: string;
  num_pupils: number | null;
  num_classes: number | null;
  avg_class_size: number | null;
}

interface ParkingRatingSummary {
  school_id: number;
  total_ratings: number;
  avg_dropoff_chaos?: number | null;
  avg_pickup_chaos?: number | null;
  avg_parking_availability?: number | null;
  avg_road_congestion?: number | null;
  avg_restrictions_hazards?: number | null;
  overall_chaos_score?: number | null;
}

interface AdmissionsCriterion {
  id: number;
  school_id: number;
  priority_rank: number;
  category: string;
  description: string;
  religious_requirement: string | null;
  requires_sif: boolean;
  notes: string | null;
}

interface OfstedInspection {
  id: number;
  school_id: number;
  inspection_date: string;
  rating: string;
  strengths_quote?: string | null;
  improvements_quote?: string | null;
  report_url?: string | null;
  is_current: boolean;
}

interface OfstedTrajectoryResponse {
  school_id: number;
  trajectory: 'improving' | 'stable' | 'declining' | 'unknown';
  current_rating?: string | null;
  previous_rating?: string | null;
  inspection_age_years?: number | null;
  is_stale: boolean;
  history: OfstedInspection[];
}

interface SchoolDetail extends School {
  clubs: Club[];
  performance: Performance[];
  admissions_history: AdmissionsRecord[];
  admissions_criteria: AdmissionsCriterion[];
  prospectus_url: string | null;
  class_sizes: ClassSize[];
  parking_summary?: ParkingRatingSummary | null;
  ofsted_trajectory?: OfstedTrajectoryResponse | null;
}

const TABS = [
  "Overview",
  "Clubs",
  "Performance",
  "Term Dates",
  "Admissions",
  "Class Sizes",
] as const;
type Tab = (typeof TABS)[number];

const RATING_COLORS: Record<string, string> = {
  Outstanding: "bg-green-100 text-green-800 ring-1 ring-green-600/20",
  Good: "bg-blue-100 text-blue-800 ring-1 ring-blue-600/20",
  "Requires improvement": "bg-amber-100 text-amber-800 ring-1 ring-amber-600/20",
  Inadequate: "bg-red-100 text-red-800 ring-1 ring-red-600/20",
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
      <h3 className="text-lg font-semibold text-stone-800">{title}</h3>
      <div className="mt-2 space-y-3">
        {clubs.map((club) => (
          <div
            key={club.id}
            className="rounded-lg border border-stone-100 bg-stone-50 p-4"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-stone-900">{club.name}</p>
                {club.description && (
                  <p className="mt-0.5 text-sm text-stone-600">{club.description}</p>
                )}
              </div>
              {club.cost_per_session != null && (
                <span className="whitespace-nowrap rounded bg-brand-50 px-2 py-1 text-sm font-medium text-brand-700">
                  &pound;{club.cost_per_session.toFixed(2)}/session
                </span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-sm text-stone-500">
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

/** Determine trend arrow for a metric across years. */
function TrendArrow({ current, previous }: { current: number; previous: number }) {
  const diff = current - previous;
  if (Math.abs(diff) < 0.01) {
    return <span className="ml-1 text-stone-400" title="No change">&mdash;</span>;
  }
  if (diff > 0) {
    return (
      <span className="ml-1 text-green-600" title={`Up from ${previous}`}>
        &#9650;
      </span>
    );
  }
  return (
    <span className="ml-1 text-red-600" title={`Down from ${previous}`}>
      &#9660;
    </span>
  );
}

/** Extract a numeric value from a metric_value string for trend comparison. */
function extractNumeric(value: string): number | null {
  // Handle Progress8 values like "+0.30" or "-0.15"
  const p8Match = value.match(/^[+-]?\d+\.?\d*$/);
  if (p8Match) return parseFloat(value);
  // Handle "Expected standard: 65%" or "5+ GCSEs 9-4: 72%"
  const pctMatch = value.match(/(\d+)%/);
  if (pctMatch) return parseInt(pctMatch[1], 10);
  // Handle Attainment8 plain numbers like "48.2"
  const numMatch = value.match(/^\d+\.?\d*$/);
  if (numMatch) return parseFloat(value);
  return null;
}

/** Format an academic year number into a readable string. */
function academicYear(year: number): string {
  return `${year - 1}/${year}`;
}

function PerformanceTab({ performance }: { performance: Performance[] }) {
  if (performance.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
        <Users className="mx-auto h-10 w-10 text-stone-300" aria-hidden="true" />
        <h2 className="mt-3 text-lg font-semibold text-stone-900">
          No performance data available
        </h2>
        <p className="mt-1 text-sm text-stone-500">
          Academic results (SATs, GCSEs, Progress 8) are not available for this school.
          Check the school&apos;s website or the DfE performance tables for the latest results.
        </p>
      </div>
    );
  }

  // Group by metric_type, then sort by year
  const grouped: Record<string, Performance[]> = {};
  for (const p of performance) {
    if (!grouped[p.metric_type]) grouped[p.metric_type] = [];
    grouped[p.metric_type].push(p);
  }
  for (const key of Object.keys(grouped)) {
    grouped[key].sort((a, b) => a.year - b.year);
  }

  // Display order: primary metrics first, then secondary
  const metricOrder = ["SATs", "SATs_Higher", "GCSE", "Progress8", "Attainment8"];
  const metricLabels: Record<string, string> = {
    SATs: "SATs - Expected Standard",
    SATs_Higher: "SATs - Higher Standard",
    GCSE: "GCSE Results",
    Progress8: "Progress 8",
    Attainment8: "Attainment 8",
  };

  const orderedKeys = metricOrder.filter((k) => grouped[k]);
  // Add any remaining metric types not in our predefined order
  for (const key of Object.keys(grouped)) {
    if (!orderedKeys.includes(key)) orderedKeys.push(key);
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-6">
      <h2 className="text-xl font-semibold text-stone-900">
        Performance &amp; Ratings
      </h2>
      <div className="mt-4 space-y-6">
        {orderedKeys.map((metricType) => {
          const entries = grouped[metricType];
          const label = metricLabels[metricType] ?? metricType;
          const isProgress8 = metricType === "Progress8";

          return (
            <div key={metricType}>
              <h3 className="text-lg font-semibold text-stone-800">{label}</h3>
              <div className="mt-2 overflow-x-auto">
                <table className="min-w-full divide-y divide-stone-200">
                  <thead className="bg-stone-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-stone-500">
                        Academic Year
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-stone-500">
                        Result
                      </th>
                      {entries.length > 1 && (
                        <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-stone-500">
                          Trend
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 bg-white">
                    {entries.map((entry, idx) => {
                      const numVal = extractNumeric(entry.metric_value);
                      // Progress8 colour: green if positive, red if negative
                      let valueClass = "text-stone-900";
                      if (isProgress8 && numVal !== null) {
                        if (numVal > 0) valueClass = "text-green-700 font-semibold";
                        else if (numVal < 0) valueClass = "text-red-700 font-semibold";
                      }

                      const prevEntry = idx > 0 ? entries[idx - 1] : null;
                      const prevNum = prevEntry
                        ? extractNumeric(prevEntry.metric_value)
                        : null;

                      return (
                        <tr key={entry.id}>
                          <td className="whitespace-nowrap px-4 py-2 text-sm text-stone-600">
                            {academicYear(entry.year)}
                          </td>
                          <td
                            className={`whitespace-nowrap px-4 py-2 text-sm ${valueClass}`}
                          >
                            {entry.metric_value}
                          </td>
                          {entries.length > 1 && (
                            <td className="whitespace-nowrap px-4 py-2 text-sm">
                              {idx > 0 && numVal !== null && prevNum !== null ? (
                                <TrendArrow current={numVal} previous={prevNum} />
                              ) : (
                                <span className="text-stone-300">&mdash;</span>
                              )}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {entries[0]?.source_url && (
                <p className="mt-1 text-xs text-stone-400">
                  Source:{" "}
                  <a
                    href={entries[0].source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-stone-600"
                  >
                    DfE School Performance Data
                  </a>
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ClassSizesTab({ classSizes }: { classSizes: ClassSize[] }) {
  if (classSizes.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
        <Users className="mx-auto h-10 w-10 text-stone-300" aria-hidden="true" />
        <h2 className="mt-3 text-lg font-semibold text-stone-900">
          No class size data available
        </h2>
        <p className="mt-1 text-sm text-stone-500">
          Class size and enrollment information is not available for this school.
        </p>
      </div>
    );
  }

  // Group by academic year, then by year group
  const byYear: Record<string, ClassSize[]> = {};
  for (const cs of classSizes) {
    if (!byYear[cs.academic_year]) byYear[cs.academic_year] = [];
    byYear[cs.academic_year].push(cs);
  }

  // Sort years descending (most recent first)
  const years = Object.keys(byYear).sort((a, b) => b.localeCompare(a));

  // Calculate total pupils per year and overall trend
  const yearTotals = years.map((year) => {
    const total = byYear[year].reduce((sum, cs) => sum + (cs.num_pupils || 0), 0);
    return { year, total };
  }).reverse(); // Reverse for chronological order for trend calculation

  let trend = "Stable";
  let trendColor = "text-stone-600";
  if (yearTotals.length >= 2) {
    const oldest = yearTotals[0].total;
    const newest = yearTotals[yearTotals.length - 1].total;
    const changePct = ((newest - oldest) / oldest) * 100;
    if (changePct > 5) {
      trend = `Growing (+${changePct.toFixed(0)}%)`;
      trendColor = "text-green-600";
    } else if (changePct < -5) {
      trend = `Shrinking (${changePct.toFixed(0)}%)`;
      trendColor = "text-red-600";
    }
  }

  return (
    <div className="space-y-6">
      {/* Summary Card */}
      <div className="rounded-lg border border-stone-200 bg-white p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-stone-900">Class Size Trends</h2>
            <p className="mt-1 text-sm text-stone-600">
              Enrollment patterns over recent years show if the school is growing, stable, or shrinking.
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Trend</p>
            <p className={`mt-1 text-lg font-semibold ${trendColor}`}>{trend}</p>
          </div>
        </div>

        {/* Implications */}
        {trend !== "Stable" && (
          <div className="mt-4 rounded-md bg-stone-50 p-4">
            <h3 className="text-sm font-semibold text-stone-800">What this means:</h3>
            <ul className="mt-2 space-y-1 text-sm text-stone-600">
              {trend.startsWith("Growing") && (
                <>
                  <li>• School is becoming more popular or the local area is expanding</li>
                  <li>• May lead to larger class sizes or additional forms</li>
                  <li>• Facilities and resources may be stretched</li>
                  <li>• Positive indicator of school reputation and demand</li>
                </>
              )}
              {trend.startsWith("Shrinking") && (
                <>
                  <li>• Falling rolls may indicate declining popularity or demographic shifts</li>
                  <li>• Could face funding pressure (funding follows pupil numbers)</li>
                  <li>• May have smaller class sizes (potential benefit)</li>
                  <li>• Risk of reduced facilities, staff cuts, or future viability concerns</li>
                </>
              )}
            </ul>
          </div>
        )}
      </div>

      {/* Year-by-Year Breakdown */}
      <div className="rounded-lg border border-stone-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-stone-900">Enrollment by Year Group</h3>
        <div className="mt-4 space-y-6">
          {years.map((year) => {
            const yearData = byYear[year];
            const totalPupils = yearData.reduce((sum, cs) => sum + (cs.num_pupils || 0), 0);
            const totalClasses = yearData.reduce((sum, cs) => sum + (cs.num_classes || 0), 0);
            const avgClassSize = totalClasses > 0 ? (totalPupils / totalClasses).toFixed(1) : "N/A";

            return (
              <div key={year} className="border-t border-stone-100 pt-4 first:border-t-0 first:pt-0">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-base font-semibold text-stone-800">{year}</h4>
                  <div className="flex gap-6 text-sm text-stone-600">
                    <span><strong>{totalPupils}</strong> pupils</span>
                    <span><strong>{totalClasses}</strong> classes</span>
                    <span>Avg: <strong>{avgClassSize}</strong> per class</span>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-stone-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-stone-500">
                          Year Group
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-stone-500">
                          Pupils
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-stone-500">
                          Classes
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-stone-500">
                          Avg Class Size
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100 bg-white">
                      {yearData.map((cs) => (
                        <tr key={cs.id}>
                          <td className="whitespace-nowrap px-3 py-2 font-medium text-stone-900">
                            {cs.year_group}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-stone-600">
                            {cs.num_pupils ?? "—"}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-stone-600">
                            {cs.num_classes ?? "—"}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-stone-600">
                            {cs.avg_class_size?.toFixed(1) ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ClubsTab({ clubs }: { clubs: Club[] }) {
  if (clubs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
        <Clock className="mx-auto h-10 w-10 text-stone-300" aria-hidden="true" />
        <h2 className="mt-3 text-lg font-semibold text-stone-900">
          No club information available
        </h2>
        <p className="mt-1 text-sm text-stone-500">
          We don&apos;t have breakfast or after-school club details for this school.
          Contact the school directly for their wraparound care options.
        </p>
      </div>
    );
  }

  const breakfastClubs = clubs.filter((c) => c.club_type === "breakfast");
  const afterSchoolClubs = clubs.filter((c) => c.club_type === "after_school");

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-6">
      <h2 className="text-xl font-semibold text-stone-900">
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
  const [school, setSchool] = useState<SchoolDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [admissionsEstimate, setAdmissionsEstimate] =
    useState<AdmissionsEstimate | null>(null);
  const [estimateLoaded, setEstimateLoaded] = useState(false);
  const [sendEnabled] = useSendEnabled();

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    get<SchoolDetail>(`/schools/${id}`)
      .then(setSchool)
      .catch(() => setSchool(null))
      .finally(() => setLoading(false));
  }, [id]);

  // Fetch admissions estimate when Admissions tab is selected
  useEffect(() => {
    if (activeTab !== "Admissions" || !school || estimateLoaded) return;
    // Use school's distance_km if available, otherwise use catchment_radius_km as a proxy
    const userDist = school.distance_km ?? school.catchment_radius_km ?? 2.0;
    get<AdmissionsEstimate>(
      `/schools/${school.id}/admissions/estimate`,
      { distance_km: userDist },
    )
      .then((est) => {
        setAdmissionsEstimate(est);
        setEstimateLoaded(true);
      })
      .catch(() => {
        setEstimateLoaded(true);
      });
  }, [activeTab, school, estimateLoaded]);

  /** Handle keyboard navigation for tabs (arrow keys). */
  function handleTabKeyDown(e: React.KeyboardEvent, tabIndex: number) {
    let nextIndex = tabIndex;
    if (e.key === "ArrowRight") {
      nextIndex = (tabIndex + 1) % TABS.length;
    } else if (e.key === "ArrowLeft") {
      nextIndex = (tabIndex - 1 + TABS.length) % TABS.length;
    } else if (e.key === "Home") {
      nextIndex = 0;
    } else if (e.key === "End") {
      nextIndex = TABS.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    setActiveTab(TABS[nextIndex]);
    // Focus the new tab button
    const tabBtn = document.getElementById(`school-tab-${TABS[nextIndex]}`);
    tabBtn?.focus();
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
        {/* Skeleton loading state */}
        <div className="animate-pulse" aria-live="polite" aria-label="Loading school details">
          <div className="h-4 w-24 rounded bg-stone-200" />
          <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
            <div className="flex-1">
              <div className="h-8 w-3/4 rounded bg-stone-200" />
              <div className="mt-2 h-4 w-1/2 rounded bg-stone-200" />
              <div className="mt-1 h-3 w-1/3 rounded bg-stone-200" />
            </div>
            <div className="h-8 w-24 rounded-full bg-stone-200" />
          </div>
          <div className="mt-4 flex gap-2">
            <div className="h-6 w-20 rounded bg-stone-200" />
            <div className="h-6 w-16 rounded bg-stone-200" />
            <div className="h-6 w-24 rounded bg-stone-200" />
          </div>
          <div className="mt-6 flex gap-4 border-b border-stone-200 pb-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-4 w-16 rounded bg-stone-200" />
            ))}
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className="h-64 rounded-lg bg-stone-200" />
            <div className="h-64 rounded-lg bg-stone-200" />
          </div>
        </div>
      </main>
    );
  }

  if (!school) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
        <Link
          to="/schools"
          className="inline-flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-700 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to schools
        </Link>
        <div className="mt-8 rounded-lg border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
          <AlertCircle className="mx-auto h-12 w-12 text-stone-300" aria-hidden="true" />
          <h1 className="mt-4 text-xl font-bold text-stone-900">School not found</h1>
          <p className="mt-2 text-sm text-stone-500">
            We couldn&apos;t find the school you&apos;re looking for. It may have been removed
            or the link might be incorrect.
          </p>
          <Link
            to="/schools"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
          >
            Browse all schools
          </Link>
        </div>
      </main>
    );
  }

  const badge = RATING_COLORS[school.ofsted_rating ?? ""] ?? "bg-stone-100 text-stone-700 ring-1 ring-stone-300/50";

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
      {/* Back navigation */}
      <Link
        to="/schools"
        className="inline-flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-700 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to schools
      </Link>

      {/* School header */}
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">{school.name}</h1>
          <div className="mt-1.5 flex items-center gap-1.5 text-sm text-stone-600">
            <MapPin className="h-3.5 w-3.5 flex-shrink-0 text-stone-400" aria-hidden="true" />
            <span>{school.address}, {school.postcode}</span>
          </div>
          {school.ethos && (
            <p className="mt-2.5 text-sm leading-relaxed text-stone-600">
              {school.ethos}
            </p>
          )}
        </div>
        <div className="flex flex-shrink-0 flex-col items-end gap-2">
          {school.ofsted_rating && (
            <span className={`inline-flex items-center rounded-full px-3.5 py-1.5 text-sm font-semibold ${badge}`}>
              {school.ofsted_rating}
            </span>
          )}
          {school.ofsted_date && (
            <span className="text-xs text-stone-400">
              Inspected {school.ofsted_date}
            </span>
          )}
        </div>
      </div>

      {/* Quick facts - parent-relevant info, no URN */}
      <div className="mt-4 flex flex-wrap gap-2 text-xs sm:text-sm">
        <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2.5 py-1 font-medium text-stone-700">
          Ages {school.age_range_from}&ndash;{school.age_range_to}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2.5 py-1 font-medium text-stone-700">
          {school.gender_policy}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2.5 py-1 font-medium text-stone-700 capitalize">
          {school.type || (school.is_private ? "Independent" : "State")}
        </span>
        {school.faith && (
          <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2.5 py-1 font-medium text-stone-700">
            {school.faith}
          </span>
        )}
        {school.distance_km != null && (
          <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 font-medium text-brand-700">
            <MapPin className="h-3 w-3" aria-hidden="true" />
            {school.distance_km.toFixed(1)} km away
          </span>
        )}
      </div>

      {/* Tab navigation - with scroll indicators on mobile */}
      <div className="relative mt-6">
        <div className="border-b border-stone-200">
          <nav
            className="-mb-px flex overflow-x-auto scrollbar-hide"
            role="tablist"
            aria-label="School information sections"
          >
            {TABS.map((tab, idx) => (
              <button
                key={tab}
                id={`school-tab-${tab}`}
                role="tab"
                aria-selected={activeTab === tab}
                aria-controls={`school-tabpanel-${tab}`}
                tabIndex={activeTab === tab ? 0 : -1}
                onClick={() => setActiveTab(tab)}
                onKeyDown={(e) => handleTabKeyDown(e, idx)}
                className={`flex-shrink-0 whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500 sm:px-4 ${
                  activeTab === tab
                    ? "border-brand-600 text-brand-600"
                    : "border-transparent text-stone-500 hover:border-stone-300 hover:text-stone-700"
                }`}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>
        {/* Right-edge fade to indicate more tabs are scrollable on mobile */}
        <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-stone-50 to-transparent sm:hidden" aria-hidden="true" />
      </div>

      {/* Tab content */}
      <div
        className="mt-6"
        id={`school-tabpanel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`school-tab-${activeTab}`}
      >
        {activeTab === "Overview" && (
          <div className="space-y-6">
            {/* Quick links bar - compact, side-by-side */}
            {(school.website || school.prospectus_url) && (
              <div className="flex flex-wrap gap-3">
                {school.website && (
                  <a
                    href={school.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 shadow-sm transition-all hover:border-stone-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
                  >
                    <Globe className="h-4 w-4 text-brand-600" aria-hidden="true" />
                    School website
                    <ExternalLink className="h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
                  </a>
                )}
                {school.prospectus_url && (
                  <a
                    href={school.prospectus_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 shadow-sm transition-all hover:border-stone-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
                  >
                    <BookOpen className="h-4 w-4 text-brand-600" aria-hidden="true" />
                    View prospectus
                    <ExternalLink className="h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
                  </a>
                )}
              </div>
            )}

            <div className="grid gap-6 lg:grid-cols-2">
              {/* School details card */}
              <div className="rounded-lg border border-stone-200 bg-white p-6">
                <h2 className="text-lg font-semibold text-stone-900">School details</h2>
                <dl className="mt-4 space-y-3 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-stone-500">School type</dt>
                    <dd className="font-medium text-stone-900 capitalize text-right">{school.type}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-stone-500">Local authority</dt>
                    <dd className="font-medium text-stone-900 text-right">{school.council}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-stone-500">Age range</dt>
                    <dd className="font-medium text-stone-900 text-right">
                      {school.age_range_from}&ndash;{school.age_range_to} years
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-stone-500">Catchment radius</dt>
                    <dd className="font-medium text-stone-900 text-right">
                      {school.catchment_radius_km} km
                    </dd>
                  </div>
                  {school.ofsted_rating && (
                    <div className="flex justify-between gap-4">
                      <dt className="text-stone-500">Ofsted rating</dt>
                      <dd>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${badge}`}>
                          {school.ofsted_rating}
                        </span>
                      </dd>
                    </div>
                  )}
                  {school.ofsted_date && (
                    <div className="flex justify-between gap-4">
                      <dt className="text-stone-500">Last inspection</dt>
                      <dd className="font-medium text-stone-900 text-right">
                        {school.ofsted_date}
                      </dd>
                    </div>
                  )}
                </dl>
                {/* URN - subtle reference info at bottom */}
                <p className="mt-4 border-t border-stone-100 pt-3 text-xs text-stone-400">
                  URN: {school.urn}
                </p>
              </div>

              {/* Catchment map */}
              <div className="h-[300px] overflow-hidden rounded-lg border border-stone-200 bg-white sm:h-[350px]">
                {school.lat != null && school.lng != null ? (
                  <Map
                    center={[school.lat, school.lng]}
                    zoom={14}
                    schools={[school]}
                    selectedSchoolId={school.id}
                  />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-center p-6">
                    <MapPin className="h-8 w-8 text-stone-300" aria-hidden="true" />
                    <p className="mt-2 text-sm text-stone-400">
                      Location data not available for this school
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Ofsted Trajectory */}
            {school.ofsted_trajectory && (
              <OfstedTrajectory trajectory={school.ofsted_trajectory} />
            )}

            {/* SEND information - hidden by default, cleaner toggle */}
            {sendEnabled && (
              <SendInfoPanel
                senProvision={null}
                ehcpFriendly={null}
                accessibilityInfo={null}
                specialistUnit={null}
              />
            )}
            {!sendEnabled && (
              <div className="rounded-lg border border-stone-100 bg-stone-50/50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-stone-500">
                    Looking for SEND provision details? Enable below to see special educational needs information.
                  </p>
                  <SendToggle />
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "Clubs" && (
          <ClubsTab clubs={school.clubs ?? []} />
        )}

        {activeTab === "Performance" && (
          <PerformanceTab performance={school.performance ?? []} />
        )}

        {activeTab === "Term Dates" && (
          <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
            <Calendar className="mx-auto h-10 w-10 text-stone-300" aria-hidden="true" />
            <h2 className="mt-3 text-lg font-semibold text-stone-900">
              No term dates available
            </h2>
            <p className="mt-1 text-sm text-stone-500">
              Term date information is not available for this school.
              Check the school&apos;s website or your local council for published term dates.
            </p>
            {school.website && (
              <a
                href={school.website}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-700 shadow-sm hover:border-stone-300 hover:shadow-md transition-all focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
              >
                <Globe className="h-4 w-4 text-brand-600" aria-hidden="true" />
                Check school website
                <ExternalLink className="h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
              </a>
            )}
          </div>
        )}

        {activeTab === "Admissions" && (
          <div>
            <WaitingListGauge
              admissionsHistory={school.admissions_history ?? []}
              estimate={admissionsEstimate}
              userDistanceKm={school.distance_km ?? school.catchment_radius_km ?? null}
            />

            {/* Admissions Criteria Breakdown */}
            {(school.admissions_criteria ?? []).length > 0 && (
              <div className="mt-6 rounded-lg border border-stone-200 bg-white p-6">
                <h3 className="text-lg font-semibold text-stone-900">Admissions Priority Order</h3>
                <p className="mt-2 text-sm text-stone-600">
                  When the school is oversubscribed, places are allocated in the following priority order:
                </p>
                <div className="mt-4 space-y-4">
                  {[...(school.admissions_criteria ?? [])]
                    .sort((a, b) => a.priority_rank - b.priority_rank)
                    .map((criterion) => (
                      <div key={criterion.id} className="border-l-4 border-brand-500 bg-brand-50 p-4 rounded">
                        <div className="flex items-start">
                          <div className="flex-shrink-0 mr-3">
                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
                              {criterion.priority_rank}
                            </span>
                          </div>
                          <div className="flex-1">
                            <h4 className="text-base font-semibold text-stone-900">{criterion.category}</h4>
                            <p className="mt-1 text-sm text-stone-700">{criterion.description}</p>

                            {criterion.religious_requirement && (
                              <div className="mt-2 rounded bg-white p-3 border border-amber-200">
                                <p className="text-xs font-medium text-amber-800 uppercase tracking-wide">Religious Requirement</p>
                                <p className="mt-1 text-sm text-stone-700">{criterion.religious_requirement}</p>
                              </div>
                            )}

                            <div className="mt-2 flex flex-wrap gap-2">
                              {criterion.requires_sif && (
                                <span className="inline-flex items-center rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-800">
                                  Requires SIF
                                </span>
                              )}
                            </div>

                            {criterion.notes && (
                              <p className="mt-2 text-xs italic text-stone-600">{criterion.notes}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
                {(school.admissions_criteria ?? []).some(c => c.requires_sif) && (
                  <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-4">
                    <p className="text-sm text-amber-900">
                      <strong>Note:</strong> This school requires a Supplementary Information Form (SIF) for certain criteria.
                      The SIF must be submitted in addition to your council's standard application form.
                      Check the school's website for deadlines and submission instructions.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Historical admissions table */}
            {(school.admissions_history ?? []).length > 0 && (
              <div className="mt-6 rounded-lg border border-stone-200 bg-white p-6">
                <h3 className="text-lg font-semibold text-stone-900">Historical Admissions</h3>
                <div className="mt-4 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-stone-200 text-left text-xs font-medium uppercase text-stone-500">
                        <th className="pb-2 pr-4">Year</th>
                        <th className="pb-2 pr-4">Places</th>
                        <th className="pb-2 pr-4">Applications</th>
                        <th className="pb-2 pr-4">Last Distance</th>
                        <th className="pb-2 pr-4">Off Waiting List</th>
                        <th className="pb-2 pr-4">Appeals Heard</th>
                        <th className="pb-2">Appeals Upheld</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...(school.admissions_history ?? [])]
                        .sort((a, b) => b.academic_year.localeCompare(a.academic_year))
                        .map((r) => (
                          <tr key={r.academic_year} className="border-b border-stone-100">
                            <td className="py-2 pr-4 font-medium">{r.academic_year}</td>
                            <td className="py-2 pr-4">{r.places_offered ?? "—"}</td>
                            <td className="py-2 pr-4">{r.applications_received ?? "—"}</td>
                            <td className="py-2 pr-4">{r.last_distance_offered_km != null ? `${r.last_distance_offered_km.toFixed(2)} km` : "—"}</td>
                            <td className="py-2 pr-4">{r.waiting_list_offers ?? "—"}</td>
                            <td className="py-2 pr-4">{r.appeals_heard ?? "—"}</td>
                            <td className="py-2">{r.appeals_upheld ?? "—"}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "Class Sizes" && (
          <ClassSizesTab classSizes={school.class_sizes ?? []} />
        )}
      </div>
    </main>
  );
}
