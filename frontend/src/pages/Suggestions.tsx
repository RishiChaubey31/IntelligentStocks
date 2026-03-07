import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  fetchSuggestions,
  fetchHoldings,
  addHolding,
  removeHolding,
  refresh,
} from "../api";
import StockSearch from "../components/StockSearch";

export default function Suggestions() {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [notes, setNotes] = useState("");

  const { data: suggestions, isLoading } = useQuery({
    queryKey: ["suggestions"],
    queryFn: fetchSuggestions,
  });

  const { data: holdings = [] } = useQuery({
    queryKey: ["holdings"],
    queryFn: fetchHoldings,
  });

  const addMutation = useMutation({
    mutationFn: () =>
      addHolding(ticker, parseInt(quantity, 10), parseFloat(buyPrice), notes || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
      queryClient.invalidateQueries({ queryKey: ["suggestions"] });
      setShowAddForm(false);
      setTicker("");
      setQuantity("");
      setBuyPrice("");
      setNotes("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeHolding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
      queryClient.invalidateQueries({ queryKey: ["suggestions"] });
    },
  });

  const refreshMutation = useMutation({
    mutationFn: refresh,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suggestions"] });
      queryClient.invalidateQueries({ queryKey: ["holdings"] });
    },
  });

  const buySuggestions = suggestions?.buy_suggestions ?? [];
  const sellSuggestions = suggestions?.sell_suggestions ?? [];
  const potentialStocks = suggestions?.potential_stocks ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-pulse text-gray-500">Loading suggestions...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Suggestions</h1>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="px-4 py-2 rounded bg-accent hover:bg-accent/80 text-white font-medium disabled:opacity-50"
        >
          {refreshMutation.isPending ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      {/* My Holdings */}
      <div className="rounded-lg bg-card border border-border p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">My Holdings</h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 rounded bg-accent/20 text-accent text-sm hover:bg-accent/30"
          >
            {showAddForm ? "Cancel" : "Add Holding"}
          </button>
        </div>

        {showAddForm && (
          <div className="mb-4 p-4 rounded bg-surface border border-border space-y-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">
                Search any NSE/BSE stock, ETF, or fund
              </label>
              <StockSearch
                value={ticker}
                onChange={(t, result) => {
                  setTicker(t);
                  if (result) {
                    // auto-fill notes with company name
                    if (!notes) setNotes(result.name);
                  }
                }}
                autoFocus
              />
              {ticker && (
                <p className="text-xs text-emerald-400 mt-1">
                  ✓ Selected: <span className="font-mono font-bold">{ticker}</span>
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Quantity</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  placeholder="0"
                  className="w-full px-3 py-1.5 rounded bg-surface border border-border text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Buy Price (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  value={buyPrice}
                  onChange={(e) => setBuyPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-1.5 rounded bg-surface border border-border text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Notes (optional)</label>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. SIP, Long term…"
                  className="w-full px-3 py-1.5 rounded bg-surface border border-border text-sm"
                />
              </div>
            </div>
            <button
              onClick={() => addMutation.mutate()}
              disabled={!ticker || !quantity || !buyPrice || addMutation.isPending}
              className="px-4 py-2 rounded bg-accent text-white text-sm font-medium disabled:opacity-50"
            >
              {addMutation.isPending ? "Adding…" : "Add Holding"}
            </button>
            {addMutation.isError && (
              <p className="text-xs text-red-400">Failed to add. Check the ticker is valid.</p>
            )}
          </div>
        )}

        <div className="space-y-2">
          {holdings.length === 0 ? (
            <p className="text-gray-500 text-sm">No holdings. Add stocks you bought.</p>
          ) : (
            (holdings as Record<string, unknown>[]).map((h) => (
              <div
                key={h.id as number}
                className="flex items-center justify-between p-3 rounded bg-surface border border-border"
              >
                <div>
                  <Link to={`/stock/${h.ticker}`} className="font-medium text-accent hover:underline">
                    {(h.ticker as string).replace(/\.(NS|BO)$/, "")}
                  </Link>
                  <p className="text-xs text-gray-500">
                    {h.quantity as number} @ ₹{(h.buy_price as number).toFixed(2)} | Buy: ₹
                    {((h.quantity as number) * (h.buy_price as number)).toFixed(0)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm">₹{(h.current_price as number)?.toFixed(2) ?? "—"}</p>
                  <p
                    className={`text-xs font-medium ${
                      (h.pnl_pct as number) >= 0 ? "text-buy" : "text-sell"
                    }`}
                  >
                    {(h.pnl_pct as number) >= 0 ? "+" : ""}
                    {h.pnl_pct as number}%
                  </p>
                </div>
                <button
                  onClick={() => removeMutation.mutate(h.id as number)}
                  className="text-gray-500 hover:text-sell text-xs"
                >
                  Remove
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Sell Alerts */}
      {sellSuggestions.length > 0 && (
        <div className="rounded-lg bg-card border border-border p-4">
          <h2 className="text-lg font-semibold mb-3 text-sell">Consider Selling</h2>
          <div className="space-y-3">
            {(sellSuggestions as Record<string, unknown>[]).map((s) => (
              <div
                key={s.ticker as string}
                className="p-4 rounded bg-sell/10 border border-sell/30"
              >
                <div className="flex items-center justify-between">
                  <Link
                    to={`/stock/${s.ticker}`}
                    className="font-medium text-sell hover:underline"
                  >
                    {s.symbol as string}
                  </Link>
                  <span className="text-xs text-gray-500">
                    Confidence: {Math.round(s.confidence as number)}%
                  </span>
                </div>
                <p className="text-sm mt-2">{s.reason as string}</p>
                {(s.news as Record<string, unknown>[]).length > 0 && (
                  <div className="mt-3 space-y-1">
                    <p className="text-xs text-gray-500">Related news:</p>
                    {(s.news as Record<string, unknown>[]).map((n) => (
                      <a
                        key={n.id as number}
                        href={n.link as string}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-xs text-accent hover:underline line-clamp-1"
                      >
                        {n.title as string}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Buy Suggestions */}
      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3 text-buy">Buy Suggestions</h2>
        <div className="grid md:grid-cols-2 gap-3">
          {buySuggestions.length === 0 ? (
            <p className="text-gray-500 text-sm">No strong buy signals. Click Refresh.</p>
          ) : (
            (buySuggestions as Record<string, unknown>[]).map((s) => (
              <Link
                key={s.ticker as string}
                to={`/stock/${s.ticker}`}
                className="block p-4 rounded bg-buy/10 border border-buy/30 hover:border-buy/50"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{s.symbol as string}</span>
                  <span className="text-xs">
                    {Math.round(s.confidence as number)}% | {s.news_count as number} news
                  </span>
                </div>
                <p className="text-sm text-gray-400 mt-1">{s.reason as string}</p>
              </Link>
            ))
          )}
        </div>
      </div>

      {/* Stocks with Potential */}
      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">Stocks with Potential</h2>
        <div className="flex flex-wrap gap-2">
          {potentialStocks.length === 0 ? (
            <p className="text-gray-500 text-sm">No potential stocks. Click Refresh.</p>
          ) : (
            (potentialStocks as Record<string, unknown>[]).map((s) => (
              <Link
                key={s.ticker as string}
                to={`/stock/${s.ticker}`}
                className="px-4 py-2 rounded bg-surface border border-border hover:border-accent/50 text-sm"
              >
                <span className="font-medium">{s.symbol as string}</span>
                <span className="text-gray-500 text-xs ml-2">({Math.round(s.score as number)}%)</span>
                <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{s.rationale as string}</p>
              </Link>
            ))
          )}
        </div>
      </div>

      <p className="text-xs text-gray-600 text-center">
        This tool is for educational purposes only. Not financial advice.
      </p>
    </div>
  );
}
