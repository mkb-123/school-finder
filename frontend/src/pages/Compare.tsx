import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { get } from "../api/client";

interface Performance {
  id: number;
  school_id: number;
  metric_type: string;
  metric_value: string;
  year: number;
  source_url: string | null;
}

interface Club {
  id: number;
  club_type: string;
  name: string;
}

interface CompareSchool {
  id: number;
  name: string;
  type: string | null;
  ofsted_rating: string | null;
  ofsted_date: string | null;
  age_range_from: number | null;
  age_range_to: number | null;
  gender_policy: string | null;
  faith: string | null;
  distance_km: number | null;
  catchment_radius_km: number | null;
  is_private: boolean;
  clubs: Club[];
  performance: Performance[];
  ethos: string | null;
}

interface CompareResponse {
  schools: CompareSchool[];
}

const RATING_COLORS: Record<string, string> = {
  Outstanding: "text-green-700 font-semibold",
  Good: "text-blue-700 font-semibold",
  "Requires Improvement": "text-amber-700 font-semibold",
  Inadequate: "text-red-700 font-semibold",
};

/** Get the latest year's metric value for a given metric type. */
function latestMetric(
  performance: Performance[],
  metricType: string,
): string | null {
  const matches = performance
    .filter((p) => p.metric_type === metricType)
    .sort((a, b) => b.year - a.year);
  return matches.length > 0 ? matches[0].metric_value : null;
}

/** Colour Progress 8 values: green if positive, red if negative. */
function Progress8Cell({ value }: { value: string | null }) {
  if (!value) return <span className="text-gray-400">--</span>;
  const num = parseFloat(value);
  let cls = "text-gray-900";
  if (!isNaN(num)) {
    if (num > 0) cls = "text-green-700 font-semibold";
    else if (num < 0) cls = "text-red-700 font-semibold";
  }
  return <span className={cls}>{value}</span>;
}

