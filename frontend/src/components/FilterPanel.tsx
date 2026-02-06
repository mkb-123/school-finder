import { useState } from "react";
import SendToggle from "./SendToggle";

export default function FilterPanel() {
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [schoolType, setSchoolType] = useState("");
  const [minRating, setMinRating] = useState("");
  const [maxDistance, setMaxDistance] = useState("");
  const [hasBreakfastClub, setHasBreakfastClub] = useState(false);
  const [hasAfterSchoolClub, setHasAfterSchoolClub] = useState(false);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
      <p className="mt-1 text-xs text-gray-500">
        Set constraints to narrow your results.
      </p>

      <div className="mt-4 space-y-4">
        {/* Child's age */}
        <div>
          <label
            htmlFor="filter-age"
            className="block text-sm font-medium text-gray-700"
          >
            Child&apos;s Age
          </label>
          <select
            id="filter-age"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="4">4 (Reception)</option>
            <option value="5">5 (Year 1)</option>
            <option value="6">6 (Year 2)</option>
            <option value="7">7 (Year 3)</option>
            <option value="8">8 (Year 4)</option>
            <option value="9">9 (Year 5)</option>
            <option value="10">10 (Year 6)</option>
            <option value="11">11 (Year 7)</option>
            <option value="12">12 (Year 8)</option>
            <option value="13">13 (Year 9)</option>
            <option value="14">14 (Year 10)</option>
            <option value="15">15 (Year 11)</option>
            <option value="16">16 (Year 12)</option>
            <option value="17">17 (Year 13)</option>
          </select>
        </div>

        {/* Gender */}
        <div>
          <label
            htmlFor="filter-gender"
            className="block text-sm font-medium text-gray-700"
          >
            Child&apos;s Gender
          </label>
          <select
            id="filter-gender"
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>

        {/* School type */}
        <div>
          <label
            htmlFor="filter-type"
            className="block text-sm font-medium text-gray-700"
          >
            School Type
          </label>
          <select
            id="filter-type"
            value={schoolType}
            onChange={(e) => setSchoolType(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="state">State</option>
            <option value="academy">Academy</option>
            <option value="free">Free School</option>
            <option value="faith">Faith School</option>
          </select>
        </div>

        {/* Ofsted rating */}
        <div>
          <label
            htmlFor="filter-rating"
            className="block text-sm font-medium text-gray-700"
          >
            Minimum Ofsted Rating
          </label>
          <select
            id="filter-rating"
            value={minRating}
            onChange={(e) => setMinRating(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Any</option>
            <option value="outstanding">Outstanding</option>
            <option value="good">Good</option>
            <option value="requires_improvement">Requires Improvement</option>
          </select>
        </div>

        {/* Distance */}
        <div>
          <label
            htmlFor="filter-distance"
            className="block text-sm font-medium text-gray-700"
          >
            Max Distance (miles)
          </label>
          <input
            id="filter-distance"
            type="number"
            placeholder="e.g. 3"
            value={maxDistance}
            onChange={(e) => setMaxDistance(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Club filters */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">Clubs</p>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={hasBreakfastClub}
              onChange={(e) => setHasBreakfastClub(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600"
            />
            Has breakfast club
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={hasAfterSchoolClub}
              onChange={(e) => setHasAfterSchoolClub(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600"
            />
            Has after-school club
          </label>
        </div>

        {/* SEND toggle */}
        <div className="border-t border-gray-200 pt-4">
          <SendToggle />
        </div>
      </div>
    </div>
  );
}
