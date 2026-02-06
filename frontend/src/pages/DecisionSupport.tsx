import { useState } from "react";

interface Weights {
  distance: number;
  ofstedRating: number;
  clubs: number;
  performance: number;
  admissions: number;
}

const DEFAULT_WEIGHTS: Weights = {
  distance: 50,
  ofstedRating: 50,
  clubs: 50,
  performance: 50,
  admissions: 50,
};

export default function DecisionSupport() {
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);

  function handleWeightChange(key: keyof Weights, value: number) {
    setWeights((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">Decision Support</h1>
      <p className="mt-1 text-gray-600">
        Weigh up your options with personalised scoring. Set what matters most to
        your family and see schools ranked by a composite score. Explore
        &quot;what if&quot; scenarios and build a shortlist.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Priority sliders */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 lg:col-span-1">
          <h2 className="text-lg font-semibold text-gray-900">
            Your Priorities
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Adjust sliders to set how important each factor is.
          </p>

          <div className="mt-6 space-y-5">
            {(
              [
                ["distance", "Distance"],
                ["ofstedRating", "Ofsted Rating"],
                ["clubs", "Clubs & Wraparound Care"],
                ["performance", "Academic Performance"],
                ["admissions", "Admissions Likelihood"],
              ] as [keyof Weights, string][]
            ).map(([key, label]) => (
              <div key={key}>
                <div className="flex justify-between text-sm">
                  <label htmlFor={key} className="font-medium text-gray-700">
                    {label}
                  </label>
                  <span className="text-gray-500">{weights[key]}%</span>
                </div>
                <input
                  id={key}
                  type="range"
                  min={0}
                  max={100}
                  value={weights[key]}
                  onChange={(e) =>
                    handleWeightChange(key, Number(e.target.value))
                  }
                  className="mt-1 w-full"
                />
              </div>
            ))}
          </div>

          {/* What-if controls */}
          <div className="mt-8 border-t border-gray-200 pt-6">
            <h3 className="text-sm font-semibold text-gray-900">
              &quot;What If&quot; Scenarios
            </h3>
            <p className="mt-1 text-xs text-gray-500">
              Adjust constraints to see how results change.
            </p>
            <div className="mt-3 space-y-2">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                OK with a 15 min drive
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                Drop min Ofsted to Good
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                Include faith schools
              </label>
            </div>
          </div>
        </section>

        {/* Ranked results & pros/cons */}
        <section className="space-y-6 lg:col-span-2">
          {/* Shortlist */}
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Ranked Schools
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Schools ranked by your personalised composite score. Click a school
              to see auto-generated pros and cons.
            </p>
            <div className="mt-4 rounded-md border-2 border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
              Ranked school list will appear here once data is loaded.
            </div>
          </div>

          {/* Pros / Cons */}
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Pros &amp; Cons
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Auto-generated bullet points for each school (e.g., &quot;Outstanding
              Ofsted but no breakfast club&quot;, &quot;10 min walk but Requires
              Improvement&quot;).
            </p>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-md bg-green-50 p-4">
                <h3 className="text-sm font-semibold text-green-800">Pros</h3>
                <ul className="mt-2 list-inside list-disc text-sm text-green-700">
                  <li>Example: Outstanding Ofsted rating</li>
                  <li>Example: Breakfast club available</li>
                </ul>
              </div>
              <div className="rounded-md bg-red-50 p-4">
                <h3 className="text-sm font-semibold text-red-800">Cons</h3>
                <ul className="mt-2 list-inside list-disc text-sm text-red-700">
                  <li>Example: No after-school club</li>
                  <li>Example: 2+ miles away</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Shortlist & export */}
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-gray-900">Shortlist</h2>
            <p className="mt-1 text-sm text-gray-500">
              Save schools to your shortlist (stored in local storage). Export
              your comparison as PDF or share via link.
            </p>
            <div className="mt-4 flex gap-3">
              <button className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                Export as PDF
              </button>
              <button className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                Share Link
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
