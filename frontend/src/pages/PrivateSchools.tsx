import { useState } from "react";
import SchoolCard from "../components/SchoolCard";
import Map from "../components/Map";

export default function PrivateSchools() {
  const [maxFee, setMaxFee] = useState<string>("");

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Private Schools</h1>
        <p className="mt-1 text-gray-600">
          Browse independent and private schools in your area. Filter by fees,
          age range, transport availability, and more.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Fee filter sidebar */}
        <aside className="space-y-4 lg:col-span-3">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-gray-900">Filters</h2>

            <div className="mt-4 space-y-4">
              <div>
                <label
                  htmlFor="maxFee"
                  className="block text-sm font-medium text-gray-700"
                >
                  Max Termly Fee
                </label>
                <input
                  id="maxFee"
                  type="number"
                  placeholder="e.g. 5000"
                  value={maxFee}
                  onChange={(e) => setMaxFee(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label
                  htmlFor="ageRange"
                  className="block text-sm font-medium text-gray-700"
                >
                  Age Range
                </label>
                <select
                  id="ageRange"
                  className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Any</option>
                  <option value="3-7">3-7 (Pre-prep)</option>
                  <option value="7-11">7-11 (Prep)</option>
                  <option value="11-16">11-16 (Senior)</option>
                  <option value="16-18">16-18 (Sixth Form)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="gender"
                  className="block text-sm font-medium text-gray-700"
                >
                  Gender Policy
                </label>
                <select
                  id="gender"
                  className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Any</option>
                  <option value="co-ed">Co-educational</option>
                  <option value="boys">Boys only</option>
                  <option value="girls">Girls only</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <input
                  id="transport"
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-blue-600"
                />
                <label
                  htmlFor="transport"
                  className="text-sm text-gray-700"
                >
                  Provides transport
                </label>
              </div>
            </div>
          </div>
        </aside>

        {/* School cards */}
        <section className="space-y-4 lg:col-span-4">
          <p className="text-sm text-gray-500">
            Private school results will appear here. Fee breakdowns, school
            hours, and transport details are shown on each school&apos;s detail
            page.
          </p>
          <SchoolCard
            name="Example Independent School"
            type="Independent"
            ofstedRating="Good"
            distance="3.5 miles"
          />
          <SchoolCard
            name="Example Preparatory School"
            type="Preparatory"
            ofstedRating="Outstanding"
            distance="5.0 miles"
          />
        </section>

        {/* Map */}
        <section className="h-[500px] lg:col-span-5 lg:h-auto lg:min-h-[600px]">
          <Map />
        </section>
      </div>
    </main>
  );
}
