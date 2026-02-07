import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  SlidersHorizontal,
  Star,
  ChevronDown,
  ChevronRight,
  Plus,
  Minus,
  FileDown,
  Scale,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { get, post } from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ComponentScores {
  distance: number;
  ofsted: number;
  clubs: number;
  fees: number;
  ofsted_trajectory: number;
  attendance: number;
  class_size: number;
  parking: number;
  holiday_club: number;
  uniform: number;
  diversity: number;
  sibling_priority: number;
  school_run_ease: number;
  homework: number;
}

interface ScoredSchool {
  school_id: number;
  school_name: string;
  composite_score: number;
  component_scores: ComponentScores;
  ofsted_rating: string | null;
  distance_km: number | null;
  is_private: boolean;
  has_breakfast_club: boolean;
  has_afterschool_club: boolean;
  annual_fee: number | null;
  postcode: string | null;
  school_type: string | null;
  faith: string | null;
  age_range_from: number | null;
  age_range_to: number | null;
  gender_policy: string | null;
}

interface DecisionScoreResponse {
  schools: ScoredSchool[];
  weights_used: Record<string, number>;
}

interface ProsConsResponse {
  school_id: number;
  school_name: string;
  pros: string[];
  cons: string[];
}

interface SchoolListItem {
  id: number;
  name: string;
}

interface WhatIfFilters {
  okWith15MinDrive: boolean;
  dropMinOfstedToGood: boolean;
  includeFaith: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = "school-finder-shortlist";
const OFSTED_COLORS: Record<string, string> = {
  Outstanding: "bg-green-100 text-green-800 ring-1 ring-green-600/20",
  Good: "bg-blue-100 text-blue-800 ring-1 ring-blue-600/20",
  "Requires Improvement": "bg-amber-100 text-amber-800 ring-1 ring-amber-600/20",
  Inadequate: "bg-red-100 text-red-800 ring-1 ring-red-600/20",
};

// ---------------------------------------------------------------------------
// Shortlist helpers
// ---------------------------------------------------------------------------

function loadShortlist(): number[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as number[];
  } catch {
    /* ignore corrupt data */
  }
  return [];
}

