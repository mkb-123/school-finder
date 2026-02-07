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

function UniformTab({ uniform }: { uniform: Uniform[] }) {
  if (uniform.length === 0) {
    return (
      <div className="rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-stone-900">Uniform Cost & Appearance</h2>
        <p className="mt-2 text-stone-600">No uniform information available yet.</p>
      </div>
    );
  }

  const uni = uniform[0]; // Usually only one uniform entry per school

  return (
    <div className="space-y-6">
      {/* Affordability indicator */}
      {uni.is_expensive && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-3">
            <svg className="h-6 w-6 flex-shrink-0 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-amber-900">Expensive Branded Uniform</p>
              <p className="mt-1 text-sm text-amber-800">
                This school requires items to be purchased from a specific supplier. Total cost may be higher than schools that allow supermarket alternatives.
              </p>
            </div>
          </div>
        </div>
      )}

      {!uni.is_expensive && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <div className="flex items-start gap-3">
            <svg className="h-6 w-6 flex-shrink-0 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-green-900">Affordable Uniform</p>
              <p className="mt-1 text-sm text-green-800">
                Supermarket or generic alternatives are acceptable for this school. Parents can shop around for the best prices.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main uniform details card */}
      <div className="rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-stone-900">Uniform Details</h2>

        <div className="mt-4 space-y-4">
          {uni.description && (
            <div>
              <h3 className="text-sm font-medium text-stone-700">Description</h3>
              <p className="mt-1 text-stone-900">{uni.description}</p>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {uni.style && (
              <div>
                <h3 className="text-sm font-medium text-stone-700">Style</h3>
                <p className="mt-1 text-stone-900">{uni.style}</p>
              </div>
            )}

            {uni.colors && (
              <div>
                <h3 className="text-sm font-medium text-stone-700">Colors</h3>
                <p className="mt-1 text-stone-900">{uni.colors}</p>
              </div>
            )}
          </div>

          {uni.requires_specific_supplier && uni.supplier_name && (
            <div>
              <h3 className="text-sm font-medium text-stone-700">Supplier</h3>
              <p className="mt-1 text-stone-900">{uni.supplier_name}</p>
              {uni.supplier_website && (
                <a
                  href={uni.supplier_website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800"
                >
                  Visit supplier website
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              )}
            </div>
          )}

          {uni.notes && (
            <div className="rounded-md bg-stone-50 p-3">
              <p className="text-sm text-stone-700">{uni.notes}</p>
            </div>
          )}
        </div>
      </div>

      {/* Cost breakdown card */}
      <div className="rounded-lg border border-stone-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-stone-900">Cost Breakdown</h2>
        <p className="mt-1 text-sm text-stone-600">
          Estimated costs for a full uniform set (quantities shown are typical for a year)
        </p>

        <div className="mt-4 space-y-3">
          {uni.polo_shirts_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">Polo Shirts</p>
                <p className="text-xs text-stone-500">2 items</p>
              </div>
              <p className="text-stone-900">&pound;{(uni.polo_shirts_cost * 2).toFixed(2)}</p>
            </div>
          )}

          {uni.jumper_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">Jumper/Sweatshirt</p>
                <p className="text-xs text-stone-500">2 items</p>
              </div>
              <p className="text-stone-900">&pound;{(uni.jumper_cost * 2).toFixed(2)}</p>
            </div>
          )}

          {uni.trousers_skirt_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">Trousers/Skirt</p>
                <p className="text-xs text-stone-500">2 items</p>
              </div>
              <p className="text-stone-900">&pound;{(uni.trousers_skirt_cost * 2).toFixed(2)}</p>
            </div>
          )}

          {uni.pe_kit_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">PE Kit</p>
                <p className="text-xs text-stone-500">1 set</p>
              </div>
              <p className="text-stone-900">&pound;{uni.pe_kit_cost.toFixed(2)}</p>
            </div>
          )}

          {uni.bag_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">School Bag</p>
                <p className="text-xs text-stone-500">1 item</p>
              </div>
              <p className="text-stone-900">&pound;{uni.bag_cost.toFixed(2)}</p>
            </div>
          )}

          {uni.coat_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">Coat</p>
                <p className="text-xs text-stone-500">1 item</p>
              </div>
              <p className="text-stone-900">&pound;{uni.coat_cost.toFixed(2)}</p>
            </div>
          )}

          {uni.other_items_cost != null && (
            <div className="flex items-center justify-between border-b border-stone-100 pb-2">
              <div>
                <p className="font-medium text-stone-900">Other Items</p>
                {uni.other_items_description && (
                  <p className="text-xs text-stone-500">{uni.other_items_description}</p>
                )}
              </div>
              <p className="text-stone-900">&pound;{uni.other_items_cost.toFixed(2)}</p>
            </div>
          )}

          {/* Total */}
          {uni.total_cost_estimate != null && (
            <div className="flex items-center justify-between border-t-2 border-stone-300 pt-3">
              <p className="text-lg font-semibold text-stone-900">Total Estimate</p>
              <p className="text-lg font-bold text-stone-900">&pound;{uni.total_cost_estimate.toFixed(2)}</p>
            </div>
          )}
        </div>

        <p className="mt-4 text-xs text-stone-500">
          Costs are estimates and may vary. Always check with the school or supplier for current prices.
        </p>
      </div>
    </div>
  );
}

export default UniformTab;
