import { useEffect, useState } from "react";
import { Calendar, X, Loader2, AlertTriangle, Plus } from "lucide-react";
import { get } from "../api/client";

interface SchoolSummary {
  id: number;
  name: string;
  type: string | null;
  is_private: boolean;
}

interface TermDate {
  id: number;
  school_id: number;
  academic_year: string;
  term_name: string;
  start_date: string;
  end_date: string;
  half_term_start: string | null;
  half_term_end: string | null;
}

/** Colour palette for each school slot (up to 4). */
const SCHOOL_COLOURS = [
  { bg: "bg-blue-50", border: "border-blue-400", text: "text-blue-700", dot: "bg-blue-500", ring: "ring-blue-500" },
  { bg: "bg-emerald-50", border: "border-emerald-400", text: "text-emerald-700", dot: "bg-emerald-500", ring: "ring-emerald-500" },
  { bg: "bg-amber-50", border: "border-amber-400", text: "text-amber-700", dot: "bg-amber-500", ring: "ring-amber-500" },
  { bg: "bg-purple-50", border: "border-purple-400", text: "text-purple-700", dot: "bg-purple-500", ring: "ring-purple-500" },
];

const TERM_NAMES = ["Autumn Term", "Spring Term", "Summer Term"];

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function formatShortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** Check if two date strings differ. */
function datesDiffer(dates: (string | null | undefined)[]): boolean {
  const valid = dates.filter((d): d is string => d != null);
  if (valid.length <= 1) return false;
  return new Set(valid).size > 1;
}

