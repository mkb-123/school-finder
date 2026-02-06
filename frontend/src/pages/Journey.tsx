import { useState } from "react";
import Map from "../components/Map";

const TRANSPORT_MODES = ["Walking", "Cycling", "Driving", "Public Transport"];

export default function Journey() {
  const [postcode, setPostcode] = useState("");
  const [mode, setMode] = useState("Walking");

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">
        School Run Planner
      </h1>
      <p className="mt-1 text-gray-600">
        Plan the school run with realistic travel time estimates. Times are
        calculated for drop-off (8:00-8:45am) and pick-up (5:00-5:30pm) to
        account for peak traffic conditions.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Controls */}
        <aside className="space-y-4 lg:col-span-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Route Settings
            </h2>

            <div className="mt-4 space-y-4">
              <div>
                <label
                  htmlFor="journeyPostcode"
                  className="block text-sm font-medium text-gray-700"
                >
                  Your Postcode
                </label>
                <input
                  id="journeyPostcode"
                  type="text"
                  placeholder="e.g. MK9 1AB"
                  value={postcode}
                  onChange={(e) => setPostcode(e.target.value.toUpperCase())}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Transport Mode
                </label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {TRANSPORT_MODES.map((m) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                        mode === m
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Travel time cards */}
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Travel Times
            </h2>
            <p className="mt-1 text-xs text-gray-500">
              Estimated times at peak hours
            </p>

            <div className="mt-4 space-y-3">
              {[
                {
                  name: "Example Primary School",
                  dropoff: "8 min",
                  pickup: "10 min",
                },
                {
                  name: "Example Secondary Academy",
                  dropoff: "22 min",
                  pickup: "25 min",
                },
                {
                  name: "Example Free School",
                  dropoff: "15 min",
                  pickup: "18 min",
                },
              ].map((school) => (
                <div
                  key={school.name}
                  className="rounded-md border border-gray-100 bg-gray-50 p-3"
                >
                  <p className="text-sm font-medium text-gray-900">
                    {school.name}
                  </p>
                  <div className="mt-1 flex gap-4 text-xs text-gray-500">
                    <span>
                      Drop-off:{" "}
                      <span className="font-semibold text-gray-700">
                        {school.dropoff}
                      </span>
                    </span>
                    <span>
                      Pick-up:{" "}
                      <span className="font-semibold text-gray-700">
                        {school.pickup}
                      </span>
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-4 text-xs text-gray-400">
              Note: parking difficulties and drop-off restrictions will be
              flagged for schools with known issues.
            </p>
          </div>
        </aside>

        {/* Map with route overlay */}
        <section className="h-[500px] lg:col-span-8 lg:h-auto lg:min-h-[600px]">
          <Map />
        </section>
      </div>
    </main>
  );
}
