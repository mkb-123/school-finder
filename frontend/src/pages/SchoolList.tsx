import { useSearchParams } from "react-router-dom";
import FilterPanel from "../components/FilterPanel";
import SchoolCard from "../components/SchoolCard";
import Map from "../components/Map";

export default function SchoolList() {
  const [searchParams] = useSearchParams();
  const council = searchParams.get("council") ?? "";
  const postcode = searchParams.get("postcode") ?? "";

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">School Results</h1>
        <p className="mt-1 text-gray-600">
          {council && postcode
            ? `Showing schools near ${postcode} in ${council}`
            : "Search for schools by council and postcode from the home page."}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Filter sidebar */}
        <aside className="lg:col-span-3">
          <FilterPanel />
        </aside>

        {/* School cards */}
        <section className="space-y-4 lg:col-span-4">
          <p className="text-sm text-gray-500">
            School results will appear here once the backend is connected.
            Filters from the URL query parameters will be read and applied.
          </p>
          {/* Placeholder cards */}
          <SchoolCard
            name="Example Primary School"
            type="Primary"
            ofstedRating="Outstanding"
            distance="0.4 miles"
          />
          <SchoolCard
            name="Example Secondary Academy"
            type="Secondary"
            ofstedRating="Good"
            distance="1.2 miles"
          />
          <SchoolCard
            name="Example Free School"
            type="Primary"
            ofstedRating="Requires Improvement"
            distance="2.1 miles"
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