function saveShortlist(ids: number[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type WeightKey =
  | "distance"
  | "ofsted"
  | "clubs"
  | "fees"
  | "ofsted_trajectory"
  | "attendance"
  | "class_size"
  | "parking"
  | "holiday_club"
  | "uniform"
  | "diversity"
  | "sibling_priority"
  | "school_run_ease"
  | "homework";

type Weights = Record<WeightKey, number>;

interface WeightConfig {
  key: WeightKey;
  label: string;
  description: string;
  isAdvanced: boolean;
}

const WEIGHT_CONFIGS: WeightConfig[] = [
  {
    key: "distance",
    label: "Distance from home",
    description: "Closer schools score higher",
    isAdvanced: false,
  },
  {
    key: "ofsted",
    label: "Ofsted rating",
    description: "Based on latest inspection result",
    isAdvanced: false,
  },
  {
    key: "clubs",
    label: "Clubs and wraparound care",
    description: "Breakfast and after-school club availability",
    isAdvanced: false,
  },
  {
    key: "fees",
    label: "Fees and value",
    description: "Annual fees for private schools (state schools score highest)",
    isAdvanced: false,
  },
  {
    key: "school_run_ease",
    label: "School run ease",
    description: "Journey time and convenience of the commute",
    isAdvanced: true,
  },
  {
    key: "ofsted_trajectory",
    label: "Ofsted trajectory",
    description: "Whether the school is improving, stable, or declining",
    isAdvanced: true,
  },
  {
    key: "attendance",
    label: "Attendance rate",
    description: "Higher attendance rates score better",
    isAdvanced: true,
  },
  {
    key: "class_size",
    label: "Class size",
    description: "Smaller class sizes score better",
    isAdvanced: true,
  },
  {
    key: "parking",
    label: "Drop-off and parking ease",
    description: "Less chaos at the school gate scores better",
    isAdvanced: true,
  },
  {
    key: "holiday_club",
    label: "Holiday club on-site",
    description: "Whether holiday provision is available",
    isAdvanced: true,
  },
  {
    key: "uniform",
    label: "Uniform affordability",
    description: "Lower uniform costs score better",
    isAdvanced: true,
  },
  {
    key: "diversity",
    label: "Demographic diversity",
    description: "Diversity of the school community",
    isAdvanced: true,
  },
  {
    key: "sibling_priority",
    label: "Sibling priority",
    description: "Likelihood of siblings getting a place",
    isAdvanced: true,
  },
  {
    key: "homework",
    label: "Homework load",
    description: "Less homework scores better for those who prefer it",
    isAdvanced: true,
  },
];

const DEFAULT_WEIGHTS: Weights = {
  distance: 30,
  ofsted: 30,
  clubs: 20,
  fees: 20,
  ofsted_trajectory: 0,
  attendance: 0,
  class_size: 0,
  parking: 0,
  holiday_club: 0,
  uniform: 0,
  diversity: 0,
  sibling_priority: 0,
  school_run_ease: 0,
  homework: 0,
};

/** Human-readable component score labels for expanded school detail. */
const COMPONENT_LABELS: [keyof ComponentScores, string][] = [
  ["distance", "Distance"],
  ["ofsted", "Ofsted"],
  ["clubs", "Clubs"],
  ["fees", "Fees"],
  ["ofsted_trajectory", "Trajectory"],
  ["attendance", "Attendance"],
  ["class_size", "Class Size"],
  ["parking", "Parking"],
  ["holiday_club", "Holiday Club"],
  ["uniform", "Uniform"],
  ["diversity", "Diversity"],
  ["sibling_priority", "Sibling"],
  ["school_run_ease", "School Run"],
  ["homework", "Homework"],
];

export default function DecisionSupport() {
  const [searchParams] = useSearchParams();
  const council = searchParams.get("council") || "Milton Keynes";

  // --- State ---
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [allSchools, setAllSchools] = useState<SchoolListItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [rankedSchools, setRankedSchools] = useState<ScoredSchool[]>([]);
  const [prosConsMap, setProsConsMap] = useState<
    Record<number, ProsConsResponse>
  >({});
  const [expandedSchoolId, setExpandedSchoolId] = useState<number | null>(null);
  const [shortlist, setShortlist] = useState<number[]>(loadShortlist);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [schoolSearch, setSchoolSearch] = useState("");

  const [whatIf, setWhatIf] = useState<WhatIfFilters>({
    okWith15MinDrive: false,
    dropMinOfstedToGood: false,
    includeFaith: false,
  });

  // --- Load school list on mount ---
  useEffect(() => {
    get<SchoolListItem[]>("/schools", { council })
      .then((data) => {
        setAllSchools(data);
        // Pre-select the first 10 (or all if less)
        const initial = data.slice(0, 10).map((s) => s.id);
        setSelectedIds(initial);
      })
      .catch(() => setError("Could not load the list of schools. Please refresh to try again."));
  }, [council]);

  // --- Fetch scores when selectedIds or weights change ---
  const fetchScores = useCallback(async () => {
    if (selectedIds.length === 0) {
      setRankedSchools([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Normalise weights to 0-1 scale for the API
      const total = Object.values(weights).reduce((a, b) => a + b, 0);
      const normWeights =
        total > 0
          ? Object.fromEntries(
              Object.entries(weights).map(([k, v]) => [k, v / total]),
            )
          : weights;

      const weightsStr = Object.entries(normWeights)
        .map(([k, v]) => `${k}:${v.toFixed(3)}`)
        .join(",");

      if (whatIf.okWith15MinDrive || whatIf.dropMinOfstedToGood || !whatIf.includeFaith) {
        // Use what-if endpoint
        const body = {
          school_ids: selectedIds,
          weights: normWeights,
          max_distance_km: whatIf.okWith15MinDrive ? 15 : undefined,
          min_rating: whatIf.dropMinOfstedToGood ? "Good" : undefined,
          include_faith: whatIf.includeFaith ? true : undefined,
        };
        const data = await post<DecisionScoreResponse>(
          "/decision/what-if",
          body,
        );
        setRankedSchools(data.schools);
      } else {
        const data = await get<DecisionScoreResponse>("/decision/score", {
          school_ids: selectedIds.join(","),
          weights: weightsStr,
        });
        setRankedSchools(data.schools);
      }
    } catch {
      setError("Something went wrong while scoring schools. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [selectedIds, weights, whatIf]);

  useEffect(() => {
    fetchScores();
  }, [fetchScores]);

  // --- Fetch pros/cons when a school is expanded ---
  async function fetchProsCons(schoolId: number) {
    if (prosConsMap[schoolId]) return;
    try {
      const data = await get<ProsConsResponse>("/decision/pros-cons", {
        school_id: schoolId,
      });
      setProsConsMap((prev) => ({ ...prev, [schoolId]: data }));
    } catch {
      /* ignore */
    }
  }

  function handleExpand(schoolId: number) {
    if (expandedSchoolId === schoolId) {
      setExpandedSchoolId(null);
    } else {
      setExpandedSchoolId(schoolId);
      fetchProsCons(schoolId);
    }
  }

  // --- Shortlist ---
  function toggleShortlist(schoolId: number) {
    setShortlist((prev) => {
      const next = prev.includes(schoolId)
        ? prev.filter((id) => id !== schoolId)
        : [...prev, schoolId];
      saveShortlist(next);
      return next;
    });
  }

  function removeFromShortlist(schoolId: number) {
    setShortlist((prev) => {
      const next = prev.filter((id) => id !== schoolId);
      saveShortlist(next);
      return next;
    });
  }

  // --- School selection ---
  function toggleSchoolSelection(schoolId: number) {
    setSelectedIds((prev) =>
      prev.includes(schoolId)
        ? prev.filter((id) => id !== schoolId)
        : [...prev, schoolId],
    );
  }

  function selectAllSchools() {
    setSelectedIds(allSchools.map((s) => s.id));
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  // --- Export ---
  function handleExportPdf() {
    window.print();
  }

  // --- Weight change ---
  function handleWeightChange(key: WeightKey, value: number) {
    setWeights((prev) => ({ ...prev, [key]: value }));
  }

  // --- School search filter ---
  const filteredAllSchools = schoolSearch.trim()
    ? allSchools.filter((s) =>
        s.name.toLowerCase().includes(schoolSearch.toLowerCase()),
      )
    : allSchools;

  // --- Which component scores are non-zero-weighted ---
  const activeWeightKeys = (Object.entries(weights) as [WeightKey, number][])
    .filter(([, v]) => v > 0)
    .map(([k]) => k);

  const visibleComponentLabels =
    activeWeightKeys.length > 0
      ? COMPONENT_LABELS.filter(([key]) => activeWeightKeys.includes(key))
      : COMPONENT_LABELS.slice(0, 4); // fallback to top 4

  // --- Render ---
  const shortlistedSchools = rankedSchools.filter((s) =>
    shortlist.includes(s.school_id),
  );

  const corePriorities = WEIGHT_CONFIGS.filter((w) => !w.isAdvanced);
  const advancedPriorities = WEIGHT_CONFIGS.filter((w) => w.isAdvanced);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8 print:px-0" role="main">
      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 sm:h-12 sm:w-12">
          <Scale className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden="true" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">
            Help me decide
          </h1>
          <p className="mt-1 text-sm leading-relaxed text-stone-600 sm:text-base">
            Tell us what matters most to your family, and we will rank schools
            by a personalised score. Explore "what if" scenarios and build a
            shortlist.
          </p>
        </div>
      </div>

      {error && (
        <div
          className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 sm:mt-8 sm:gap-8 lg:grid-cols-12">
        {/* ---- Left column: controls ---- */}
        <aside className="space-y-4 sm:space-y-5 lg:col-span-4 print:hidden" aria-label="Decision support controls">
          {/* School selector */}
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-600" aria-hidden="true" />
              <h2 className="text-base font-semibold text-stone-900">
                Schools to rank
              </h2>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-stone-500">
              Pick which schools to include in scoring. All are selected by
              default.
            </p>

            {/* Quick actions */}
            <div className="mt-3 flex gap-2">
              <button
                onClick={selectAllSchools}
                className="rounded-lg px-3 py-2 text-xs font-medium text-stone-700 transition-colors hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                Select all
              </button>
              <button
                onClick={clearSelection}
                className="rounded-lg px-3 py-2 text-xs font-medium text-stone-700 transition-colors hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                Clear all
              </button>
            </div>

            {/* Search */}
            <div className="mt-2">
              <input
                type="text"
                placeholder="Search schools..."
                value={schoolSearch}
                onChange={(e) => setSchoolSearch(e.target.value)}
                aria-label="Filter school list"
                className="block w-full rounded-lg border border-stone-300 px-3 py-2 text-sm shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>

            {/* School list */}
            <div className="mt-2 max-h-48 space-y-0.5 overflow-y-auto rounded-lg border border-stone-100 p-1">
              {filteredAllSchools.map((school) => (
                <label
                  key={school.id}
                  className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm text-stone-700 transition-colors hover:bg-stone-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(school.id)}
                    onChange={() => toggleSchoolSelection(school.id)}
                    className="h-4 w-4 flex-shrink-0 rounded border-stone-300 text-brand-600 focus:ring-brand-500"
                  />
                  <span className="truncate">{school.name}</span>
                </label>
              ))}
              {allSchools.length === 0 && (
                <div className="flex items-center justify-center py-6 text-xs text-stone-400">
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  Loading schools...
                </div>
              )}
              {allSchools.length > 0 && filteredAllSchools.length === 0 && (
                <p className="py-4 text-center text-xs text-stone-400">
                  No schools match your search
                </p>
              )}
            </div>
            {selectedIds.length > 0 && (
              <p className="mt-2 text-xs text-stone-500">
                {selectedIds.length} school{selectedIds.length !== 1 ? "s" : ""} selected
              </p>
            )}
          </section>

          {/* Priority sliders */}
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-brand-600" aria-hidden="true" />
              <h2 className="text-base font-semibold text-stone-900">
                Your priorities
              </h2>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-stone-500">
              Drag the sliders to reflect what matters most to your family.
              Weights are balanced automatically.
            </p>

            {/* Core priorities - always visible */}
            <div className="mt-4 space-y-5">
              {corePriorities.map(({ key, label, description }) => (
                <div key={key}>
                  <div className="flex items-baseline justify-between">
                    <label
                      htmlFor={`w-${key}`}
                      className="text-sm font-medium text-stone-700"
                    >
                      {label}
                    </label>
                    <span className="ml-2 min-w-[2.5rem] text-right text-sm tabular-nums text-stone-500">
                      {weights[key]}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-stone-400">{description}</p>
                  <input
                    id={`w-${key}`}
                    type="range"
                    min={0}
                    max={100}
                    value={weights[key]}
                    onChange={(e) =>
                      handleWeightChange(key, Number(e.target.value))
                    }
                    aria-label={`${label} importance: ${weights[key]} out of 100`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={weights[key]}
                    className="mt-1.5 h-2 w-full cursor-pointer appearance-none rounded-full bg-stone-200 accent-[#0d9488] [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5"
                  />
                </div>
              ))}
            </div>

            {/* Advanced priorities - progressive disclosure */}
            <div className="mt-5 border-t border-stone-100 pt-4">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex w-full min-h-[44px] items-center justify-between text-sm font-medium text-stone-600 transition-colors hover:text-stone-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 rounded-lg px-1"
                aria-expanded={showAdvanced}
              >
                <span>More factors</span>
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`}
                  aria-hidden="true"
                />
              </button>

              {showAdvanced && (
                <div className="mt-3 space-y-5">
                  {advancedPriorities.map(({ key, label, description }) => (
                    <div key={key}>
                      <div className="flex items-baseline justify-between">
                        <label
                          htmlFor={`w-${key}`}
                          className="text-sm font-medium text-stone-700"
                        >
                          {label}
                        </label>
                        <span className="ml-2 min-w-[2.5rem] text-right text-sm tabular-nums text-stone-500">
                          {weights[key]}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-stone-400">
                        {description}
                      </p>
                      <input
                        id={`w-${key}`}
                        type="range"
                        min={0}
                        max={100}
                        value={weights[key]}
                        onChange={(e) =>
                          handleWeightChange(key, Number(e.target.value))
                        }
                        aria-label={`${label} importance: ${weights[key]} out of 100`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={weights[key]}
                        className="mt-1.5 h-2 w-full cursor-pointer appearance-none rounded-full bg-stone-200 accent-[#0d9488] [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* What-if controls */}
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-stone-900">
              "What if" scenarios
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-stone-500">
              Toggle these to explore how your rankings change under different
              assumptions.
            </p>
            <div className="mt-4 space-y-1">
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm text-stone-700 transition-colors hover:bg-stone-50">
                <input
                  type="checkbox"
                  checked={whatIf.okWith15MinDrive}
                  onChange={(e) =>
                    setWhatIf((p) => ({
                      ...p,
                      okWith15MinDrive: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 flex-shrink-0 rounded border-stone-300 text-brand-600 focus:ring-brand-500"
                />
                <span>
                  I am happy with up to a 15 km drive
                </span>
              </label>
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm text-stone-700 transition-colors hover:bg-stone-50">
                <input
                  type="checkbox"
                  checked={whatIf.dropMinOfstedToGood}
                  onChange={(e) =>
                    setWhatIf((p) => ({
                      ...p,
                      dropMinOfstedToGood: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 flex-shrink-0 rounded border-stone-300 text-brand-600 focus:ring-brand-500"
                />
                <span>
                  A "Good" Ofsted rating is fine
                </span>
              </label>
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm text-stone-700 transition-colors hover:bg-stone-50">
                <input
                  type="checkbox"
                  checked={whatIf.includeFaith}
                  onChange={(e) =>
                    setWhatIf((p) => ({
                      ...p,
                      includeFaith: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 flex-shrink-0 rounded border-stone-300 text-brand-600 focus:ring-brand-500"
                />
                <span>Include faith schools</span>
              </label>
            </div>
          </section>
        </aside>

        {/* ---- Right column: results ---- */}
        <div className="space-y-6 lg:col-span-8">
          {/* Ranked list */}
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-stone-900">
                  Your ranked schools
                </h2>
                <p className="mt-0.5 text-xs leading-relaxed text-stone-500">
                  {rankedSchools.length} school{rankedSchools.length !== 1 ? "s" : ""}{" "}
                  ranked by your personalised score. Tap a school to see the
                  breakdown.
                </p>
              </div>
              {loading && (
                <div className="flex items-center gap-1.5 text-xs text-brand-600">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  <span>Updating</span>
                </div>
              )}
            </div>

            {rankedSchools.length === 0 && !loading ? (
              <div className="mt-6 rounded-xl border-2 border-dashed border-stone-200 px-6 py-10 text-center">
                <SlidersHorizontal className="mx-auto h-8 w-8 text-stone-300" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-stone-600">
                  {selectedIds.length === 0
                    ? "Select schools to get started"
                    : "No schools match your current filters"}
                </p>
                <p className="mt-1 text-xs text-stone-400">
                  {selectedIds.length === 0
                    ? "Use the school selector on the left to pick schools to rank."
                    : "Try adjusting your \"what if\" settings or selecting more schools."}
                </p>
              </div>
            ) : (
              <ul className="mt-4 divide-y divide-stone-100" role="list">
                {rankedSchools.map((school, idx) => {
                  const isExpanded = expandedSchoolId === school.school_id;
                  const pc = prosConsMap[school.school_id];
                  const isShortlisted = shortlist.includes(school.school_id);
                  const ratingColor =
                    OFSTED_COLORS[school.ofsted_rating ?? ""] ??
                    "bg-stone-100 text-stone-600";

                  return (
                    <li key={school.school_id} className="py-3 first:pt-0 last:pb-0">
                      {/* Main row */}
                      <button
                        onClick={() => handleExpand(school.school_id)}
                        className="w-full min-h-[56px] rounded-lg px-2 py-1 text-left transition-colors hover:bg-stone-50 focus:outline-none focus:ring-2 focus:ring-brand-500"
                        aria-expanded={isExpanded}
                        aria-label={`${school.school_name}, ranked ${idx + 1}, score ${school.composite_score.toFixed(1)}. Click to ${isExpanded ? "collapse" : "expand"} details.`}
                      >
                        <div className="flex items-start gap-3">
                          {/* Rank badge */}
                          <span
                            className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                              idx === 0
                                ? "bg-brand-600 text-white"
                                : idx === 1
                                  ? "bg-brand-100 text-brand-700"
                                  : idx === 2
                                    ? "bg-brand-50 text-brand-600"
                                    : "bg-stone-100 text-stone-600"
                            }`}
                          >
                            {idx + 1}
                          </span>

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="truncate font-medium text-stone-900">
                                {school.school_name}
                              </span>
                              {school.ofsted_rating && (
                                <span
                                  className={`inline-flex flex-shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${ratingColor}`}
                                >
                                  {school.ofsted_rating}
                                </span>
                              )}
                              {isShortlisted && (
                                <Star className="h-3.5 w-3.5 flex-shrink-0 fill-yellow-400 text-yellow-400" aria-label="On your shortlist" />
                              )}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-500">
                              {school.distance_km != null && (
                                <span>{school.distance_km.toFixed(1)} km</span>
                              )}
                              {school.school_type && (
                                <span>{school.school_type}</span>
                              )}
                              {school.has_breakfast_club && (
                                <span className="text-orange-600">
                                  Breakfast club
                                </span>
                              )}
                              {school.has_afterschool_club && (
                                <span className="text-purple-600">
                                  After-school
                                </span>
                              )}
                              {school.is_private && school.annual_fee != null && (
                                <span className="text-stone-600">
                                  {"\u00A3"}
                                  {school.annual_fee.toLocaleString()}/yr
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Score bar + expand indicator */}
                          <div className="flex items-center gap-2">
                            <div className="flex w-24 flex-shrink-0 flex-col items-end sm:w-28">
                              <span className="text-sm font-bold text-stone-900">
                                {school.composite_score.toFixed(1)}
                              </span>
                              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-stone-200">
                                <div
                                  className="h-full rounded-full bg-brand-600 transition-all duration-300"
                                  style={{
                                    width: `${Math.min(school.composite_score, 100)}%`,
                                  }}
                                />
                              </div>
                            </div>
                            <ChevronRight
                              className={`h-4 w-4 flex-shrink-0 text-stone-400 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                              aria-hidden="true"
                            />
                          </div>
                        </div>
                      </button>

                      {/* Expanded: component scores + pros/cons */}
                      {isExpanded && (
                        <div className="ml-11 mt-3 space-y-4 rounded-lg border border-stone-100 bg-stone-50/50 p-4">
                          {/* Component score bars - only show weighted ones */}
                          <div>
                            <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                              Score breakdown
                            </h3>
                            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
                              {visibleComponentLabels.map(([key, label]) => (
                                <div key={key}>
                                  <div className="flex justify-between text-xs text-stone-500">
                                    <span>{label}</span>
                                    <span className="tabular-nums">
                                      {school.component_scores[key].toFixed(0)}
                                    </span>
                                  </div>
                                  <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-stone-200">
                                    <div
                                      className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                                      style={{
                                        width: `${Math.min(school.component_scores[key], 100)}%`,
                                      }}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Pros / Cons */}
                          {pc ? (
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                              <div className="rounded-lg bg-green-50 p-4">
                                <div className="flex items-center gap-1.5">
                                  <ThumbsUp className="h-3.5 w-3.5 text-green-700" aria-hidden="true" />
                                  <h4 className="text-xs font-semibold text-green-800">
                                    Strengths
                                  </h4>
                                </div>
                                {pc.pros.length > 0 ? (
                                  <ul className="mt-2 space-y-1.5">
                                    {pc.pros.map((p) => (
                                      <li key={p} className="flex items-start gap-1.5 text-xs text-green-700">
                                        <span className="mt-1 block h-1 w-1 flex-shrink-0 rounded-full bg-green-500" aria-hidden="true" />
                                        {p}
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="mt-2 text-xs text-green-600">
                                    No data available yet
                                  </p>
                                )}
                              </div>
                              <div className="rounded-lg bg-red-50 p-4">
                                <div className="flex items-center gap-1.5">
                                  <ThumbsDown className="h-3.5 w-3.5 text-red-700" aria-hidden="true" />
                                  <h4 className="text-xs font-semibold text-red-800">
                                    Considerations
                                  </h4>
                                </div>
                                {pc.cons.length > 0 ? (
                                  <ul className="mt-2 space-y-1.5">
                                    {pc.cons.map((c) => (
                                      <li key={c} className="flex items-start gap-1.5 text-xs text-red-700">
                                        <span className="mt-1 block h-1 w-1 flex-shrink-0 rounded-full bg-red-500" aria-hidden="true" />
                                        {c}
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="mt-2 text-xs text-red-600">
                                    No data available yet
                                  </p>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 text-xs text-stone-400">
                              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                              Loading strengths and considerations...
                            </div>
                          )}

                          {/* Actions */}
                          <div className="flex flex-wrap gap-2 pt-1">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleShortlist(school.school_id);
                              }}
                              className={`inline-flex min-h-[44px] items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                                isShortlisted
                                  ? "bg-yellow-100 text-yellow-800 hover:bg-yellow-200"
                                  : "bg-stone-100 text-stone-700 hover:bg-stone-200"
                              }`}
                            >
                              {isShortlisted ? (
                                <>
                                  <Minus className="h-3.5 w-3.5" aria-hidden="true" />
                                  Remove from shortlist
                                </>
                              ) : (
                                <>
                                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                                  Add to shortlist
                                </>
                              )}
                            </button>
                            <Link
                              to={
                                school.is_private
                                  ? `/private-schools/${school.school_id}`
                                  : `/schools/${school.school_id}`
                              }
                              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-stone-100 px-4 py-2 text-xs font-medium text-stone-700 transition-colors hover:bg-stone-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
                            >
                              View full details
                              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                            </Link>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* Shortlist */}
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <Star className="h-4 w-4 text-yellow-500" aria-hidden="true" />
                <div>
                  <h2 className="text-lg font-semibold text-stone-900">
                    Your shortlist
                  </h2>
                  <p className="mt-0.5 text-xs text-stone-500">
                    {shortlist.length} school{shortlist.length !== 1 ? "s" : ""}{" "}
                    saved. Your shortlist is kept between visits.
                  </p>
                </div>
              </div>
              <div className="flex gap-2 print:hidden">
                {shortlist.length >= 2 && (
                  <Link
                    to={`/compare?ids=${shortlist.join(",")}`}
                    className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-4 py-2 text-xs font-medium text-stone-700 transition-colors hover:bg-stone-50 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    Compare side by side
                    <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </Link>
                )}
                <button
                  onClick={handleExportPdf}
                  disabled={shortlist.length === 0}
                  className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300"
                >
                  <FileDown className="h-3.5 w-3.5" aria-hidden="true" />
                  Export as PDF
                </button>
              </div>
            </div>

            {shortlist.length === 0 ? (
              <div className="mt-5 rounded-xl border-2 border-dashed border-stone-200 px-6 py-8 text-center">
                <Star className="mx-auto h-7 w-7 text-stone-300" aria-hidden="true" />
                <p className="mt-2 text-sm font-medium text-stone-600">
                  No schools shortlisted yet
                </p>
                <p className="mt-1 text-xs text-stone-400">
                  Expand a school above and tap "Add to shortlist" to save it here.
                </p>
              </div>
            ) : (
              <ul className="mt-4 divide-y divide-stone-100" role="list">
                {shortlistedSchools.map((school) => (
                  <li
                    key={school.school_id}
                    className="flex items-center justify-between gap-3 py-3"
                  >
                    <div className="min-w-0">
                      <Link
                        to={
                          school.is_private
                            ? `/private-schools/${school.school_id}`
                            : `/schools/${school.school_id}`
                        }
                        className="text-sm font-medium text-stone-900 hover:text-brand-700 hover:underline"
                      >
                        {school.school_name}
                      </Link>
                      <span className="ml-2 text-xs tabular-nums text-stone-400">
                        Score: {school.composite_score.toFixed(1)}
                      </span>
                    </div>
                    <button
                      onClick={() => removeFromShortlist(school.school_id)}
                      className="flex-shrink-0 rounded-lg px-3 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500"
                      aria-label={`Remove ${school.school_name} from shortlist`}
                    >
                      Remove
                    </button>
                  </li>
                ))}
                {/* Show shortlisted schools not in the current ranked view */}
                {shortlist
                  .filter(
                    (id) => !rankedSchools.some((s) => s.school_id === id),
                  )
                  .map((id) => {
                    const schoolInfo = allSchools.find((s) => s.id === id);
                    return (
                      <li
                        key={id}
                        className="flex items-center justify-between gap-3 py-3"
                      >
                        <span className="text-sm text-stone-700">
                          {schoolInfo?.name ?? `School #${id}`}
                        </span>
                        <button
                          onClick={() => removeFromShortlist(id)}
                          className="flex-shrink-0 rounded-lg px-3 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500"
                          aria-label={`Remove ${schoolInfo?.name ?? `school ${id}`} from shortlist`}
                        >
                          Remove
                        </button>
                      </li>
                    );
                  })}
              </ul>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
