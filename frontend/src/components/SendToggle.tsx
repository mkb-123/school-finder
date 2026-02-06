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
    <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
      <h3 className="text-sm font-semibold text-purple-900">
        SEND Provision
      </h3>
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-purple-700">SEN Provision Type</dt>
          <dd className="font-medium text-purple-900">
            {senProvision ?? "Not specified"}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-purple-700">EHCP-Friendly</dt>
          <dd className="font-medium text-purple-900">
            {ehcpFriendly == null
              ? "Not specified"
              : ehcpFriendly
                ? "Yes"
                : "No"}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-purple-700">Accessibility</dt>
          <dd className="font-medium text-purple-900">
            {accessibilityInfo ?? "Not specified"}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-purple-700">Specialist Unit</dt>
          <dd className="font-medium text-purple-900">
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
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label="Toggle SEND information display"
          onClick={() => toggle(!enabled)}
          className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 ${
            enabled ? "bg-purple-600" : "bg-gray-200"
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
        <div className="mt-3 rounded-md bg-purple-50 p-3 text-xs text-purple-700">
          <p className="font-medium">SEND Provision Filters Active</p>
          <p className="mt-1">
            SEND (Special Educational Needs &amp; Disabilities) information is
            now visible on school detail pages. This includes SEN provision
            type, EHCP-friendly flags, accessibility info, and specialist unit
            availability.
          </p>
        </div>
      )}
    </div>
  );
}
