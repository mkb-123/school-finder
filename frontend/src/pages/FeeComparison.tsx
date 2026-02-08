import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PoundSterling, ArrowUpDown, GraduationCap, Bus, Award, BookOpen } from "lucide-react";
import { get } from "../api/client";

interface FeeTier {
  termly_fee: number | null;
  annual_fee: number | null;
  fee_age_group: string | null;
  provides_transport: boolean | null;
}

interface FeeComparisonEntry {
  school_id: number;
  school_name: string;
  age_range_from: number | null;
  age_range_to: number | null;
  gender_policy: string | null;
  faith: string | null;
  fee_tiers: FeeTier[];
  min_termly_fee: number | null;
  max_termly_fee: number | null;
  provides_transport: boolean | null;
  has_bursaries: boolean;
  has_scholarships: boolean;
}

interface FeeComparisonResponse {
  schools: FeeComparisonEntry[];
}

type SortField = "name" | "min_fee" | "max_fee" | "age";
type SortDirection = "asc" | "desc";

function formatFee(amount: number | null): string {
  if (amount == null) return "N/A";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function SkeletonRow() {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-4"><div className="h-4 w-40 rounded bg-stone-200" /></td>
      <td className="px-4 py-4"><div className="h-4 w-16 rounded bg-stone-100" /></td>
      <td className="px-4 py-4"><div className="h-4 w-24 rounded bg-stone-200" /></td>
      <td className="px-4 py-4"><div className="h-4 w-24 rounded bg-stone-200" /></td>
      <td className="px-4 py-4"><div className="h-4 w-12 rounded bg-stone-100" /></td>
      <td className="px-4 py-4"><div className="h-4 w-12 rounded bg-stone-100" /></td>
    </tr>
  );
}

