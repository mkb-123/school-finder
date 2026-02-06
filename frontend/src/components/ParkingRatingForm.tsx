import { useState } from "react";

interface ParkingRatingFormProps {
  schoolId: number;
  onSubmitSuccess: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">{label}</label>
        <p className="text-xs text-gray-500">{description}</p>
        <div className="flex items-center gap-2">
          {[1, 2, 3, 4, 5].map((rating) => (
            <button
              key={rating}
              type="button"
              onClick={() => setFormData({ ...formData, [field]: rating })}
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-medium transition ${
                value === rating
                  ? rating <= 2
                    ? "border-green-500 bg-green-500 text-white"
                    : rating <= 3
                    ? "border-amber-500 bg-amber-500 text-white"
                    : "border-red-500 bg-red-500 text-white"
                  : "border-gray-300 text-gray-600 hover:border-gray-400"
              }`}
            >
              {rating}
            </button>
          ))}
          <span className="ml-2 text-xs text-gray-500">
            {value === 0 ? "Not rated" : value <= 2 ? "Low chaos" : value <= 3 ? "Moderate" : "High chaos"}
          </span>
        </div>
      </div>
    );
  };

  if (success) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
        <svg
          className="mx-auto h-12 w-12 text-green-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
        <h3 className="mt-4 text-lg font-semibold text-green-900">Thank you!</h3>
        <p className="mt-2 text-sm text-green-700">
          Your parking rating has been submitted successfully.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <p className="text-sm text-blue-900">
          Help other parents by sharing your experience with parking and drop-off at this school.
          Rate from 1 (easy/safe) to 5 (chaotic/difficult).
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          {error}
        </div>
      )}

      {renderRatingInput(
        "Drop-off chaos",
        "dropoff_chaos",
        "Morning drop-off congestion and stress level"
      )}

      {renderRatingInput(
        "Pick-up chaos",
        "pickup_chaos",
        "Afternoon pick-up congestion and wait times"
      )}

      {renderRatingInput(
        "Parking availability",
        "parking_availability",
        "How hard is it to find parking nearby?"
      )}

      {renderRatingInput(
        "Road congestion",
        "road_congestion",
        "Traffic congestion on surrounding roads"
      )}

      {renderRatingInput(
        "Restrictions & hazards",
        "restrictions_hazards",
        "Parking restrictions, safety concerns, or hazards"
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700">
          Additional comments (optional)
        </label>
        <textarea
          value={formData.comments}
          onChange={(e) => setFormData({ ...formData, comments: e.target.value })}
          rows={4}
          className="mt-2 w-full rounded-md border border-gray-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="Share any specific details about parking challenges, helpful tips, or safety concerns..."
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">
          Email (optional)
        </label>
        <input
          type="email"
          value={formData.parent_email}
          onChange={(e) => setFormData({ ...formData, parent_email: e.target.value })}
          className="mt-2 w-full rounded-md border border-gray-300 p-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="your.email@example.com"
        />
        <p className="mt-1 text-xs text-gray-500">
          Optional. Only used if we need to follow up on your feedback.
        </p>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-md bg-blue-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
      >
        {isSubmitting ? "Submitting..." : "Submit Rating"}
      </button>
    </form>
  );
}
