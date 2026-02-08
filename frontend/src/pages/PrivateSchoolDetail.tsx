import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  GraduationCap,
  Globe,
  ExternalLink,
  ChevronRight,
  PlusCircle,
  Clock,
  Bus,
  Calendar,
  PoundSterling,
  Info,
  MapPin,
  Award,
  BookOpen,
  ClipboardCheck,
  Users,
  CalendarDays,
  Share2,
  Check,
} from "lucide-react";
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

interface BursaryData {
  id: number;
  max_percentage: number | null;
  min_percentage: number | null;
  income_threshold: number | null;
  eligibility_notes: string | null;
  application_deadline: string | null;
  application_url: string | null;
  percentage_of_pupils: number | null;
  notes: string | null;
}

interface ScholarshipData {
  id: number;
  scholarship_type: string;
  value_description: string | null;
  value_percentage: number | null;
  entry_points: string | null;
  assessment_method: string | null;
  application_deadline: string | null;
  notes: string | null;
}

interface EntryAssessmentData {
  id: number;
  entry_point: string;
  assessment_type: string | null;
  subjects_tested: string | null;
  registration_deadline: string | null;
  assessment_date: string | null;
  offer_date: string | null;
  registration_fee: number | null;
  notes: string | null;
}

interface OpenDayData {
  id: number;
  event_date: string;
  event_time: string | null;
  event_type: string;
  registration_required: boolean;
  booking_url: string | null;
  description: string | null;
}

interface SiblingDiscountData {
  id: number;
  second_child_percent: number | null;
  third_child_percent: number | null;
  fourth_child_percent: number | null;
  conditions: string | null;
  stacks_with_bursary: boolean | null;
  notes: string | null;
}

/** Extended school response with private details and admissions info. */
interface PrivateSchoolResponse extends School {
  private_details: PrivateDetail[];
  bursaries?: BursaryData[];
  scholarships?: ScholarshipData[];
  entry_assessments?: EntryAssessmentData[];
  open_days?: OpenDayData[];
  sibling_discounts?: SiblingDiscountData[];
}

/* ------------------------------------------------------------------ */
/* Tabs                                                                */
/* ------------------------------------------------------------------ */
const ALL_TABS = ["Overview", "Fees", "Admissions", "Hours & Transport", "True Cost"] as const;
type Tab = (typeof ALL_TABS)[number];

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/* No-data placeholder component                                       */
/* ------------------------------------------------------------------ */
function NoData({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-stone-50 border border-dashed border-stone-200 p-5 text-sm text-stone-500">
      <Icon className="h-5 w-5 flex-shrink-0 text-stone-400" aria-hidden="true" />
      <div>
        <p className="font-medium text-stone-700">{title}</p>
        <p className="mt-0.5">{description}</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Skeleton loading state                                              */
/* ------------------------------------------------------------------ */
function DetailSkeleton() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
      <div className="animate-pulse">
        {/* Breadcrumb skeleton */}
        <div className="flex gap-2 mb-6">
          <div className="h-3 w-16 rounded bg-stone-200" />
          <div className="h-3 w-4 rounded bg-stone-100" />
          <div className="h-3 w-28 rounded bg-stone-200" />
          <div className="h-3 w-4 rounded bg-stone-100" />
          <div className="h-3 w-40 rounded bg-stone-200" />
        </div>

        {/* Header skeleton */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-xl bg-private-50" />
            <div className="flex-1">
              <div className="h-7 w-3/4 rounded bg-stone-200" />
              <div className="mt-2 h-4 w-1/2 rounded bg-stone-100" />
            </div>
          </div>
          <div className="flex gap-2 mt-2">
            <div className="h-7 w-20 rounded-full bg-stone-100" />
            <div className="h-7 w-16 rounded-full bg-stone-100" />
            <div className="h-7 w-24 rounded-full bg-private-50" />
          </div>
        </div>

        {/* Fee banner skeleton */}
        <div className="mt-6 h-20 rounded-xl bg-private-50" />

        {/* Tabs skeleton */}
        <div className="mt-6 flex gap-4 border-b border-stone-200 pb-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-4 w-20 rounded bg-stone-200" />
          ))}
        </div>

        {/* Content grid skeleton */}
        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="h-64 rounded-xl border border-stone-200 bg-white" />
          <div className="h-64 rounded-xl border border-stone-200 bg-white" />
        </div>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */
