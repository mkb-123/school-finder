import { useState } from "react";

export default function SendToggle() {
  const [enabled, setEnabled] = useState(false);

  return (
    <div>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <button
          role="switch"
          aria-checked={enabled}
          onClick={() => setEnabled(!enabled)}
          className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
            enabled ? "bg-blue-600" : "bg-gray-200"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              enabled ? "translate-x-4" : "translate-x-0"
            }`}
          />
        </button>
        Show SEND information
      </label>

      {enabled && (
        <div className="mt-3 rounded-md bg-blue-50 p-3 text-xs text-blue-700">
          <p className="font-medium">SEND Provision Filters</p>
          <p className="mt-1">
            When enabled, SEND (Special Educational Needs &amp; Disabilities)
            information will be shown on school cards and detail pages. This
            includes EHCP-friendly flags, accessibility info, and specialist
            unit availability.
          </p>
        </div>
      )}
    </div>
  );
}
