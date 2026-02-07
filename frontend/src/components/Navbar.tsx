import { useState } from "react";
import { Link, NavLink } from "react-router-dom";

const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/schools", label: "Schools" },
  { to: "/private-schools", label: "Private Schools" },
  { to: "/compare", label: "Compare" },
  { to: "/term-dates", label: "Term Dates" },
  { to: "/decision-support", label: "Decision Support" },
  { to: "/journey", label: "Journey" },
];

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav
      className="bg-white shadow-sm"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex h-14 items-center justify-between">
          {/* Logo / brand */}
          <Link
            to="/"
            className="flex items-center gap-2"
            aria-label="School Finder home"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              SF
            </span>
            <span className="font-display text-xl text-stone-900">
              School Finder
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex md:items-center md:gap-1">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `relative px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "text-brand-700"
                      : "text-stone-500 hover:text-stone-900"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {link.label}
                    {isActive && (
                      <span className="absolute inset-x-1 -bottom-[13px] h-0.5 rounded-full bg-brand-600" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>

          {/* Mobile menu button */}
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-label="Open main menu"
          >
            <span className="sr-only">Open main menu</span>
            {mobileMenuOpen ? (
              <svg
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            ) : (
              <svg
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="border-t border-stone-100 md:hidden">
          <div className="space-y-1 px-4 py-3">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `block rounded-md px-3 py-2 text-sm font-medium ${
                    isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-stone-600 hover:bg-stone-50 hover:text-stone-900"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
