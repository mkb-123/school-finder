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
    if (!council) return;
    const params = new URLSearchParams({ council });
    if (postcode) params.set("postcode", postcode);
    navigate(`/schools?${params.toString()}`);
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:py-20" role="main">
      <div className="text-center">
        <h1 className="font-display text-4xl tracking-tight text-stone-900 sm:text-5xl">
          Find the right school
          <span className="block text-brand-600">for your family</span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-base text-stone-500 sm:text-lg">
          Search by postcode to see distances, Ofsted ratings, clubs, and
          catchment areas. Compare schools side-by-side and plan the school run.
        </p>
      </div>

      <form
        onSubmit={handleSearch}
        className="mt-10 overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-md sm:mt-12"
        aria-label="School search form"
      >
        <div className="p-5 sm:p-8">
          <div className="space-y-5">
            <div>
              <label
                htmlFor="council"
                className="block text-sm font-medium text-stone-700"
              >
                Council area
              </label>
              <select
                id="council"
                value={council}
                onChange={(e) => setCouncil(e.target.value)}
                className="mt-1.5 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-stone-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
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
                className="block text-sm font-medium text-stone-700"
              >
                Postcode{" "}
                <span className="font-normal text-stone-400">(optional)</span>
              </label>
              <input
                id="postcode"
                type="text"
                placeholder="e.g. MK9 1AB"
                value={postcode}
                onChange={(e) => setPostcode(e.target.value.toUpperCase())}
                className="mt-1.5 block w-full rounded-lg border border-stone-300 px-3 py-2.5 text-stone-900 shadow-sm placeholder:text-stone-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <p className="mt-1.5 text-xs text-stone-400">
                Enter a postcode to sort schools by distance and see catchment areas
              </p>
            </div>
          </div>
        </div>

        <div className="border-t border-stone-100 bg-stone-50 px-5 py-4 sm:px-8">
          <button
            type="submit"
            disabled={!council}
            className="w-full rounded-lg bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Search schools
          </button>
        </div>
      </form>

      {/* Settings */}
      <div className="mt-8 rounded-xl border border-stone-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-stone-700">Settings</h2>
        <div className="mt-3">
          <SendToggle />
        </div>
      </div>

      <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="rounded-xl border border-stone-200 bg-white p-5">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50">
            <svg className="h-5 w-5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <h3 className="font-semibold text-stone-900">Catchment maps</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-stone-500">
            See which schools cover your area with interactive catchment
            boundaries.
          </p>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-5">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50">
            <svg className="h-5 w-5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
            </svg>
          </div>
          <h3 className="font-semibold text-stone-900">Compare schools</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-stone-500">
            Side-by-side comparison of ratings, clubs, term dates, and more.
          </p>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-5">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50">
            <svg className="h-5 w-5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="font-semibold text-stone-900">Journey planner</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-stone-500">
            Plan the school run with realistic drop-off and pick-up travel
            times.
          </p>
        </div>
      </div>
    </main>
  );
}
