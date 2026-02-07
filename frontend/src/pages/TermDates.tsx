import { useEffect, useState } from "react";
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
  { bg: "bg-blue-50", border: "border-blue-400", text: "text-blue-700", dot: "bg-blue-500" },
  { bg: "bg-emerald-50", border: "border-emerald-400", text: "text-emerald-700", dot: "bg-emerald-500" },
  { bg: "bg-amber-50", border: "border-amber-400", text: "text-amber-700", dot: "bg-amber-500" },
  { bg: "bg-purple-50", border: "border-purple-400", text: "text-purple-700", dot: "bg-purple-500" },
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

  const handleToggleSchool = (id: number) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((sid) => sid !== id);
      }
      if (prev.length >= 4) return prev; // max 4
      return [...prev, id];
    });
  };

  const selectedSchools = schools.filter((s) => selectedIds.includes(s.id));

  /** For a given term name, get the term date object for each selected school. */
  const getTermsForName = (termName: string): (TermDate | undefined)[] => {
    return selectedIds.map((id) => {
      const dates = termDatesBySchool[id] ?? [];
      return dates.find((d) => d.term_name === termName);
    });
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:py-8" role="main">
      <h1 className="text-2xl font-bold text-stone-900 sm:text-3xl">Term Dates</h1>
      <p className="mt-1 text-sm text-stone-600 sm:text-base">
        Compare term dates across Milton Keynes schools. Academies and free
        schools may set their own dates. Private schools often have different
        schedules with longer holidays.
      </p>

      {/* School selector */}
      <div className="mt-6 rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-stone-700">
          Select schools to compare (up to 4)
        </h2>
        {schoolsLoading ? (
          <p className="mt-2 text-sm text-stone-400">Loading schools...</p>
        ) : (
          <div className="mt-2 flex flex-wrap gap-2">
            <select
              className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:w-auto"
              value=""
              onChange={(e) => {
                const id = Number(e.target.value);
                if (id) handleToggleSchool(id);
              }}
            >
              <option value="">-- Add a school --</option>
              {schools
                .filter((s) => !selectedIds.includes(s.id))
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.is_private ? " (Private)" : ""}
                  </option>
                ))}
            </select>
          </div>
        )}

        {/* Selected school chips */}
        {selectedSchools.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedSchools.map((school, idx) => {
              const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
              return (
                <span
                  key={school.id}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium ${colour.bg} ${colour.border} ${colour.text}`}
                >
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${colour.dot}`} />
                  {school.name}
                  <button
                    onClick={() => handleToggleSchool(school.id)}
                    className="ml-1 hover:opacity-70"
                    aria-label={`Remove ${school.name}`}
                  >
                    x
                  </button>
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Term date comparison grid */}
      {selectedIds.length === 0 ? (
        <div className="mt-8 rounded-md border-2 border-dashed border-stone-300 p-12 text-center text-sm text-stone-400">
          Select one or more schools above to view and compare their term dates.
        </div>
      ) : loading ? (
        <div className="mt-8 text-center text-sm text-stone-400">
          Loading term dates...
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
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

            return (
              <div
                key={termName}
                className="rounded-lg border border-stone-200 bg-white p-6"
              >
                <h2 className="text-lg font-semibold text-stone-900">
                  {termName}
                </h2>

                {/* Term Start */}
                <div className="mt-4">
                  <p className={`text-xs font-semibold uppercase tracking-wide ${startDiffers ? "text-amber-600" : "text-stone-500"}`}>
                    Term Start {startDiffers && "(differs)"}
                  </p>
                  <div className="mt-1 space-y-1">
                    {terms.map((term, idx) => {
                      const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
                      const schoolName = selectedSchools[idx]?.name ?? "";
                      return (
                        <div key={idx} className="flex items-center gap-2">
                          <span className={`inline-block h-2 w-2 rounded-full ${colour.dot}`} />
                          <span className={`text-sm ${startDiffers ? "font-semibold" : ""} ${colour.text}`}>
                            {term ? formatDate(term.start_date) : "--"}
                          </span>
                          {selectedIds.length > 1 && (
                            <span className="text-xs text-stone-400 truncate" title={schoolName}>
                              {schoolName.length > 20 ? schoolName.slice(0, 20) + "..." : schoolName}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Half Term */}
                <div className="mt-4">
                  <p className={`text-xs font-semibold uppercase tracking-wide ${htStartDiffers || htEndDiffers ? "text-amber-600" : "text-stone-500"}`}>
                    Half Term {(htStartDiffers || htEndDiffers) && "(differs)"}
                  </p>
                  <div className="mt-1 space-y-1">
                    {terms.map((term, idx) => {
                      const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
                      const ht =
                        term?.half_term_start && term?.half_term_end
                          ? `${formatShortDate(term.half_term_start)} - ${formatShortDate(term.half_term_end)}`
                          : "--";
                      return (
                        <div key={idx} className="flex items-center gap-2">
                          <span className={`inline-block h-2 w-2 rounded-full ${colour.dot}`} />
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
                  <p className={`text-xs font-semibold uppercase tracking-wide ${endDiffers ? "text-amber-600" : "text-stone-500"}`}>
                    Term End {endDiffers && "(differs)"}
                  </p>
                  <div className="mt-1 space-y-1">
                    {terms.map((term, idx) => {
                      const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
                      return (
                        <div key={idx} className="flex items-center gap-2">
                          <span className={`inline-block h-2 w-2 rounded-full ${colour.dot}`} />
                          <span className={`text-sm ${endDiffers ? "font-semibold" : ""} ${colour.text}`}>
                            {term ? formatDate(term.end_date) : "--"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Visual timeline */}
      {selectedIds.length > 0 && !loading && (
        <div className="mt-8 rounded-lg border border-stone-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-stone-900">
            Academic Year Overview
          </h2>
          <p className="mt-1 text-sm text-stone-500">
            Visual comparison of term lengths. Bars represent term duration;
            gaps represent holidays.
          </p>
          <div className="mt-4 space-y-3">
            {selectedSchools.map((school, idx) => {
              const colour = SCHOOL_COLOURS[idx % SCHOOL_COLOURS.length];
              const dates = termDatesBySchool[school.id] ?? [];
              // Calculate total academic year span (Sep 1 to Jul 31)
              const yearStart = new Date("2025-09-01T00:00:00").getTime();
              const yearEnd = new Date("2026-07-31T00:00:00").getTime();
              const totalMs = yearEnd - yearStart;

              return (
                <div key={school.id}>
                  <p className={`text-sm font-medium ${colour.text} mb-1`}>
                    {school.name}
                    {school.is_private ? " (Private)" : ""}
                  </p>
                  <div className="relative h-6 rounded bg-stone-100">
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
                </div>
              );
            })}
            {/* Month labels */}
            <div className="relative h-5 text-xs text-stone-400">
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
          </div>
        </div>
      )}
    </main>
  );
}
