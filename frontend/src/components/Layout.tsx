import { ReactNode, useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const navLinks = [
    { to: "/", label: "Dashboard" },
    { to: "/intelligence", label: "⚡ Intelligence" },
    { to: "/suggestions", label: "Suggestions" },
  ];

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-xl font-bold text-accent whitespace-nowrap">
              AI Stock Agent
            </Link>
            <nav className="hidden md:flex gap-1">
              {navLinks.map(({ to, label }) => {
                const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                      active
                        ? "bg-accent/20 text-accent"
                        : "text-gray-400 hover:text-accent hover:bg-accent/10"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <p className="text-xs text-gray-500 hidden sm:block">
            NSE & BSE · Educational only · Not financial advice
          </p>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 rounded text-gray-400 hover:text-white hover:bg-accent/10 transition-colors"
            aria-label="Toggle menu"
          >
            {mobileOpen ? (
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 5l10 10M15 5L5 15" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 5h14M3 10h14M3 15h14" />
              </svg>
            )}
          </button>
        </div>

        {mobileOpen && (
          <nav className="md:hidden border-t border-border bg-card/95 backdrop-blur px-4 py-3 space-y-1">
            {navLinks.map(({ to, label }) => {
              const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
              return (
                <Link
                  key={to}
                  to={to}
                  className={`block px-3 py-2.5 rounded text-sm font-medium transition-colors ${
                    active
                      ? "bg-accent/20 text-accent"
                      : "text-gray-400 hover:text-accent hover:bg-accent/10"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
            <p className="text-xs text-gray-600 pt-2 px-3">
              NSE & BSE · Educational only · Not financial advice
            </p>
          </nav>
        )}
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
