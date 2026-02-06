import { useState } from "react";
import { useParams } from "react-router-dom";

const TABS = [
  "Overview",
  "Clubs",
  "Performance",
  "Term Dates",
  "Admissions",
] as const;
type Tab = (typeof TABS)[number];

export default function SchoolDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("Overview");

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">School Detail</h1>
      <p className="mt-1 text-gray-600">
        Viewing details for school ID: <span className="font-mono">{id}</span>.
        Data will load from the API once the backend is connected.
      </p>

      {/* Tab navigation */}
      <div className="mt-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-6" aria-label="Tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium ${
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6">
        {activeTab === "Overview" && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Overview</h2>
            <p className="mt-2 text-gray-600">
              General information about the school: name, address, type, age
              range, gender policy, faith, Ofsted rating with inspection date,
              and catchment area displayed on a map.
            </p>
          </div>
        )}

        {activeTab === "Clubs" && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Breakfast &amp; After-School Clubs
            </h2>
            <p className="mt-2 text-gray-600">
              Listing of breakfast club availability, hours, and cost.
              After-school club options including sports, arts, and homework
              club. Days of the week and time ranges for each.
            </p>
          </div>
        )}

        {activeTab === "Performance" && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Performance &amp; Ratings
            </h2>
            <p className="mt-2 text-gray-600">
              Academic performance data: SATs results for primary schools,
              GCSE/A-level results for secondary schools. Progress 8 and
              Attainment 8 scores. Parent review summaries.
            </p>
          </div>
        )}

        {activeTab === "Term Dates" && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Term Dates</h2>
            <p className="mt-2 text-gray-600">
              Calendar view showing this school&apos;s term dates, half-term
              breaks, and holiday periods for the current and upcoming academic
              year.
            </p>
          </div>
        )}

        {activeTab === "Admissions" && (
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Admissions &amp; Waiting List
            </h2>
            <p className="mt-2 text-gray-600">
              Historical admissions data: last distance offered, trend analysis,
              waiting list movement, likelihood indicator based on your postcode
              distance. Appeals success rate where data is available.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
