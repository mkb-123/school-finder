import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Menu, X, GraduationCap } from "lucide-react";

const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/schools", label: "Schools" },
  { to: "/private-schools", label: "Private Schools" },
  { to: "/compare", label: "Compare" },
  { to: "/term-dates", label: "Term Dates" },
  { to: "/decision-support", label: "Help Me Decide" },
  { to: "/journey", label: "Journey" },
];

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Close mobile menu when clicking outside
  useEffect(() => {
    if (!mobileMenuOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        toggleRef.current &&
        !toggleRef.current.contains(event.target as Node)
      ) {
        setMobileMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [mobileMenuOpen]);

  // Trap focus within mobile menu and handle Escape key
  useEffect(() => {
    if (!mobileMenuOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        toggleRef.current?.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileMenuOpen]);

  return (
    <nav
      className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur-sm"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="mx-auto max-w-7xl px-4">
        <div className="flex h-14 items-center justify-between sm:h-16">
          {/* Logo / brand */}
          <Link
            to="/"
            className="flex items-center gap-2 rounded-lg px-1 py-1 text-lg font-bold text-blue-600 transition-colors hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            aria-label="School Finder home"
          >
            <GraduationCap className="h-5 w-5" aria-hidden="true" />
            <span className="hidden sm:inline">School Finder</span>
            <span className="sm:hidden">Schools</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden items-center gap-0.5 md:flex">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `relative rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
                    isActive
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {link.label}
                    {/* Active indicator bar */}
                    {isActive && (
                      <span
                        className="absolute -bottom-[9px] left-2 right-2 h-0.5 rounded-full bg-blue-600"
                        aria-hidden="true"
                      />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>

          {/* Mobile menu button */}
          <button
            ref={toggleRef}
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-nav-menu"
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
          >
            {mobileMenuOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu - slide down with transition */}
      <div
        ref={menuRef}
        id="mobile-nav-menu"
        className={`overflow-hidden border-t border-gray-200 transition-all duration-200 ease-in-out md:hidden ${
          mobileMenuOpen ? "max-h-[420px] opacity-100" : "max-h-0 opacity-0 border-t-0"
        }`}
        aria-hidden={!mobileMenuOpen}
      >
        <div className="space-y-1 px-4 py-3">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              tabIndex={mobileMenuOpen ? 0 : -1}
              className={({ isActive }) =>
                `flex min-h-[44px] items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`
              }
            >
              {({ isActive }) => (
                <span className="flex items-center gap-2">
                  {isActive && (
                    <span
                      className="inline-block h-1.5 w-1.5 rounded-full bg-blue-600"
                      aria-hidden="true"
                    />
                  )}
                  {link.label}
                </span>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
