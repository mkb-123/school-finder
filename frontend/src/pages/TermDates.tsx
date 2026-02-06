export default function TermDates() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">Term Dates</h1>
      <p className="mt-1 text-gray-600">
        Calendar view of term dates across schools. Compare term start/end
        dates, half-term breaks, and holiday periods. Academies and free schools
        may have different dates from council schools.
      </p>

      {/* Calendar placeholder */}
      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {["Autumn Term", "Spring Term", "Summer Term"].map((term) => (
          <div
            key={term}
            className="rounded-lg border border-gray-200 bg-white p-6"
          >
            <h2 className="text-lg font-semibold text-gray-900">{term}</h2>
            <div className="mt-4 space-y-3">
              <div>
                <p className="text-sm font-medium text-gray-700">Term Start</p>
                <p className="text-sm text-gray-500">--</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">Half Term</p>
                <p className="text-sm text-gray-500">--</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">Term End</p>
                <p className="text-sm text-gray-500">--</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* School comparison area */}
      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-gray-900">
          Compare Term Dates Across Schools
        </h2>
        <p className="mt-2 text-sm text-gray-500">
          Select schools to compare their term dates side by side. Differences
          will be highlighted to show where academy or free school dates diverge
          from council-set dates.
        </p>
        <div className="mt-4 rounded-md border-2 border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
          Calendar visualisation will render here when school term date data is
          available.
        </div>
      </div>
    </main>
  );
}
