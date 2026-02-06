import { useSearchParams } from "react-router-dom";

export default function Compare() {
  const [searchParams] = useSearchParams();
  const ids = searchParams.get("ids")?.split(",").filter(Boolean) ?? [];

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">Compare Schools</h1>
      <p className="mt-1 text-gray-600">
        Side-by-side comparison of 2-4 schools. Select schools from the search
        results page or enter school IDs to compare every metric in columns.
      </p>

      {ids.length > 0 ? (
        <p className="mt-4 text-sm text-gray-500">
          Comparing schools: {ids.join(", ")}
        </p>
      ) : (
        <p className="mt-4 text-sm text-gray-500">
          No schools selected yet. Add school IDs via the{" "}
          <code className="rounded bg-gray-100 px-1 py-0.5 text-xs">
            ?ids=1,2,3
          </code>{" "}
          query parameter.
        </p>
      )}

      {/* Comparison table placeholder */}
      <div className="mt-8 overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 border border-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Metric
              </th>
              {(ids.length > 0 ? ids : ["School A", "School B", "School C"]).map(
                (label) => (
                  <th
                    key={label}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                  >
                    {label}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {[
              "Ofsted Rating",
              "Distance",
              "School Type",
              "Age Range",
              "Breakfast Club",
              "After-School Club",
              "SATs / GCSE Results",
              "Progress 8",
              "Term Dates",
              "Waiting List Likelihood",
            ].map((metric) => (
              <tr key={metric}>
                <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                  {metric}
                </td>
                {(ids.length > 0 ? ids : ["A", "B", "C"]).map((col) => (
                  <td
                    key={col}
                    className="whitespace-nowrap px-4 py-3 text-sm text-gray-500"
                  >
                    --
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