export default function PrivateSchoolDetail() {
  const { id } = useParams<{ id: string }>();
  const [school, setSchool] = useState<PrivateSchoolResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [tabDirection, setTabDirection] = useState<"left" | "right" | "none">("none");
  const prevTabIndexRef = useRef(0);
  const [shareToast, setShareToast] = useState(false);

  /** Switch tab with directional awareness for animation. */
  const switchTab = useCallback((newTab: Tab) => {
    const allTabs = ALL_TABS as readonly string[];
    const oldIndex = allTabs.indexOf(activeTab);
    const newIndex = allTabs.indexOf(newTab);
    if (newIndex > oldIndex) setTabDirection("left");
    else if (newIndex < oldIndex) setTabDirection("right");
    else setTabDirection("none");
    prevTabIndexRef.current = newIndex;
    setActiveTab(newTab);
  }, [activeTab]);

  /** Share school via Web Share API or copy link to clipboard. */
  async function handleShare() {
    const url = window.location.href;
    const title = school?.name ? `${school.name} - School Finder` : "School Finder";
    const text = school?.name
      ? `Check out ${school.name} on School Finder`
      : "Check out this school on School Finder";

    if (navigator.share) {
      try {
        await navigator.share({ title, text, url });
      } catch {
        // User cancelled the share dialog — do nothing
      }
    } else {
      try {
        await navigator.clipboard.writeText(url);
        setShareToast(true);
        setTimeout(() => setShareToast(false), 2200);
      } catch {
        // Clipboard API not available — try fallback
        const input = document.createElement("input");
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand("copy");
        document.body.removeChild(input);
        setShareToast(true);
        setTimeout(() => setShareToast(false), 2200);
      }
    }
  }

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    get<PrivateSchoolResponse>(`/private-schools/${id}`)
      .then(setSchool)
      .catch(() => setSchool(null))
      .finally(() => setLoading(false));
  }, [id]);

  /** Handle keyboard navigation for tabs (arrow keys). */
  function handleTabKeyDown(e: React.KeyboardEvent, tabIndex: number) {
    const tabs = visibleTabs;
    let nextIndex = tabIndex;
    if (e.key === "ArrowRight") {
      nextIndex = (tabIndex + 1) % tabs.length;
    } else if (e.key === "ArrowLeft") {
      nextIndex = (tabIndex - 1 + tabs.length) % tabs.length;
    } else if (e.key === "Home") {
      nextIndex = 0;
    } else if (e.key === "End") {
      nextIndex = tabs.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    switchTab(tabs[nextIndex]);
    const tabBtn = document.getElementById(`private-tab-${tabs[nextIndex]}`);
    tabBtn?.focus();
  }

  if (loading) {
    return <DetailSkeleton />;
  }

  if (!school) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
        <div className="flex flex-col items-center py-16 text-center animate-fade-in">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-private-50">
            <GraduationCap className="h-8 w-8 text-private-300" aria-hidden="true" />
          </div>
          <h1 className="mt-4 text-xl font-bold text-stone-900 sm:text-2xl">School not found</h1>
          <p className="mt-2 max-w-md text-sm text-stone-500">
            We couldn't find this school. It may have been removed or the link may be incorrect.
          </p>
          <Link
            to="/private-schools"
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-private-600 px-5 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:bg-private-700 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-private-500 focus:ring-offset-2"
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
  const firstDetail = details.length > 0 ? details[0] : null;
  const providesTransport = firstDetail?.provides_transport ?? null;
  const transportNotes = firstDetail?.transport_notes ?? null;
  const holidayNotes = firstDetail?.holiday_schedule_notes ?? null;

  // Fee range across all tiers
  const termlyFees = details.map((d) => d.termly_fee).filter((f): f is number => f != null);
  const feeMin = termlyFees.length > 0 ? Math.min(...termlyFees) : null;
  const feeMax = termlyFees.length > 0 ? Math.max(...termlyFees) : null;
  const feeIncreasePct = firstDetail?.fee_increase_pct ?? null;

  // Admissions data
  const bursaries = school.bursaries ?? [];
  const scholarships = school.scholarships ?? [];
  const entryAssessments = school.entry_assessments ?? [];
  const openDays = school.open_days ?? [];
  const siblingDiscounts = school.sibling_discounts ?? [];

  // Check if any detail has actual hidden cost data (not just base fees)
  const hasHiddenCostData = details.some(
    (d) =>
      d.lunches_per_term ||
      d.trips_per_term ||
      d.exam_fees_per_year ||
      d.textbooks_per_year ||
      d.music_tuition_per_term ||
      d.sports_per_term ||
      d.uniform_per_year ||
      d.registration_fee ||
      d.deposit_fee ||
      d.insurance_per_year ||
      d.building_fund_per_year
  );

  // Determine which tabs to show
  const visibleTabs = ALL_TABS.filter((tab) => {
    if (tab === "Overview") return true;
    if (tab === "Fees") return true; // Always show — has empty state
    if (tab === "Admissions") return true; // Always show — has empty state
    if (tab === "Hours & Transport") return true;
    if (tab === "True Cost") return hasHiddenCostData;
    return true;
  });

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8" role="main">
      {/* Breadcrumb navigation */}
      <nav className="mb-5 animate-fade-in" aria-label="Breadcrumb">
        <ol className="flex items-center gap-1.5 text-sm">
          <li>
            <Link to="/" className="text-stone-400 transition-colors hover:text-stone-600">
              Home
            </Link>
          </li>
          <ChevronRight className="h-3.5 w-3.5 text-stone-300" aria-hidden="true" />
          <li>
            <Link to="/private-schools" className="text-stone-400 transition-colors hover:text-stone-600">
              Private Schools
            </Link>
          </li>
          <ChevronRight className="h-3.5 w-3.5 text-stone-300" aria-hidden="true" />
          <li>
            <span className="font-medium text-stone-700" aria-current="page">
              {school.name}
            </span>
          </li>
        </ol>
      </nav>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 animate-fade-in">
        <div className="flex items-start gap-3">
          {/* School type icon */}
          <div className="mt-1 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-private-100 text-private-600">
            <GraduationCap className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">{school.name}</h1>
            <div className="mt-1 flex items-center gap-1.5 text-sm text-stone-600">
              <MapPin className="h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
              <span>{school.address}, {school.postcode}</span>
            </div>
            {school.ethos && (
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-stone-600">
                {school.ethos}
              </p>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-shrink-0 flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3.5 py-2 text-sm font-medium text-stone-700 transition-all duration-200 hover:border-stone-300 hover:shadow-sm active:scale-[0.98] min-h-[44px] min-w-[44px]"
            aria-label="Share this school"
          >
            <Share2 className="h-4 w-4 text-stone-500" aria-hidden="true" />
            <span className="hidden sm:inline">Share</span>
          </button>
          <Link
            to={`/compare?ids=${school.id}`}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-private-200 bg-private-50 px-3.5 py-2 text-sm font-medium text-private-700 transition-all duration-200 hover:bg-private-100 hover:border-private-300 active:scale-[0.98] min-h-[44px]"
          >
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            Add to comparison
          </Link>
          {school.website && (
            <a
              href={school.website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3.5 py-2 text-sm font-medium text-stone-700 transition-all duration-200 hover:border-stone-300 hover:shadow-sm min-h-[44px]"
            >
              <Globe className="h-4 w-4 text-private-500" aria-hidden="true" />
              School website
              <ExternalLink className="h-3 w-3 text-stone-400" aria-hidden="true" />
            </a>
          )}
        </div>
      </div>

      {/* Quick facts */}
      <div className="mt-4 flex flex-wrap gap-2 text-sm animate-fade-in" aria-label="School quick facts">
        <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-700">
          Ages {school.age_range_from}&ndash;{school.age_range_to}
        </span>
        <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-700">
          {school.gender_policy}
        </span>
        <span className="inline-flex items-center rounded-full bg-private-50 px-3 py-1 font-medium text-private-700 ring-1 ring-private-600/20">
          Independent
        </span>
        {school.faith && (
          <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-700">{school.faith}</span>
        )}
        <span className="inline-flex items-center rounded-full bg-stone-100 px-3 py-1 text-stone-400 text-xs">
          URN: {school.urn}
        </span>
      </div>

      {/* Sticky fee summary banner — compact on mobile, expanded on desktop */}
      {feeMin != null && feeMax != null && (
        <div className="sticky top-14 z-20 -mx-4 mt-4 border-y border-private-200 bg-gradient-to-r from-private-50 to-indigo-50 px-3 py-2.5 sticky-header-blur sm:static sm:mx-0 sm:mt-6 sm:rounded-xl sm:border sm:py-4 sm:px-5">
          <div className="flex items-center justify-between gap-2 sm:gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-wider text-private-600 sm:text-xs">Termly fees</p>
              <p className="mt-0.5 truncate text-base font-bold text-private-900 sm:text-xl">
                {feeMin === feeMax
                  ? `${formatFee(feeMin)} / term`
                  : `${formatFee(feeMin)} \u2013 ${formatFee(feeMax)}`}
              </p>
              {/* Show "per term" label on a separate line on mobile for space */}
              {feeMin !== feeMax && (
                <p className="text-[10px] text-private-600 sm:hidden">per term</p>
              )}
            </div>
            <div className="flex flex-shrink-0 items-center gap-2 sm:gap-3">
              {feeIncreasePct != null && (
                <div className="rounded-lg bg-white/70 px-2 py-1 text-right sm:px-3 sm:py-1.5">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-private-600 hidden sm:block">Est. increase</p>
                  <p className="text-xs font-semibold text-private-900 sm:text-sm">
                    <span className="sm:hidden">+</span>~{feeIncreasePct}%<span className="hidden sm:inline">/yr</span>
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab navigation */}
      <div className="relative mt-6">
        <div className="border-b border-stone-200">
          <nav
            className="-mb-px flex overflow-x-auto scrollbar-hide sm:scrollbar-thin"
            role="tablist"
            aria-label="School information sections"
          >
            {visibleTabs.map((tab, idx) => (
              <button
                key={tab}
                id={`private-tab-${tab}`}
                role="tab"
                aria-selected={activeTab === tab}
                aria-controls={`private-tabpanel-${tab}`}
                tabIndex={activeTab === tab ? 0 : -1}
                onClick={() => switchTab(tab)}
                onKeyDown={(e) => handleTabKeyDown(e, idx)}
                className={`flex-shrink-0 whitespace-nowrap border-b-2 px-3.5 py-3 text-sm font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-private-500 sm:px-4 ${
                  activeTab === tab
                    ? "border-private-600 text-private-700"
                    : "border-transparent text-stone-500 hover:border-stone-300 hover:text-stone-700"
                }`}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>
        {/* Right-edge fade for scrollable tabs on mobile */}
        <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-stone-50 to-transparent sm:hidden" aria-hidden="true" />
      </div>

      {/* Tab content */}
      <div
        className={`mt-6 ${
          tabDirection === "left"
            ? "animate-tab-slide-left"
            : tabDirection === "right"
              ? "animate-tab-slide-right"
              : "animate-tab-slide-in"
        }`}
        id={`private-tabpanel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`private-tab-${activeTab}`}
        key={activeTab}
      >
        {/* ============================================================ */}
        {/* OVERVIEW TAB                                                   */}
        {/* ============================================================ */}
        {activeTab === "Overview" && (
          <div className="space-y-6">
            {/* Quick links */}
            {school.website && (
              <div className="flex flex-wrap gap-3">
                <a
                  href={school.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 shadow-sm transition-all duration-200 hover:border-stone-300 hover:shadow-md"
                >
                  <Globe className="h-4 w-4 text-private-500" aria-hidden="true" />
                  School website
                  <ExternalLink className="h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
                </a>
              </div>
            )}

            <div className="grid gap-6 lg:grid-cols-2">
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

            {/* Holiday Schedule (shown in Overview since it's general info) */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <Calendar className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Holiday Schedule</h2>
              </div>
              <p className="mt-1 ml-7.5 text-sm text-stone-500">
                Private schools often have different term dates from state schools.
              </p>
              {holidayNotes ? (
                <p className="mt-4 text-sm leading-relaxed text-stone-600">{holidayNotes}</p>
              ) : (
                <div className="mt-4">
                  <NoData
                    icon={Calendar}
                    title="No holiday schedule data available"
                    description="Check the school's website for published term dates."
                  />
                </div>
              )}
            </section>
          </div>
        )}

        {/* ============================================================ */}
        {/* FEES TAB                                                       */}
        {/* ============================================================ */}
        {activeTab === "Fees" && (
          <div className="space-y-6">
            {/* Fee Breakdown */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <PoundSterling className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Fee Breakdown</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Fees by age group, shown per term and per year.
              </p>
              {details.length > 0 ? (
                <div className="mt-5 divide-y divide-stone-100">
                  {details.map((d) => (
                    <div
                      key={d.id}
                      className="flex items-center justify-between py-3.5 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        <span className="inline-block h-2 w-2 rounded-full bg-private-400" aria-hidden="true" />
                        <span className="font-medium text-stone-700">
                          {d.fee_age_group ?? "General"}
                        </span>
                      </div>
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
                <div className="mt-5">
                  <NoData
                    icon={PoundSterling}
                    title="No fee data available"
                    description="Fee information for this school has not been collected yet. Check the school's website for the latest fees."
                  />
                </div>
              )}
            </section>

            {/* Fee increase note */}
            {feeIncreasePct != null && (
              <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/50 p-4 text-sm">
                <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-500" aria-hidden="true" />
                <div>
                  <p className="font-medium text-amber-900">Annual fee increase</p>
                  <p className="mt-0.5 text-amber-800">
                    Fees at this school have typically increased by approximately <strong>{feeIncreasePct}%</strong> per year.
                    Factor this into your long-term budget planning.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* HOURS & TRANSPORT TAB                                          */}
        {/* ============================================================ */}
        {activeTab === "Hours & Transport" && (
          <div className="space-y-6">
            {/* School Hours */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <Clock className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">School Hours</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Daily start and end times for the school day.
              </p>
              {firstDetail && (firstDetail.school_day_start || firstDetail.school_day_end) ? (
                <div className="mt-5 grid grid-cols-2 gap-4">
                  <div className="rounded-xl bg-green-50 border border-green-200 p-5 text-center transition-shadow hover:shadow-sm">
                    <p className="text-xs font-medium uppercase tracking-wider text-green-700">Start</p>
                    <p className="mt-1.5 text-2xl font-bold text-green-900">
                      {formatTime(firstDetail.school_day_start)}
                    </p>
                  </div>
                  <div className="rounded-xl bg-amber-50 border border-amber-200 p-5 text-center transition-shadow hover:shadow-sm">
                    <p className="text-xs font-medium uppercase tracking-wider text-amber-700">End</p>
                    <p className="mt-1.5 text-2xl font-bold text-amber-900">
                      {formatTime(firstDetail.school_day_end)}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="mt-5">
                  <NoData
                    icon={Clock}
                    title="No hours data available"
                    description="School hours have not been collected yet."
                  />
                </div>
              )}
            </section>

            {/* Transport */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <Bus className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Transport</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                School transport availability and details.
              </p>
              {providesTransport != null ? (
                <div className="mt-5 space-y-3">
                  <div className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium ${
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
                <div className="mt-5">
                  <NoData
                    icon={Bus}
                    title="No transport data available"
                    description="Transport information has not been collected yet."
                  />
                </div>
              )}
            </section>
          </div>
        )}

        {/* ============================================================ */}
        {/* ADMISSIONS TAB                                                  */}
        {/* ============================================================ */}
        {activeTab === "Admissions" && (
          <div className="space-y-6">
            {/* Bursaries */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <BookOpen className="h-5 w-5 text-amber-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Bursaries</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Means-tested financial assistance to reduce fees.
              </p>
              {bursaries.length > 0 ? (
                <div className="mt-5 space-y-4">
                  {bursaries.map((b) => (
                    <div key={b.id} className="rounded-lg bg-amber-50/50 border border-amber-100 p-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-stone-900">
                          Up to {b.max_percentage}% fee reduction
                        </span>
                        {b.application_deadline && (
                          <span className="text-xs text-amber-700">
                            Deadline: {new Date(b.application_deadline).toLocaleDateString("en-GB")}
                          </span>
                        )}
                      </div>
                      {b.eligibility_notes && (
                        <p className="mt-2 text-sm text-stone-600">{b.eligibility_notes}</p>
                      )}
                      {b.income_threshold && (
                        <p className="mt-1 text-xs text-stone-500">
                          Income threshold: {formatFee(b.income_threshold)}
                        </p>
                      )}
                      {b.percentage_of_pupils != null && (
                        <p className="mt-1 text-xs text-stone-500">
                          {b.percentage_of_pupils}% of pupils receive bursary support
                        </p>
                      )}
                      {b.notes && <p className="mt-2 text-xs text-stone-500 italic">{b.notes}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-5">
                  <NoData
                    icon={BookOpen}
                    title="No bursary data available"
                    description="Bursary information has not been collected yet. Contact the school directly for means-tested fee assistance."
                  />
                </div>
              )}
            </section>

            {/* Scholarships */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <Award className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Scholarships</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Merit-based awards for academic, music, sport, or other talents.
              </p>
              {scholarships.length > 0 ? (
                <div className="mt-5 divide-y divide-stone-100">
                  {scholarships.map((s) => (
                    <div key={s.id} className="py-3.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex rounded-full bg-private-50 px-2.5 py-0.5 text-xs font-medium text-private-700 ring-1 ring-private-600/20 capitalize">
                            {s.scholarship_type}
                          </span>
                          {s.value_description && (
                            <span className="text-sm font-medium text-stone-900">
                              {s.value_description}
                            </span>
                          )}
                        </div>
                        {s.entry_points && (
                          <span className="text-xs text-stone-500">Entry: {s.entry_points}</span>
                        )}
                      </div>
                      {s.assessment_method && (
                        <p className="mt-1.5 text-sm text-stone-600">{s.assessment_method}</p>
                      )}
                      {s.application_deadline && (
                        <p className="mt-1 text-xs text-stone-500">
                          Deadline: {new Date(s.application_deadline).toLocaleDateString("en-GB")}
                        </p>
                      )}
                      {s.notes && <p className="mt-1 text-xs text-stone-500 italic">{s.notes}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-5">
                  <NoData
                    icon={Award}
                    title="No scholarship data available"
                    description="Scholarship information has not been collected yet. Check the school's website for available awards."
                  />
                </div>
              )}
            </section>

            {/* Entry Assessments */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <ClipboardCheck className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Entry Assessments</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                What to expect at each entry point.
              </p>
              {entryAssessments.length > 0 ? (
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  {entryAssessments.map((ea) => (
                    <div key={ea.id} className="rounded-lg border border-stone-200 p-4 transition-shadow hover:shadow-sm">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-private-100 text-sm font-bold text-private-700">
                          {ea.entry_point}
                        </span>
                        <span className="text-sm font-medium text-stone-900">
                          Entry at {ea.entry_point}
                        </span>
                      </div>
                      {ea.assessment_type && (
                        <p className="mt-2 text-sm text-stone-600">{ea.assessment_type}</p>
                      )}
                      {ea.subjects_tested && (
                        <p className="mt-1 text-xs text-stone-500">Subjects: {ea.subjects_tested}</p>
                      )}
                      <div className="mt-2 space-y-0.5 text-xs text-stone-500">
                        {ea.registration_deadline && (
                          <p>Registration deadline: {new Date(ea.registration_deadline).toLocaleDateString("en-GB")}</p>
                        )}
                        {ea.assessment_date && (
                          <p>Assessment date: {new Date(ea.assessment_date).toLocaleDateString("en-GB")}</p>
                        )}
                        {ea.offer_date && (
                          <p>Offers by: {new Date(ea.offer_date).toLocaleDateString("en-GB")}</p>
                        )}
                        {ea.registration_fee != null && (
                          <p>Registration fee: {formatFee(ea.registration_fee)}</p>
                        )}
                      </div>
                      {ea.notes && <p className="mt-2 text-xs text-stone-500 italic">{ea.notes}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-5">
                  <NoData
                    icon={ClipboardCheck}
                    title="No entry assessment data available"
                    description="Entry assessment details have not been collected yet. Contact the admissions office for assessment requirements."
                  />
                </div>
              )}
            </section>

            {/* Open Days */}
            <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
              <div className="flex items-center gap-2.5">
                <CalendarDays className="h-5 w-5 text-private-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-stone-900">Open Days</h2>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Upcoming events where you can visit the school.
              </p>
              {openDays.length > 0 ? (
                <div className="mt-5 space-y-3">
                  {openDays.map((od) => (
                    <div key={od.id} className="flex items-center justify-between rounded-lg border border-stone-200 p-4 transition-shadow hover:shadow-sm">
                      <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 flex-shrink-0 flex-col items-center justify-center rounded-lg bg-private-50 text-private-700">
                          <span className="text-xs font-medium uppercase">
                            {new Date(od.event_date).toLocaleDateString("en-GB", { month: "short" })}
                          </span>
                          <span className="text-lg font-bold leading-tight">
                            {new Date(od.event_date).getDate()}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-stone-900">{od.event_type}</p>
                          {od.event_time && (
                            <p className="text-xs text-stone-500">{od.event_time}</p>
                          )}
                          {od.description && (
                            <p className="mt-0.5 text-xs text-stone-500">{od.description}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {od.registration_required && (
                          <span className="text-xs text-amber-700">Booking required</span>
                        )}
                        {od.booking_url && (
                          <a
                            href={od.booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-lg bg-private-600 px-3 py-1.5 text-xs font-medium text-white transition-all duration-200 hover:bg-private-700"
                          >
                            Book
                            <ExternalLink className="h-3 w-3" aria-hidden="true" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-5">
                  <NoData
                    icon={CalendarDays}
                    title="No upcoming open days listed"
                    description="Open day information has not been collected yet. Check the school's website for upcoming visit opportunities."
                  />
                </div>
              )}
            </section>

            {/* Sibling Discounts */}
            {siblingDiscounts.length > 0 && (
              <section className="rounded-xl border border-stone-200 bg-white p-5 sm:p-6">
                <div className="flex items-center gap-2.5">
                  <Users className="h-5 w-5 text-private-500" aria-hidden="true" />
                  <h2 className="text-lg font-semibold text-stone-900">Sibling Discounts</h2>
                </div>
                <div className="mt-5 space-y-3">
                  {siblingDiscounts.map((sd) => (
                    <div key={sd.id} className="rounded-lg bg-green-50/50 border border-green-100 p-4">
                      <div className="flex flex-wrap gap-3">
                        {sd.second_child_percent != null && (
                          <div className="text-center">
                            <p className="text-xs text-stone-500">2nd child</p>
                            <p className="text-lg font-bold text-green-700">{sd.second_child_percent}%</p>
                          </div>
                        )}
                        {sd.third_child_percent != null && (
                          <div className="text-center">
                            <p className="text-xs text-stone-500">3rd child</p>
                            <p className="text-lg font-bold text-green-700">{sd.third_child_percent}%</p>
                          </div>
                        )}
                        {sd.fourth_child_percent != null && (
                          <div className="text-center">
                            <p className="text-xs text-stone-500">4th child</p>
                            <p className="text-lg font-bold text-green-700">{sd.fourth_child_percent}%</p>
                          </div>
                        )}
                      </div>
                      {sd.conditions && (
                        <p className="mt-2 text-sm text-stone-600">{sd.conditions}</p>
                      )}
                      {sd.stacks_with_bursary != null && (
                        <p className="mt-1 text-xs text-stone-500">
                          {sd.stacks_with_bursary
                            ? "Can be combined with bursaries"
                            : "Cannot be combined with bursaries"}
                        </p>
                      )}
                      {sd.notes && <p className="mt-1 text-xs text-stone-500 italic">{sd.notes}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* TRUE COST TAB                                                  */}
        {/* ============================================================ */}
        {activeTab === "True Cost" && details.length > 0 && (
          <div className="space-y-6">
            {/* Explainer */}
            <div className="flex items-start gap-3 rounded-xl border border-orange-200 bg-orange-50/50 p-5">
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

            {/* Cost cards */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {details.map((detail) => {
                const costs = calculateTrueAnnualCost(detail);
                return (
                  <div
                    key={detail.id}
                    className="rounded-xl border border-stone-200 bg-white p-5 transition-shadow duration-200 hover:shadow-md"
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

                    {/* True annual cost — highlight */}
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
                      <details className="mt-3 border-t border-stone-200 pt-3 group">
                        <summary className="flex cursor-pointer items-center justify-between text-xs font-medium text-stone-600 hover:text-stone-900 transition-colors">
                          <span>Optional extras</span>
                          <span className="font-medium text-stone-700">
                            +{formatFee(costs.optional)}
                          </span>
                        </summary>
                        <div className="mt-2 space-y-1 text-xs text-stone-500 animate-fade-in">
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
              <p className="text-xs text-stone-600 italic">
                {firstDetail.hidden_costs_notes}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Share toast notification */}
      {shareToast && (
        <div
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 share-toast"
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center gap-2 rounded-full bg-stone-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
            <Check className="h-4 w-4 text-green-400" aria-hidden="true" />
            Link copied to clipboard
          </div>
        </div>
      )}
    </main>
  );
}
