import { useState } from "react";
import { useNavigate } from "react-router-dom";
import SendToggle from "../components/SendToggle";

const COUNCILS = [
  "Milton Keynes",
  "Bedford Borough",
  "Central Bedfordshire",
  "Buckinghamshire",
  "Northamptonshire",
];

export default function Home() {
  const navigate = useNavigate();
  const [council, setCouncil] = useState("");
  const [postcode, setPostcode] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!council || !postcode) return;
    const params = new URLSearchParams({ council, postcode });
    navigate(`/schools?${params.toString()}`);
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:py-16" role="main">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          School Finder
        </h1>
        <p className="mt-4 text-base text-gray-600 sm:text-lg">
          Find and compare schools in your local council area. Search by
          postcode to discover schools in your catchment, view Ofsted ratings,
          explore clubs, and plan the school run.
        </p>
      </div>

      <form
        onSubmit={handleSearch}
        className="mt-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:mt-10 sm:p-6"
        aria-label="School search form"
      >
        <div className="space-y-4">
          <div>
            <label
              htmlFor="council"
              className="block text-sm font-medium text-gray-700"
            >
              Council
            </label>
            <select
              id="council"
              value={council}
              onChange={(e) => setCouncil(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select a council...</option>
              {COUNCILS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="postcode"
              className="block text-sm font-medium text-gray-700"
            >
              Postcode
            </label>
            <input
              id="postcode"
              type="text"
              placeholder="e.g. MK9 1AB"
              value={postcode}
              onChange={(e) => setPostcode(e.target.value.toUpperCase())}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <button
            type="submit"
            disabled={!council || !postcode}
            className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Search Schools
          </button>
        </div>
      </form>

      {/* Settings */}
      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-gray-900">Settings</h2>
        <div className="mt-3">
          <SendToggle />
        </div>
      </div>

      <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <h3 className="font-semibold text-gray-900">Catchment Maps</h3>
          <p className="mt-1 text-sm text-gray-500">
            See which schools cover your area with interactive catchment
            boundaries.
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <h3 className="font-semibold text-gray-900">Compare Schools</h3>
          <p className="mt-1 text-sm text-gray-500">
            Side-by-side comparison of ratings, clubs, term dates, and more.
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <h3 className="font-semibold text-gray-900">Journey Planner</h3>
          <p className="mt-1 text-sm text-gray-500">
            Plan the school run with realistic drop-off and pick-up travel
            times.
          </p>
        </div>
      </div>
    </main>
  );
}
