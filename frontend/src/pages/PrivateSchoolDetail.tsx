import { useParams } from "react-router-dom";

export default function PrivateSchoolDetail() {
  const { id } = useParams<{ id: string }>();

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900">
        Private School Detail
      </h1>
      <p className="mt-1 text-gray-600">
        Viewing details for private school ID:{" "}
        <span className="font-mono">{id}</span>. Data will load from the API
        once the backend is connected.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Fees */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">Fees</h2>
          <p className="mt-2 text-gray-600">
            Termly and annual fee breakdowns by age group. Bursary and
            scholarship information where available.
          </p>
          <div className="mt-4 space-y-2">
            <div className="flex justify-between border-b border-gray-100 py-2 text-sm">
              <span className="text-gray-500">Pre-prep (termly)</span>
              <span className="font-medium text-gray-900">--</span>
            </div>
            <div className="flex justify-between border-b border-gray-100 py-2 text-sm">
              <span className="text-gray-500">Prep (termly)</span>
              <span className="font-medium text-gray-900">--</span>
            </div>
            <div className="flex justify-between border-b border-gray-100 py-2 text-sm">
              <span className="text-gray-500">Senior (termly)</span>
              <span className="font-medium text-gray-900">--</span>
            </div>
          </div>
        </section>

        {/* School hours */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">School Hours</h2>
          <p className="mt-2 text-gray-600">
            School day start and end times, extended day options, and wraparound
            care availability.
          </p>
        </section>

        {/* Transport */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">Transport</h2>
          <p className="mt-2 text-gray-600">
            Whether the school provides transport, routes covered, eligibility
            criteria, and costs.
          </p>
        </section>

        {/* Term dates */}
        <section className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-xl font-semibold text-gray-900">
            Holiday Schedule
          </h2>
          <p className="mt-2 text-gray-600">
            Term dates, half-terms, and holiday lengths. Private schools often
            have different term dates from state schools.
          </p>
        </section>

        {/* General info */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 md:col-span-2">
          <h2 className="text-xl font-semibold text-gray-900">
            General Information
          </h2>
          <p className="mt-2 text-gray-600">
            Address, age range, gender policy, ISI/Ofsted inspection results,
            and parent review summaries.
          </p>
        </section>
      </div>
    </main>
  );
}