export default function FeeComparison() {
  const [data, setData] = useState<FeeComparisonEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("min_fee");
  const [sortDir, setSortDir] = useState<SortDirection>("asc");
  const [ageFilter, setAgeFilter] = useState<string>("");

  // Fetch available councils
  const [councils, setCouncils] = useState<string[]>([]);
  const [selectedCouncil, setSelectedCouncil] = useState("Milton Keynes");

  useEffect(() => {
    get<string[]>("/councils").then(setCouncils).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedCouncil) return;
    setLoading(true);
    setError(null);
    get<FeeComparisonResponse>("/private-schools/compare/fees", { council: selectedCouncil })
      .then((res) => setData(res.schools))
      .catch((err) => setError(err.detail ?? "Failed to load fee data"))
      .finally(() => setLoading(false));
  }, [selectedCouncil]);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  // Filter by age group tier name
  const filteredData = data.filter((entry) => {
    if (!ageFilter) return true;
    return entry.fee_tiers.some((t) =>
      t.fee_age_group?.toLowerCase().includes(ageFilter.toLowerCase())
    );
  });

  // Sort
  const sortedData = [...filteredData].sort((a, b) => {
    const mul = sortDir === "asc" ? 1 : -1;
    switch (sortField) {
      case "name":
        return mul * a.school_name.localeCompare(b.school_name);
      case "min_fee":
        return mul * ((a.min_termly_fee ?? 99999) - (b.min_termly_fee ?? 99999));
      case "max_fee":
        return mul * ((a.max_termly_fee ?? 99999) - (b.max_termly_fee ?? 99999));
      case "age":
        return mul * ((a.age_range_from ?? 0) - (b.age_range_from ?? 0));
      default:
        return 0;
    }
  });

  function SortButton({ field, label }: { field: SortField; label: string }) {
    const active = sortField === field;
    return (
      <button
        type="button"
        onClick={() => toggleSort(field)}
        className={`group inline-flex items-center gap-1 text-left text-xs font-semibold uppercase tracking-wider transition-colors ${
          active ? "text-private-700" : "text-stone-500 hover:text-stone-700"
        }`}
      >
        {label}
        <ArrowUpDown
          className={`h-3 w-3 transition-colors ${
            active ? "text-private-500" : "text-stone-300 group-hover:text-stone-400"
          }`}
          aria-hidden="true"
        />
      </button>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      {/* Header */}
      <div className="mb-6 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-private-100 text-private-600">
            <PoundSterling className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-stone-900 sm:text-3xl">
              Fee Comparison
            </h1>
            <p className="mt-0.5 text-sm text-stone-600">
              Compare termly fees across all private schools side by side.
            </p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="mb-6 flex flex-wrap items-end gap-4 rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
        <div>
          <label htmlFor="council-fee" className="block text-sm font-medium text-stone-700 mb-1.5">
            Council
          </label>
          <select
            id="council-fee"
            value={selectedCouncil}
            onChange={(e) => setSelectedCouncil(e.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm transition-colors focus:border-private-500 focus:outline-none focus:ring-2 focus:ring-private-500/20"
          >
            <option value="">Select council</option>
            {councils.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="age-filter" className="block text-sm font-medium text-stone-700 mb-1.5">
            Filter by age group
          </label>
          <select
            id="age-filter"
            value={ageFilter}
            onChange={(e) => setAgeFilter(e.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm transition-colors focus:border-private-500 focus:outline-none focus:ring-2 focus:ring-private-500/20"
          >
            <option value="">All age groups</option>
            <option value="nursery">Nursery</option>
            <option value="pre-prep">Pre-prep</option>
            <option value="reception">Reception</option>
            <option value="prep">Prep</option>
            <option value="primary">Primary</option>
            <option value="senior">Senior</option>
            <option value="secondary">Secondary</option>
            <option value="sixth">Sixth Form</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-stone-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-stone-200">
            <thead>
              <tr className="bg-stone-50">
                <th scope="col" className="px-4 py-3 text-left">
                  <SortButton field="name" label="School" />
                </th>
                <th scope="col" className="px-4 py-3 text-left">
                  <SortButton field="age" label="Ages" />
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  <SortButton field="min_fee" label="From (term)" />
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  <SortButton field="max_fee" label="To (term)" />
                </th>
                <th scope="col" className="px-4 py-3 text-center">
                  <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">Transport</span>
                </th>
                <th scope="col" className="px-4 py-3 text-center">
                  <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">Aid</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && (
                <>
                  <SkeletonRow />
                  <SkeletonRow />
                  <SkeletonRow />
                  <SkeletonRow />
                </>
              )}

              {!loading && sortedData.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center">
                      <GraduationCap className="h-10 w-10 text-stone-300" aria-hidden="true" />
                      <p className="mt-3 text-sm font-medium text-stone-700">
                        No private schools with fee data
                      </p>
                      <p className="mt-1 text-xs text-stone-500">
                        Fee data hasn't been collected for schools in this area yet.
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {!loading && sortedData.map((entry) => (
                <tr
                  key={entry.school_id}
                  className="group transition-colors hover:bg-private-50/30"
                >
                  <td className="px-4 py-4">
                    <Link
                      to={`/private-schools/${entry.school_id}`}
                      className="font-medium text-stone-900 transition-colors group-hover:text-private-700"
                    >
                      {entry.school_name}
                    </Link>
                    <div className="mt-0.5 flex flex-wrap gap-1.5">
                      {entry.gender_policy && (
                        <span className="text-xs text-stone-500">{entry.gender_policy}</span>
                      )}
                      {entry.faith && (
                        <span className="text-xs text-stone-400">| {entry.faith}</span>
                      )}
                    </div>
                    {/* Fee tiers detail */}
                    {entry.fee_tiers.length > 0 && (
                      <details className="mt-2 group/detail">
                        <summary className="cursor-pointer text-xs text-private-600 hover:text-private-800 transition-colors">
                          View {entry.fee_tiers.length} fee tier{entry.fee_tiers.length !== 1 ? "s" : ""}
                        </summary>
                        <div className="mt-1.5 space-y-1 pl-2 border-l-2 border-private-100 animate-fade-in">
                          {entry.fee_tiers.map((tier, idx) => (
                            <div key={idx} className="flex justify-between text-xs text-stone-600">
                              <span>{tier.fee_age_group ?? "General"}</span>
                              <span className="font-medium">{formatFee(tier.termly_fee)}/term</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-stone-600">
                    {entry.age_range_from != null && entry.age_range_to != null
                      ? `${entry.age_range_from}\u2013${entry.age_range_to}`
                      : "N/A"}
                  </td>
                  <td className="px-4 py-4 text-right">
                    <span className="text-sm font-semibold text-stone-900">
                      {formatFee(entry.min_termly_fee)}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right">
                    <span className="text-sm font-semibold text-stone-900">
                      {formatFee(entry.max_termly_fee)}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-center">
                    {entry.provides_transport != null ? (
                      entry.provides_transport ? (
                        <Bus className="mx-auto h-4 w-4 text-green-600" aria-label="Transport available" />
                      ) : (
                        <span className="text-xs text-stone-400" aria-label="No transport">--</span>
                      )
                    ) : (
                      <span className="text-xs text-stone-300">?</span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {entry.has_bursaries && (
                        <BookOpen className="h-4 w-4 text-amber-500" aria-label="Bursaries available" />
                      )}
                      {entry.has_scholarships && (
                        <Award className="h-4 w-4 text-private-500" aria-label="Scholarships available" />
                      )}
                      {!entry.has_bursaries && !entry.has_scholarships && (
                        <span className="text-xs text-stone-300">--</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Legend */}
      {!loading && sortedData.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-stone-500">
          <div className="flex items-center gap-1.5">
            <Bus className="h-3.5 w-3.5 text-green-600" aria-hidden="true" />
            <span>Transport provided</span>
          </div>
          <div className="flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
            <span>Bursaries available</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Award className="h-3.5 w-3.5 text-private-500" aria-hidden="true" />
            <span>Scholarships available</span>
          </div>
        </div>
      )}

      {/* Data disclaimer */}
      <p className="mt-6 text-xs text-stone-400">
        Fee data is sourced from school websites and prospectuses. Verify current fees directly
        with the school. Last updated figures may not reflect the most recent fee schedule.
      </p>
    </main>
  );
}
