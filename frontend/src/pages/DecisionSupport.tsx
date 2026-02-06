import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ComponentScores {
  distance: number;
  ofsted: number;
  clubs: number;
  fees: number;
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
  Outstanding: "bg-green-100 text-green-800",
  Good: "bg-blue-100 text-blue-800",
  "Requires Improvement": "bg-amber-100 text-amber-800",
  Inadequate: "bg-red-100 text-red-800",
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

type WeightKey = "distance" | "ofsted" | "clubs" | "fees";
type Weights = Record<WeightKey, number>;

const WEIGHT_LABELS: [WeightKey, string][] = [
  ["distance", "Distance"],
  ["ofsted", "Ofsted Rating"],
  ["clubs", "Clubs & Wraparound"],
  ["fees", "Fees / Value"],
];

const DEFAULT_WEIGHTS: Weights = {
  distance: 30,
  ofsted: 30,
  clubs: 20,
  fees: 20,
};

export default function DecisionSupport() {
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

  const [whatIf, setWhatIf] = useState<WhatIfFilters>({
    okWith15MinDrive: false,
    dropMinOfstedToGood: false,
    includeFaith: false,
  });

  // --- Load school list on mount ---
  useEffect(() => {
    get<SchoolListItem[]>("/schools", { council: "Milton Keynes" })
      .then((data) => {
        setAllSchools(data);
        // Pre-select the first 10 (or all if less)
        const initial = data.slice(0, 10).map((s) => s.id);
        setSelectedIds(initial);
      })
      .catch(() => setError("Failed to load schools"));
  }, []);

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
      setError("Failed to fetch scores");
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

  // --- Render ---
  const shortlistedSchools = rankedSchools.filter((s) =>
    shortlist.includes(s.school_id),
  );

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8 print:px-0" role="main">
      <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">Decision Support</h1>
      <p className="mt-1 text-sm text-gray-600 sm:text-base">
        Set your priorities, explore scenarios, and build a shortlist to find the
        best school for your family.
      </p>

      {error && (
        <div className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 sm:mt-8 sm:gap-8 lg:grid-cols-12">
        {/* ---- Left column: controls ---- */}
        <aside className="space-y-4 sm:space-y-6 lg:col-span-4 print:hidden" aria-label="Decision support controls">
          {/* School selector */}
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-base font-semibold text-gray-900">
              Select Schools
            </h2>
            <p className="mt-1 text-xs text-gray-500">
              Choose which schools to include in scoring.
            </p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={selectAllSchools}
                aria-label="Select all schools"
                className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
              >
                Select all
              </button>
              <button
                onClick={clearSelection}
                aria-label="Clear school selection"
                className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
              >
                Clear
              </button>
            </div>
            <div className="mt-3 max-h-48 space-y-1 overflow-y-auto">
              {allSchools.map((school) => (
                <label
                  key={school.id}
                  className="flex items-center gap-2 rounded px-1 py-0.5 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(school.id)}
                    onChange={() => toggleSchoolSelection(school.id)}
                    className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
                  />
                  <span className="truncate">{school.name}</span>
                </label>
              ))}
              {allSchools.length === 0 && (
                <p className="text-xs text-gray-400">Loading schools...</p>
              )}
            </div>
          </section>

          {/* Priority sliders */}
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-base font-semibold text-gray-900">
              Your Priorities
            </h2>
            <p className="mt-1 text-xs text-gray-500">
              Adjust sliders to set how important each factor is. They
              auto-normalise.
            </p>
            <div className="mt-4 space-y-4">
              {WEIGHT_LABELS.map(([key, label]) => (
                <div key={key}>
                  <div className="flex justify-between text-sm">
                    <label
                      htmlFor={`w-${key}`}
                      className="font-medium text-gray-700"
                    >
                      {label}
                    </label>
                    <span className="tabular-nums text-gray-500">
                      {weights[key]}
                    </span>
                  </div>
                  <input
                    id={`w-${key}`}
                    type="range"
                    min={0}
                    max={100}
                    value={weights[key]}
                    onChange={(e) =>
                      handleWeightChange(key, Number(e.target.value))
                    }
                    aria-label={`${label} weight: ${weights[key]} out of 100`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={weights[key]}
                    className="mt-1 w-full accent-blue-600"
                  />
                </div>
              ))}
            </div>
          </section>

          {/* What-if controls */}
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-base font-semibold text-gray-900">
              &quot;What If&quot; Scenarios
            </h2>
            <p className="mt-1 text-xs text-gray-500">
              Toggle constraints to see how the rankings change.
            </p>
            <div className="mt-3 space-y-2">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={whatIf.okWith15MinDrive}
                  onChange={(e) =>
                    setWhatIf((p) => ({
                      ...p,
                      okWith15MinDrive: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                OK with a 15 km drive
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={whatIf.dropMinOfstedToGood}
                  onChange={(e) =>
                    setWhatIf((p) => ({
                      ...p,
                      dropMinOfstedToGood: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                Drop minimum Ofsted to Good
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={whatIf.includeFaith}
                  onChange={(e) =>
                    setWhatIf((p) => ({
                      ...p,
                      includeFaith: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                Include faith schools
              </label>
            </div>
          </section>
        </aside>

        {/* ---- Right column: results ---- */}
        <div className="space-y-6 lg:col-span-8">
          {/* Ranked list */}
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Ranked Schools
                </h2>
                <p className="mt-0.5 text-xs text-gray-500">
                  {rankedSchools.length} school
                  {rankedSchools.length !== 1 ? "s" : ""} ranked by your
                  composite score. Click to see pros &amp; cons.
                </p>
              </div>
              {loading && (
                <span className="text-xs text-gray-400">Updating...</span>
              )}
            </div>

            {rankedSchools.length === 0 && !loading ? (
              <div className="mt-4 rounded-md border-2 border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
                {selectedIds.length === 0
                  ? "Select schools from the panel on the left to begin."
                  : "No schools match the current filters."}
              </div>
            ) : (
              <ul className="mt-4 divide-y divide-gray-100">
                {rankedSchools.map((school, idx) => {
                  const isExpanded = expandedSchoolId === school.school_id;
                  const pc = prosConsMap[school.school_id];
                  const isShortlisted = shortlist.includes(school.school_id);
                  const ratingColor =
                    OFSTED_COLORS[school.ofsted_rating ?? ""] ??
                    "bg-gray-100 text-gray-600";

                  return (
                    <li key={school.school_id} className="py-3">
                      {/* Main row */}
                      <button
                        onClick={() => handleExpand(school.school_id)}
                        className="w-full text-left"
                      >
                        <div className="flex items-start gap-3">
                          {/* Rank badge */}
                          <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-700">
                            {idx + 1}
                          </span>

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="truncate font-medium text-gray-900">
                                {school.school_name}
                              </span>
                              {school.ofsted_rating && (
                                <span
                                  className={`inline-flex flex-shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${ratingColor}`}
                                >
                                  {school.ofsted_rating}
                                </span>
                              )}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
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
                                <span className="text-gray-600">
                                  {"\u00A3"}
                                  {school.annual_fee.toLocaleString()}/yr
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Score bar */}
                          <div className="flex w-28 flex-shrink-0 flex-col items-end">
                            <span className="text-sm font-bold text-gray-900">
                              {school.composite_score.toFixed(1)}
                            </span>
                            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                              <div
                                className="h-full rounded-full bg-blue-600 transition-all"
                                style={{
                                  width: `${Math.min(school.composite_score, 100)}%`,
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      </button>

                      {/* Expanded: component scores + pros/cons */}
                      {isExpanded && (
                        <div className="ml-10 mt-3 space-y-3">
                          {/* Component score bars */}
                          <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
                            {(
                              [
                                ["distance", "Distance"],
                                ["ofsted", "Ofsted"],
                                ["clubs", "Clubs"],
                                ["fees", "Fees"],
                              ] as [keyof ComponentScores, string][]
                            ).map(([key, label]) => (
                              <div key={key}>
                                <div className="flex justify-between text-xs text-gray-500">
                                  <span>{label}</span>
                                  <span>
                                    {school.component_scores[key].toFixed(0)}
                                  </span>
                                </div>
                                <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                                  <div
                                    className="h-full rounded-full bg-indigo-500"
                                    style={{
                                      width: `${Math.min(school.component_scores[key], 100)}%`,
                                    }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Pros / Cons */}
                          {pc ? (
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                              <div className="rounded-md bg-green-50 p-3">
                                <h4 className="text-xs font-semibold text-green-800">
                                  Pros
                                </h4>
                                {pc.pros.length > 0 ? (
                                  <ul className="mt-1 list-inside list-disc text-xs text-green-700">
                                    {pc.pros.map((p) => (
                                      <li key={p}>{p}</li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="mt-1 text-xs text-green-600">
                                    None identified
                                  </p>
                                )}
                              </div>
                              <div className="rounded-md bg-red-50 p-3">
                                <h4 className="text-xs font-semibold text-red-800">
                                  Cons
                                </h4>
                                {pc.cons.length > 0 ? (
                                  <ul className="mt-1 list-inside list-disc text-xs text-red-700">
                                    {pc.cons.map((c) => (
                                      <li key={c}>{c}</li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="mt-1 text-xs text-red-600">
                                    None identified
                                  </p>
                                )}
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-gray-400">
                              Loading pros &amp; cons...
                            </p>
                          )}

                          {/* Actions */}
                          <div className="flex gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleShortlist(school.school_id);
                              }}
                              className={`rounded px-3 py-1 text-xs font-medium transition ${
                                isShortlisted
                                  ? "bg-yellow-100 text-yellow-800 hover:bg-yellow-200"
                                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                              }`}
                            >
                              {isShortlisted
                                ? "Remove from shortlist"
                                : "Add to shortlist"}
                            </button>
                            <Link
                              to={
                                school.is_private
                                  ? `/private-schools/${school.school_id}`
                                  : `/schools/${school.school_id}`
                              }
                              className="rounded bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                            >
                              View details
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
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Your Shortlist
                </h2>
                <p className="mt-0.5 text-xs text-gray-500">
                  {shortlist.length} school
                  {shortlist.length !== 1 ? "s" : ""} saved (persisted in local
                  storage).
                </p>
              </div>
              <div className="flex gap-2 print:hidden">
                {shortlist.length >= 2 && (
                  <Link
                    to={`/compare?ids=${shortlist.join(",")}`}
                    className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Compare side-by-side
                  </Link>
                )}
                <button
                  onClick={handleExportPdf}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                >
                  Export as PDF
                </button>
              </div>
            </div>

            {shortlist.length === 0 ? (
              <div className="mt-4 rounded-md border-2 border-dashed border-gray-300 p-6 text-center text-sm text-gray-400">
                Click &quot;Add to shortlist&quot; on any school above to save it
                here.
              </div>
            ) : (
              <ul className="mt-3 divide-y divide-gray-100">
                {shortlistedSchools.map((school) => (
                  <li
                    key={school.school_id}
                    className="flex items-center justify-between py-2"
                  >
                    <div>
                      <span className="text-sm font-medium text-gray-900">
                        {school.school_name}
                      </span>
                      <span className="ml-2 text-xs text-gray-500">
                        Score: {school.composite_score.toFixed(1)}
                      </span>
                    </div>
                    <button
                      onClick={() => removeFromShortlist(school.school_id)}
                      className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
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
                        className="flex items-center justify-between py-2"
                      >
                        <span className="text-sm text-gray-700">
                          {schoolInfo?.name ?? `School #${id}`}
                        </span>
                        <button
                          onClick={() => removeFromShortlist(id)}
                          className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
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
