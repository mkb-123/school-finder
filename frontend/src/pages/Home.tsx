import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapPin, GitCompareArrows, Clock, Search, ChevronRight } from "lucide-react";
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
  const [councilTouched, setCouncilTouched] = useState(false);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setCouncilTouched(true);
    if (!council) return;
    const params = new URLSearchParams({ council });
    if (postcode) params.set("postcode", postcode);
    navigate(`/schools?${params.toString()}`);
  }

  const showCouncilError = councilTouched && !council;

  return (
    <main className="mx-auto max-w-2xl px-4 py-10 sm:py-16" role="main">
      {/* Hero */}
      <div className="text-center">
        <h1 className="font-display text-3xl font-bold tracking-tight text-stone-900 sm:text-5xl">
          Find the right school for your child
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-stone-600 sm:text-lg">
          Search schools near you, compare Ofsted ratings, check catchment areas,
          and explore breakfast and after-school clubs — all in one place.
        </p>
      </div>

      {/* Search form */}
      <form
        onSubmit={handleSearch}
        className="mt-8 rounded-xl border border-stone-200 bg-white p-5 shadow-sm sm:mt-10 sm:p-8"
        aria-label="School search form"
      >
        <div className="space-y-5">
          <div>
            <label
              htmlFor="council"
              className="block text-sm font-medium text-stone-900"
            >
              Your council area
              <span className="ml-1 text-red-500" aria-hidden="true">*</span>
              <span className="sr-only">(required)</span>
            </label>
            <select
              id="council"
              value={council}
              onChange={(e) => {
                setCouncil(e.target.value);
                setCouncilTouched(true);
              }}
              onBlur={() => setCouncilTouched(true)}
              aria-required="true"
              aria-invalid={showCouncilError}
              aria-describedby={showCouncilError ? "council-error" : undefined}
              className={`mt-1.5 block w-full rounded-lg border bg-white px-3 py-3 text-base shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 ${
                showCouncilError
                  ? "border-red-300 focus:border-red-500 focus:ring-red-500"
                  : "border-stone-300 focus:border-brand-500 focus:ring-brand-500"
              }`}
            >
              <option value="">Choose your council...</option>
              {COUNCILS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            {showCouncilError && (
              <p id="council-error" className="mt-1.5 text-sm text-red-600" role="alert">
                Please select your council area to search
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="postcode"
              className="block text-sm font-medium text-stone-900"
            >
              Your postcode
              <span className="ml-1.5 text-xs font-normal text-stone-500">(optional)</span>
            </label>
            <input
              id="postcode"
              type="text"
              placeholder="e.g. MK9 1AB"
              value={postcode}
              onChange={(e) => setPostcode(e.target.value.toUpperCase())}
              aria-describedby="postcode-hint"
              className="mt-1.5 block w-full rounded-lg border border-stone-300 px-3 py-3 text-base shadow-sm transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1"
            />
            <p id="postcode-hint" className="mt-1.5 text-xs text-stone-500">
              Add your postcode to see distances and catchment areas
            </p>
          </div>

          <button
            type="submit"
            disabled={!council}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-3.5 text-base font-semibold text-white shadow-sm transition-colors hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500"
          >
            <Search className="h-5 w-5" aria-hidden="true" />
            Find schools
          </button>
        </div>
      </form>

      {/* Feature highlights */}
      <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="group flex items-start gap-3 rounded-xl border border-stone-200 bg-white p-4 transition-shadow hover:shadow-sm">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <MapPin className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-stone-900">Catchment maps</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-stone-500">
              See which schools your address falls within on an interactive map.
            </p>
          </div>
        </div>
        <div className="group flex items-start gap-3 rounded-xl border border-stone-200 bg-white p-4 transition-shadow hover:shadow-sm">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-green-50 text-green-600">
            <GitCompareArrows className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-stone-900">Compare schools</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-stone-500">
              Put schools side by side to compare ratings, clubs, and results.
            </p>
          </div>
        </div>
        <div className="group flex items-start gap-3 rounded-xl border border-stone-200 bg-white p-4 transition-shadow hover:shadow-sm">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
            <Clock className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-stone-900">Journey planner</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-stone-500">
              Plan the school run with realistic drop-off and pick-up times.
            </p>
          </div>
        </div>
      </div>

      {/* SEND toggle - subtle, not prominent */}
      <details className="mt-8">
        <summary className="flex cursor-pointer items-center gap-2 text-sm text-stone-500 hover:text-stone-700">
          <ChevronRight className="h-4 w-4 transition-transform [[open]>&]:rotate-90" aria-hidden="true" />
          Additional settings
        </summary>
        <div className="mt-3 rounded-lg border border-stone-200 bg-white p-4">
          <SendToggle />
        </div>
      </details>
    </main>
  );
}
