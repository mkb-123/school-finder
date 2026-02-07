import { useState } from "react";

interface ParkingRatingFormProps {
  schoolId: number;
  onSubmitSuccess: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const RATING_FIELDS = [
  {
    field: "dropoff_chaos" as const,
    label: "Drop-off experience",
    description: "How stressful is the morning drop-off? (1 = calm, 5 = chaotic)",
  },
  {
    field: "pickup_chaos" as const,
    label: "Pick-up experience",
    description: "How stressful is the afternoon pick-up? (1 = calm, 5 = chaotic)",
  },
  {
    field: "parking_availability" as const,
    label: "Parking availability",
    description: "How easy is it to find parking nearby? (1 = easy, 5 = very hard)",
  },
  {
    field: "road_congestion" as const,
    label: "Road congestion",
    description: "How bad is traffic on surrounding roads? (1 = clear, 5 = gridlocked)",
  },
  {
    field: "restrictions_hazards" as const,
    label: "Safety concerns",
    description: "Are there restrictions, hazards, or safety issues? (1 = safe, 5 = concerning)",
  },
];

const RATING_LABELS: Record<number, string> = {
  0: "Not rated",
  1: "Easy",
  2: "Manageable",
  3: "Moderate",
  4: "Difficult",
  5: "Very difficult",
};

export default function ParkingRatingForm({ schoolId, onSubmitSuccess }: ParkingRatingFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    dropoff_chaos: 0,
    pickup_chaos: 0,
    parking_availability: 0,
    road_congestion: 0,
    restrictions_hazards: 0,
    comments: "",
    parent_email: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Check that at least one rating has been provided
    const hasRating = RATING_FIELDS.some(({ field }) => formData[field] > 0);
    if (!hasRating) {
      setError("Please rate at least one category before submitting.");
      return;
    }

    setIsSubmitting(true);

    // Only include ratings that have been set (non-zero)
    const payload = {
      school_id: schoolId,
      dropoff_chaos: formData.dropoff_chaos || null,
      pickup_chaos: formData.pickup_chaos || null,
      parking_availability: formData.parking_availability || null,
      road_congestion: formData.road_congestion || null,
      restrictions_hazards: formData.restrictions_hazards || null,
      comments: formData.comments || null,
      parent_email: formData.parent_email || null,
    };

    try {
      const response = await fetch(`${API_BASE}/api/parking-ratings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to submit rating");
      }

      setSuccess(true);
      setTimeout(() => {
        onSubmitSuccess();
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderRatingInput = (
    label: string,
    field: keyof typeof formData,
    description: string
  ) => {
    const value = formData[field] as number;
    return (
      <fieldset className="space-y-2">
        <legend className="block text-sm font-medium text-gray-900">{label}</legend>
        <p className="text-xs text-gray-500">{description}</p>
        <div className="flex items-center gap-2">
          {[1, 2, 3, 4, 5].map((rating) => (
            <button
              key={rating}
              type="button"
              onClick={() => setFormData({ ...formData, [field]: rating })}
              aria-label={`Rate ${label} as ${rating} out of 5`}
              className={`flex h-11 w-11 items-center justify-center rounded-full border-2 text-sm font-semibold transition-all ${
                value === rating
                  ? rating <= 2
                    ? "border-green-500 bg-green-500 text-white shadow-sm"
                    : rating <= 3
                    ? "border-amber-500 bg-amber-500 text-white shadow-sm"
                    : "border-red-500 bg-red-500 text-white shadow-sm"
                  : "border-gray-200 text-gray-600 hover:border-gray-400 hover:bg-gray-50"
              }`}
            >
              {rating}
            </button>
          ))}
          <span className="ml-2 text-xs font-medium text-gray-500">
            {RATING_LABELS[value]}
          </span>
        </div>
      </fieldset>
    );
  };

  if (success) {
    return (
      <div className="flex flex-col items-center rounded-xl border border-green-200 bg-green-50 py-8 px-6 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
          <svg
            className="h-7 w-7 text-green-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h3 className="mt-4 text-base font-semibold text-green-900">Thank you for your feedback</h3>
        <p className="mt-1.5 text-sm text-green-700">
          Your parking rating has been submitted and will help other parents.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <p className="text-sm text-blue-900">
          Help other parents by sharing your experience with parking and drop-off at this school.
          All ratings are anonymous.
        </p>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4" role="alert">
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {RATING_FIELDS.map(({ field, label, description }) =>
        renderRatingInput(label, field, description)
      )}

      <div>
        <label htmlFor="parking-comments" className="block text-sm font-medium text-gray-900">
          Additional comments (optional)
        </label>
        <textarea
          id="parking-comments"
          value={formData.comments}
          onChange={(e) => setFormData({ ...formData, comments: e.target.value })}
          rows={4}
          className="mt-2 w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          placeholder="Share any specific details about parking challenges, helpful tips, or safety concerns..."
        />
      </div>

      <div>
        <label htmlFor="parking-email" className="block text-sm font-medium text-gray-900">
          Email (optional)
        </label>
        <input
          id="parking-email"
          type="email"
          value={formData.parent_email}
          onChange={(e) => setFormData({ ...formData, parent_email: e.target.value })}
          className="mt-2 w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          placeholder="your.email@example.com"
        />
        <p className="mt-1.5 text-xs text-gray-500">
          Your email is only used if we need to follow up on your feedback. It is never shared or displayed publicly.
        </p>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? "Submitting..." : "Submit Rating"}
      </button>
    </form>
  );
}
