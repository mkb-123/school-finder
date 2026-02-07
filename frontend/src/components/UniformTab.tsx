interface Uniform {
  id: number;
  school_id: number;
  description: string | null;
  style: string | null;
  colors: string | null;
  requires_specific_supplier: boolean;
  supplier_name: string | null;
  supplier_website: string | null;
  polo_shirts_cost: number | null;
  jumper_cost: number | null;
  trousers_skirt_cost: number | null;
  pe_kit_cost: number | null;
  bag_cost: number | null;
  coat_cost: number | null;
  other_items_cost: number | null;
  other_items_description: string | null;
  total_cost_estimate: number | null;
  is_expensive: boolean;
  notes: string | null;
}

interface CostItem {
  label: string;
  perItem: number;
  quantity: number;
  quantityLabel: string;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function UniformTab({ uniform }: { uniform: Uniform[] }) {
  if (uniform.length === 0) {
    return (
      <section className="rounded-xl border border-gray-200 bg-white p-5 sm:p-6" aria-labelledby="uniform-heading">
        <h2 id="uniform-heading" className="text-lg font-semibold text-gray-900">Uniform</h2>
        <div className="mt-4 flex items-center gap-3 rounded-lg bg-gray-50 p-4 text-sm text-gray-500">
          <svg className="h-5 w-5 flex-shrink-0 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          No uniform information available yet.
        </div>
      </section>
    );
  }

  const uni = uniform[0]; // Usually only one uniform entry per school

  // Build cost items list dynamically
  const costItems: CostItem[] = [];
  if (uni.polo_shirts_cost != null) {
    costItems.push({ label: "Polo Shirts", perItem: uni.polo_shirts_cost, quantity: 2, quantityLabel: "2 items" });
  }
  if (uni.jumper_cost != null) {
    costItems.push({ label: "Jumper / Sweatshirt", perItem: uni.jumper_cost, quantity: 2, quantityLabel: "2 items" });
  }
  if (uni.trousers_skirt_cost != null) {
    costItems.push({ label: "Trousers / Skirt", perItem: uni.trousers_skirt_cost, quantity: 2, quantityLabel: "2 items" });
  }
  if (uni.pe_kit_cost != null) {
    costItems.push({ label: "PE Kit", perItem: uni.pe_kit_cost, quantity: 1, quantityLabel: "1 set" });
  }
  if (uni.bag_cost != null) {
    costItems.push({ label: "School Bag", perItem: uni.bag_cost, quantity: 1, quantityLabel: "1 item" });
  }
  if (uni.coat_cost != null) {
    costItems.push({ label: "Coat", perItem: uni.coat_cost, quantity: 1, quantityLabel: "1 item" });
  }
  if (uni.other_items_cost != null) {
    costItems.push({
      label: uni.other_items_description || "Other Items",
      perItem: uni.other_items_cost,
      quantity: 1,
      quantityLabel: "",
    });
  }

  return (
    <div className="space-y-5">
      {/* Affordability indicator */}
      {uni.is_expensive ? (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4" role="alert">
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-sm font-semibold text-amber-900">Branded uniform required</p>
            <p className="mt-0.5 text-sm text-amber-800">
              This school requires items from a specific supplier. Total cost may be higher than schools that allow supermarket alternatives.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 p-4">
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-semibold text-green-900">Affordable uniform</p>
            <p className="mt-0.5 text-sm text-green-800">
              Supermarket or generic alternatives are acceptable. Parents can shop around for the best prices.
            </p>
          </div>
        </div>
      )}

      {/* Main uniform details card */}
      <section className="rounded-xl border border-gray-200 bg-white p-5 sm:p-6" aria-labelledby="uniform-detail-heading">
        <h2 id="uniform-detail-heading" className="text-lg font-semibold text-gray-900">Uniform Details</h2>

        <div className="mt-4 space-y-4">
          {uni.description && (
            <p className="text-sm leading-relaxed text-gray-700">{uni.description}</p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {uni.style && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Style</p>
                <p className="mt-1 text-sm text-gray-900">{uni.style}</p>
              </div>
            )}

            {uni.colors && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Colours</p>
                <p className="mt-1 text-sm text-gray-900">{uni.colors}</p>
              </div>
            )}
          </div>

          {uni.requires_specific_supplier && uni.supplier_name && (
            <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Supplier</p>
              <p className="mt-1 text-sm font-medium text-gray-900">{uni.supplier_name}</p>
              {uni.supplier_website && (
                <a
                  href={uni.supplier_website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1.5 inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
                >
                  Visit supplier website
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              )}
            </div>
          )}

          {uni.notes && (
            <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
              <p className="text-sm text-gray-700">{uni.notes}</p>
            </div>
          )}
        </div>
      </section>

      {/* Cost breakdown card */}
      {costItems.length > 0 && (
        <section className="rounded-xl border border-gray-200 bg-white p-5 sm:p-6" aria-labelledby="uniform-cost-heading">
          <h2 id="uniform-cost-heading" className="text-lg font-semibold text-gray-900">Cost Breakdown</h2>
          <p className="mt-1 text-sm text-gray-500">
            Estimated costs for a full uniform set (typical quantities for a year)
          </p>

          <div className="mt-4 divide-y divide-gray-100">
            {costItems.map((item) => (
              <div key={item.label} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{item.label}</p>
                  <p className="text-xs text-gray-500">
                    {item.quantityLabel}
                    {item.quantity > 1 && ` at ${formatCurrency(item.perItem)} each`}
                  </p>
                </div>
                <p className="text-sm font-semibold text-gray-900">
                  {formatCurrency(item.perItem * item.quantity)}
                </p>
              </div>
            ))}

            {/* Total */}
            {uni.total_cost_estimate != null && (
              <div className="flex items-center justify-between pt-4">
                <p className="text-base font-bold text-gray-900">Total Estimate</p>
                <div className="text-right">
                  <p className="text-xl font-bold text-gray-900">
                    {formatCurrency(uni.total_cost_estimate)}
                  </p>
                </div>
              </div>
            )}
          </div>

          <p className="mt-4 text-xs text-gray-500">
            Costs are estimates and may vary. Always check with the school or supplier for current prices.
          </p>
        </section>
      )}
    </div>
  );
}

export default UniformTab;