export default function Compare() {
  const [searchParams] = useSearchParams();
  const ids = searchParams.get("ids")?.split(",").filter(Boolean) ?? [];
  const [schools, setSchools] = useState<CompareSchool[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (ids.length === 0) return;
    setLoading(true);
    get<CompareResponse>(`/compare`, { ids: ids.join(",") })
      .then((data) => setSchools(data.schools))
      .catch(() => setSchools([]))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);

  // Determine whether to show primary or secondary metrics
  const hasPrimary = schools.some((s) =>
    s.performance.some((p) => p.metric_type === "SATs"),
  );
  const hasSecondary = schools.some((s) =>
    s.performance.some((p) => p.metric_type === "GCSE"),
  );

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:py-8" role="main">
      <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">Compare Schools</h1>
      <p className="mt-1 text-sm text-gray-600 sm:text-base">
        Side-by-side comparison of 2-4 schools. Select schools from the search
        results page or enter school IDs to compare every metric in columns.
      </p>

      {ids.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">
          No schools selected yet. Add school IDs via the{" "}
          <code className="rounded bg-gray-100 px-1 py-0.5 text-xs">
            ?ids=1,2,3
          </code>{" "}
          query parameter.
        </p>
      )}

      {loading && (
        <p className="mt-4 text-gray-500" aria-live="polite">Loading comparison data...</p>
      )}

      {!loading && schools.length > 0 && (
        <div className="mt-8 -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <table
            className="min-w-full divide-y divide-gray-200 border border-gray-200"
            aria-label="School comparison table"
          >
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Metric
                </th>
                {schools.map((s) => (
                  <th
                    key={s.id}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                  >
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {/* Ofsted Rating */}
              <tr>
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Ofsted Rating
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className={`whitespace-nowrap px-4 py-3 text-sm ${
                      RATING_COLORS[s.ofsted_rating ?? ""] ?? "text-gray-500"
                    }`}
                  >
                    {s.ofsted_rating ?? "--"}
                  </td>
                ))}
              </tr>

              {/* Last Inspection */}
              <tr className="bg-gray-50">
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Last Inspection
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    {s.ofsted_date ?? "--"}
                  </td>
                ))}
              </tr>

              {/* Ethos */}
              <tr>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">
                  Ethos
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="px-4 py-3 text-sm italic text-gray-600"
                  >
                    {s.ethos ? `"${s.ethos}"` : "--"}
                  </td>
                ))}
              </tr>

              {/* School Type */}
              <tr className="bg-gray-50">
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  School Type
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    {s.is_private ? "Private" : s.type ?? "--"}
                  </td>
                ))}
              </tr>

              {/* Age Range */}
              <tr className="bg-gray-50">
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Age Range
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    {s.age_range_from != null && s.age_range_to != null
                      ? `${s.age_range_from}-${s.age_range_to}`
                      : "--"}
                  </td>
                ))}
              </tr>

              {/* Breakfast Club */}
              <tr>
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Breakfast Club
                </td>
                {schools.map((s) => {
                  const has = s.clubs.some((c) => c.club_type === "breakfast");
                  return (
                    <td
                      key={s.id}
                      className={`whitespace-nowrap px-4 py-3 text-sm ${has ? "text-green-700 font-medium" : "text-gray-400"}`}
                    >
                      {has ? "Yes" : "No"}
                    </td>
                  );
                })}
              </tr>

              {/* After-School Club */}
              <tr className="bg-gray-50">
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  After-School Club
                </td>
                {schools.map((s) => {
                  const has = s.clubs.some(
                    (c) => c.club_type === "after_school",
                  );
                  return (
                    <td
                      key={s.id}
                      className={`whitespace-nowrap px-4 py-3 text-sm ${has ? "text-green-700 font-medium" : "text-gray-400"}`}
                    >
                      {has ? "Yes" : "No"}
                    </td>
                  );
                })}
              </tr>

              {/* Performance - SATs (primary) */}
              {hasPrimary && (
                <tr>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    SATs (Expected Standard)
                  </td>
                  {schools.map((s) => (
                    <td
                      key={s.id}
                      className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                    >
                      {latestMetric(s.performance, "SATs") ?? "--"}
                    </td>
                  ))}
                </tr>
              )}

              {hasPrimary && (
                <tr className="bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    SATs (Higher Standard)
                  </td>
                  {schools.map((s) => (
                    <td
                      key={s.id}
                      className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                    >
                      {latestMetric(s.performance, "SATs_Higher") ?? "--"}
                    </td>
                  ))}
                </tr>
              )}

              {/* Performance - GCSE (secondary) */}
              {hasSecondary && (
                <tr className={hasPrimary ? "" : "bg-gray-50"}>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    GCSE Results
                  </td>
                  {schools.map((s) => (
                    <td
                      key={s.id}
                      className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                    >
                      {latestMetric(s.performance, "GCSE") ?? "--"}
                    </td>
                  ))}
                </tr>
              )}

              {/* Progress 8 */}
              {hasSecondary && (
                <tr>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    Progress 8
                  </td>
                  {schools.map((s) => (
                    <td
                      key={s.id}
                      className="whitespace-nowrap px-4 py-3 text-sm"
                    >
                      <Progress8Cell
                        value={latestMetric(s.performance, "Progress8")}
                      />
                    </td>
                  ))}
                </tr>
              )}

              {/* Attainment 8 */}
              {hasSecondary && (
                <tr className="bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    Attainment 8
                  </td>
                  {schools.map((s) => (
                    <td
                      key={s.id}
                      className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                    >
                      {latestMetric(s.performance, "Attainment8") ?? "--"}
                    </td>
                  ))}
                </tr>
              )}

              {/* Catchment radius */}
              <tr>
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Catchment Radius
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    {s.catchment_radius_km != null
                      ? `${s.catchment_radius_km} km`
                      : "--"}
                  </td>
                ))}
              </tr>

              {/* Gender */}
              <tr className="bg-gray-50">
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Gender Policy
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    {s.gender_policy ?? "--"}
                  </td>
                ))}
              </tr>

              {/* Faith */}
              <tr>
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  Faith
                </td>
                {schools.map((s) => (
                  <td
                    key={s.id}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    {s.faith ?? "None"}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {!loading && ids.length > 0 && schools.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">
          No matching schools found for the given IDs.
        </p>
      )}
    </main>
  );
}