export default function TermDates() {
  const [schools, setSchools] = useState<SchoolSummary[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [termDatesBySchool, setTermDatesBySchool] = useState<Record<number, TermDate[]>>({});
  const [loading, setLoading] = useState(false);
  const [schoolsLoading, setSchoolsLoading] = useState(true);
  const [schoolSearch, setSchoolSearch] = useState("");

  // Fetch school list on mount
  useEffect(() => {
    setSchoolsLoading(true);
    get<SchoolSummary[]>("/schools", { council: "Milton Keynes" })
      .then((data) => setSchools(data))
      .catch(() => setSchools([]))
      .finally(() => setSchoolsLoading(false));
  }, []);

  // Fetch term dates whenever selection changes
  useEffect(() => {
    if (selectedIds.length === 0) return;

    const idsToFetch = selectedIds.filter((id) => !(id in termDatesBySchool));
    if (idsToFetch.length === 0) return;

    setLoading(true);
    Promise.all(
      idsToFetch.map((id) =>
        get<TermDate[]>(`/schools/${id}/term-dates`).then((dates) => ({ id, dates }))
      )
    )
      .then((results) => {
        setTermDatesBySchool((prev) => {
          const next = { ...prev };
          for (const { id, dates } of results) {
            next[id] = dates;
          }
          return next;
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedIds, termDatesBySchool]);

  const handleAddSchool = (id: number) => {
    if (selectedIds.includes(id) || selectedIds.length >= 4) return;
    setSelectedIds((prev) => [...prev, id]);
  };

  const handleRemoveSchool = (id: number) => {
    setSelectedIds((prev) => prev.filter((sid) => sid !== id));
  };

  const selectedSchools = schools.filter((s) => selectedIds.includes(s.id));
  const availableSchools = schools.filter((s) => !selectedIds.includes(s.id));

  const filteredAvailableSchools = schoolSearch.trim()
    ? availableSchools.filter((s) =>
        s.name.toLowerCase().includes(schoolSearch.toLowerCase()),
      )
    : availableSchools;

  /** For a given term name, get the term date object for each selected school. */
  const getTermsForName = (termName: string): (TermDate | undefined)[] => {
    return selectedIds.map((id) => {
      const dates = termDatesBySchool[id] ?? [];
      return dates.find((d) => d.term_name === termName);
    });
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:py-8" role="main">
      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 sm:h-12 sm:w-12">
          <Calendar className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">Term Dates</h1>
          <p className="mt-1 text-sm leading-relaxed text-gray-600 sm:text-base">
            Compare term dates across schools. Academies and free schools may
            set their own dates, and private schools often have different
            schedules with longer holidays.
          </p>
        </div>
      </div>

      {/* School selector */}
      <section className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold text-gray-900">
            Schools to compare
          </h2>
          <span className="text-xs text-gray-500">
            {selectedIds.length} of 4
          </span>
        </div>

        {/* Selected school chips */}
        {selectedSchools.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedSchools.map((school, idx) => {
              const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
              return (
                <span
                  key={school.id}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium ${colour.bg} ${colour.border} ${colour.text}`}
                >
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${colour.dot}`} aria-hidden="true" />
                  <span className="max-w-[180px] truncate sm:max-w-none">{school.name}</span>
                  {school.is_private && (
                    <span className="text-xs opacity-70">(Private)</span>
                  )}
                  <button
                    onClick={() => handleRemoveSchool(school.id)}
                    className={`ml-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full transition-opacity hover:opacity-70 focus:outline-none focus:ring-2 ${colour.ring} focus:ring-offset-1`}
                    aria-label={`Remove ${school.name} from comparison`}
                  >
                    <X className="h-3 w-3" aria-hidden="true" />
                  </button>
                </span>
              );
            })}
          </div>
        )}

        {/* Add school control */}
        {selectedIds.length < 4 && (
          <div className="mt-3">
            {schoolsLoading ? (
              <div className="flex items-center gap-2 py-3 text-sm text-gray-400">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Loading schools...
              </div>
            ) : (
              <>
                <div className="relative">
                  <Plus className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
                  <input
                    type="text"
                    placeholder="Search and add a school..."
                    value={schoolSearch}
                    onChange={(e) => setSchoolSearch(e.target.value)}
                    aria-label="Search for a school to add to comparison"
                    className="block w-full rounded-lg border border-gray-300 py-2.5 pl-9 pr-3 text-sm shadow-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:w-80"
                  />
                </div>
                {schoolSearch.trim() && (
                  <div className="mt-1.5 max-h-36 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                    {filteredAvailableSchools.length === 0 ? (
                      <p className="py-3 text-center text-xs text-gray-400">
                        No matching schools found
                      </p>
                    ) : (
                      filteredAvailableSchools.slice(0, 10).map((s) => (
                        <button
                          key={s.id}
                          onClick={() => {
                            handleAddSchool(s.id);
                            setSchoolSearch("");
                          }}
                          className="flex w-full min-h-[44px] items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 transition-colors hover:bg-gray-50"
                        >
                          <Plus className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" aria-hidden="true" />
                          <span className="truncate">{s.name}</span>
                          {s.is_private && (
                            <span className="ml-auto flex-shrink-0 text-xs text-gray-400">(Private)</span>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>

      {/* Term date comparison grid */}
      {selectedIds.length === 0 ? (
        <div className="mt-8 rounded-xl border-2 border-dashed border-gray-200 px-6 py-12 text-center">
          <Calendar className="mx-auto h-10 w-10 text-gray-300" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium text-gray-600">
            Select schools to compare their term dates
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Search for schools above to see their term dates side by side. You
            can compare up to 4 schools at once.
          </p>
        </div>
      ) : loading ? (
        <div className="mt-8 flex items-center justify-center gap-2 py-12 text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading term dates...
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-3">
          {TERM_NAMES.map((termName) => {
            const terms = getTermsForName(termName);
            const startDates = terms.map((t) => t?.start_date);
            const endDates = terms.map((t) => t?.end_date);
            const htStarts = terms.map((t) => t?.half_term_start);
            const htEnds = terms.map((t) => t?.half_term_end);

            const startDiffers = datesDiffer(startDates);
            const endDiffers = datesDiffer(endDates);
            const htStartDiffers = datesDiffer(htStarts);
            const htEndDiffers = datesDiffer(htEnds);

            // Check if any school has data for this term
            const anyData = terms.some((t) => t != null);

            return (
              <section
                key={termName}
                className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
                aria-label={`${termName} dates`}
              >
                <h2 className="text-lg font-semibold text-gray-900">
                  {termName}
                </h2>

                {!anyData && (
                  <p className="mt-4 text-xs text-gray-400">
                    No term dates available for the selected schools yet.
                  </p>
                )}

                {anyData && (
                  <>
                    {/* Term Start */}
                    <div className="mt-4">
                      <div className="flex items-center gap-1.5">
                        <p className={`text-xs font-semibold uppercase tracking-wide ${startDiffers ? "text-amber-600" : "text-gray-500"}`}>
                          Term Start
                        </p>
                        {startDiffers && (
                          <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                            <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                            Differs
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 space-y-1.5">
                        {terms.map((term, idx) => {
                          const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
                          const schoolName = selectedSchools[idx]?.name ?? "";
                          return (
                            <div key={idx} className="flex items-center gap-2">
                              <span className={`inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full ${colour.dot}`} aria-hidden="true" />
                              <span className={`text-sm ${startDiffers ? "font-semibold" : ""} ${colour.text}`}>
                                {term ? formatDate(term.start_date) : "No data available"}
                              </span>
                              {selectedIds.length > 1 && (
                                <span
                                  className="truncate text-xs text-gray-400"
                                  title={schoolName}
                                >
                                  {schoolName.length > 18 ? schoolName.slice(0, 18) + "..." : schoolName}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Half Term */}
                    <div className="mt-4">
                      <div className="flex items-center gap-1.5">
                        <p className={`text-xs font-semibold uppercase tracking-wide ${htStartDiffers || htEndDiffers ? "text-amber-600" : "text-gray-500"}`}>
                          Half Term
                        </p>
                        {(htStartDiffers || htEndDiffers) && (
                          <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                            <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                            Differs
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 space-y-1.5">
                        {terms.map((term, idx) => {
                          const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
                          const ht =
                            term?.half_term_start && term?.half_term_end
                              ? `${formatShortDate(term.half_term_start)} - ${formatShortDate(term.half_term_end)}`
                              : "No data available";
                          return (
                            <div key={idx} className="flex items-center gap-2">
                              <span className={`inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full ${colour.dot}`} aria-hidden="true" />
                              <span className={`text-sm ${htStartDiffers || htEndDiffers ? "font-semibold" : ""} ${colour.text}`}>
                                {ht}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Term End */}
                    <div className="mt-4">
                      <div className="flex items-center gap-1.5">
                        <p className={`text-xs font-semibold uppercase tracking-wide ${endDiffers ? "text-amber-600" : "text-gray-500"}`}>
                          Term End
                        </p>
                        {endDiffers && (
                          <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                            <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                            Differs
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 space-y-1.5">
                        {terms.map((term, idx) => {
                          const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
                          return (
                            <div key={idx} className="flex items-center gap-2">
                              <span className={`inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full ${colour.dot}`} aria-hidden="true" />
                              <span className={`text-sm ${endDiffers ? "font-semibold" : ""} ${colour.text}`}>
                                {term ? formatDate(term.end_date) : "No data available"}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )}
              </section>
            );
          })}
        </div>
      )}

      {/* Visual timeline */}
      {selectedIds.length > 0 && !loading && (
        <section
          className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:mt-8 sm:p-6"
          aria-label="Academic year timeline"
        >
          <h2 className="text-lg font-semibold text-gray-900">
            Academic year overview
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-gray-500">
            Coloured bars show term durations; gaps show holidays. White marks
            within bars indicate half-term breaks.
          </p>

          <div className="mt-5 space-y-4">
            {selectedSchools.map((school, idx) => {
              const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
              const dates = termDatesBySchool[school.id] ?? [];
              // Calculate total academic year span (Sep 1 to Jul 31)
              const yearStart = new Date("2025-09-01T00:00:00").getTime();
              const yearEnd = new Date("2026-07-31T00:00:00").getTime();
              const totalMs = yearEnd - yearStart;

              return (
                <div key={school.id}>
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className={`inline-block h-2.5 w-2.5 rounded-full ${colour.dot}`} aria-hidden="true" />
                    <p className={`text-sm font-medium ${colour.text}`}>
                      {school.name}
                      {school.is_private ? " (Private)" : ""}
                    </p>
                  </div>
                  {dates.length === 0 ? (
                    <div className="h-7 rounded-lg bg-gray-100 flex items-center justify-center">
                      <span className="text-[10px] text-gray-400">No term date data available</span>
                    </div>
                  ) : (
                    <div
                      className="relative h-7 rounded-lg bg-gray-100"
                      role="img"
                      aria-label={`Timeline for ${school.name}: ${dates.map((t) => `${t.term_name} from ${formatShortDate(t.start_date)} to ${formatShortDate(t.end_date)}`).join("; ")}`}
                    >
                      {dates.map((term) => {
                        const tStart = new Date(term.start_date + "T00:00:00").getTime();
                        const tEnd = new Date(term.end_date + "T00:00:00").getTime();
                        const leftPct = Math.max(0, ((tStart - yearStart) / totalMs) * 100);
                        const widthPct = Math.max(0.5, ((tEnd - tStart) / totalMs) * 100);
                        return (
                          <div
                            key={term.id}
                            className={`absolute top-0 h-full rounded ${colour.dot} opacity-60`}
                            style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                            title={`${term.term_name}: ${formatShortDate(term.start_date)} - ${formatShortDate(term.end_date)}`}
                          />
                        );
                      })}
                      {/* Half-term breaks shown as lighter overlay */}
                      {dates.map((term) => {
                        if (!term.half_term_start || !term.half_term_end) return null;
                        const htStart = new Date(term.half_term_start + "T00:00:00").getTime();
                        const htEnd = new Date(term.half_term_end + "T00:00:00").getTime();
                        const leftPct = Math.max(0, ((htStart - yearStart) / totalMs) * 100);
                        const widthPct = Math.max(0.3, ((htEnd - htStart) / totalMs) * 100);
                        return (
                          <div
                            key={`ht-${term.id}`}
                            className="absolute top-0 h-full rounded bg-white opacity-70"
                            style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                            title={`Half term: ${formatShortDate(term.half_term_start)} - ${formatShortDate(term.half_term_end)}`}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Month labels */}
            <div className="relative mt-1 hidden h-5 text-[10px] text-gray-400 sm:block" aria-hidden="true">
              {["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"].map(
                (month, i) => (
                  <span
                    key={month}
                    className="absolute"
                    style={{ left: `${(i / 11) * 100}%` }}
                  >
                    {month}
                  </span>
                )
              )}
            </div>
            {/* Simplified mobile month labels - show fewer months to avoid overlap */}
            <div className="relative mt-1 flex h-5 justify-between text-[10px] text-gray-400 sm:hidden" aria-hidden="true">
              {["Sep", "Nov", "Jan", "Mar", "May", "Jul"].map((month) => (
                <span key={month}>{month}</span>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
