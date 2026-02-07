import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "school-finder-send-enabled";

/** Read SEND toggle state from localStorage. */
export function isSendEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

/** Custom hook to track SEND enabled state with localStorage persistence. */
export function useSendEnabled(): [boolean, (v: boolean) => void] {
  const [enabled, setEnabled] = useState(isSendEnabled);

  const toggle = useCallback((value: boolean) => {
    setEnabled(value);
    try {
      localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
      /* localStorage may be unavailable */
    }
    // Dispatch a storage event so other components pick up the change
    window.dispatchEvent(new Event("send-toggle-changed"));
  }, []);

  // Listen for changes from other components
  useEffect(() => {
    function onChanged() {
      setEnabled(isSendEnabled());
    }
    window.addEventListener("send-toggle-changed", onChanged);
    return () => window.removeEventListener("send-toggle-changed", onChanged);
  }, []);

  return [enabled, toggle];
}

/** SEND information panel shown when the toggle is enabled. */
export function SendInfoPanel({
  senProvision,
  ehcpFriendly,
  accessibilityInfo,
  specialistUnit,
}: {
  senProvision?: string | null;
  ehcpFriendly?: boolean | null;
  accessibilityInfo?: string | null;
  specialistUnit?: string | null;
}) {
  return (
    <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-purple-900">
        SEND Provision
      </h3>
      <p className="mt-0.5 text-xs text-purple-700">
        Special Educational Needs and Disabilities support at this school
      </p>
      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-4">
          <dt className="font-medium text-purple-700">SEN Provision Type</dt>
          <dd className="text-purple-900">
            {senProvision ?? "Not specified"}
          </dd>
        </div>
        <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-4">
          <dt className="font-medium text-purple-700">EHCP-Friendly</dt>
          <dd className="text-purple-900">
            {ehcpFriendly == null
              ? "Not specified"
              : ehcpFriendly
                ? "Yes"
                : "No"}
          </dd>
        </div>
        <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-4">
          <dt className="font-medium text-purple-700">Accessibility</dt>
          <dd className="text-purple-900">
            {accessibilityInfo ?? "Not specified"}
          </dd>
        </div>
        <div className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-4">
          <dt className="font-medium text-purple-700">Specialist Unit</dt>
          <dd className="text-purple-900">
            {specialistUnit ?? "Not available"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export default function SendToggle() {
  const [enabled, toggle] = useSendEnabled();

  return (
    <div>
      {/* Toggle with adequate touch target */}
      <label className="flex cursor-pointer items-center gap-3 rounded-lg p-1 -m-1">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label="Toggle SEND information display"
          onClick={() => toggle(!enabled)}
          className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 ${
            enabled ? "bg-purple-600" : "bg-gray-300"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow-sm ring-0 transition-transform ${
              enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
        <span className="text-sm font-medium text-gray-700">Show SEND information</span>
      </label>

      {/* Explanation for parents who may not know SEND */}
      {!enabled && (
        <p className="mt-2 text-xs text-gray-500 ml-[3.75rem]">
          Enable to see Special Educational Needs and Disabilities provision details on school pages.
        </p>
      )}

      {enabled && (
        <div className="mt-3 rounded-lg bg-purple-50 border border-purple-200 p-3 text-xs text-purple-700">
          <p className="font-medium text-purple-800">SEND information is now visible</p>
          <p className="mt-1">
            SEND (Special Educational Needs and Disabilities) details are
            now shown on school pages, including SEN provision
            type, EHCP-friendly flags, accessibility info, and specialist unit
            availability.
          </p>
        </div>
      )}
    </div>
  );
}
