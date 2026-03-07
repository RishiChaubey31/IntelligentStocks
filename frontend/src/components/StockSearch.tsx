import { useState, useEffect, useRef, useCallback } from "react";
import { searchStocks } from "../api";

export interface StockResult {
  symbol: string;
  ticker: string;   // e.g. "TATSILV.NS"
  name: string;
  series: string;   // EQ, ETF, BE, etc.
  exchange: string;
}

interface StockSearchProps {
  value: string;
  onChange: (ticker: string, result: StockResult | null) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
}

function seriesBadge(series: string) {
  const s = (series || "EQ").toUpperCase();
  if (s === "ETF" || s === "ETFSEC") return (
    <span className="px-1 py-0.5 rounded bg-blue-500/20 text-blue-400 text-xs">ETF</span>
  );
  if (s === "BE" || s === "BZ") return (
    <span className="px-1 py-0.5 rounded bg-orange-500/20 text-orange-400 text-xs">T+1</span>
  );
  if (s === "SM" || s === "ST") return (
    <span className="px-1 py-0.5 rounded bg-purple-500/20 text-purple-400 text-xs">SME</span>
  );
  return null;
}

export default function StockSearch({
  value,
  onChange,
  placeholder = "Search any stock, ETF… (e.g. Tata Silver, TATSILV)",
  className = "",
  autoFocus = false,
}: StockSearchProps) {
  const [query, setQuery] = useState(value || "");
  const [results, setResults] = useState<StockResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<StockResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const data = await searchStocks(q, 12);
      setResults(data || []);
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    setSelected(null);
    onChange("", null);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(q), 300);
  }

  function handleSelect(result: StockResult) {
    setQuery(`${result.symbol} — ${result.name}`);
    setSelected(result);
    setOpen(false);
    setResults([]);
    onChange(result.ticker, result);
  }

  function handleClear() {
    setQuery("");
    setSelected(null);
    setResults([]);
    setOpen(false);
    onChange("", null);
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={handleInput}
          onFocus={() => query.length >= 1 && results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className={`w-full px-3 py-2 pr-8 rounded bg-surface border text-sm transition-colors ${
            selected
              ? "border-emerald-500/60 text-white"
              : "border-border text-gray-200"
          } focus:outline-none focus:border-accent/60`}
        />
        {loading && (
          <span className="absolute right-2.5 top-2.5 text-gray-500 text-xs animate-spin">⟳</span>
        )}
        {!loading && query && (
          <button
            onClick={handleClear}
            className="absolute right-2.5 top-2 text-gray-500 hover:text-gray-300 text-sm"
          >
            ×
          </button>
        )}
      </div>

      {/* Dropdown */}
      {open && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 rounded-lg border border-border bg-card shadow-xl overflow-hidden">
          {results.map((r) => (
            <button
              key={r.ticker}
              onMouseDown={() => handleSelect(r)}
              className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-surface text-left transition-colors border-b border-border/50 last:border-0"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-bold text-accent text-sm w-24 shrink-0">{r.symbol}</span>
                <span className="text-gray-300 text-sm truncate">{r.name}</span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0 ml-2">
                {seriesBadge(r.series)}
                <span className="text-xs text-gray-600">{r.exchange}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {open && !loading && results.length === 0 && query.length >= 2 && (
        <div className="absolute z-50 w-full mt-1 rounded-lg border border-border bg-card shadow-xl px-3 py-3 text-sm text-gray-500">
          No results for "{query}". Try the NSE symbol directly (e.g. TATSILV).
        </div>
      )}
    </div>
  );
}
