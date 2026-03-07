import { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useLocation } from "react-router-dom";

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();

  const navLinks = [
    { to: "/", label: "Dashboard" },
    { to: "/intelligence", label: "⚡ Intelligence" },
    { to: "/suggestions", label: "Suggestions" },
  ];

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-xl font-bold text-accent whitespace-nowrap">
              AI Stock Agent
            </Link>
            <nav className="flex gap-1">
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
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
