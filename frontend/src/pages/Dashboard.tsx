import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  fetchDashboard,
  refresh,
  addToWatchlist,
  removeFromWatchlist,
  fetchIpos,
  fetchMarket,
  fetchCompanies,
  fetchMarketPulse,
  fetchPredictions,
} from "../api";
import StockSearch from "../components/StockSearch";

function SignalBadge({ signal }: { signal: string }) {
  const colors =
    signal === "buy"
      ? "bg-buy/20 text-buy border-buy/40"
      : signal === "sell"
        ? "bg-sell/20 text-sell border-sell/40"
        : "bg-hold/20 text-hold border-hold/40";
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium border ${colors}`}
    >
      {signal.toUpperCase()}
    </span>
  );
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const [newTicker, setNewTicker] = useState("");
  const [hotTab, setHotTab] = useState<"gainers" | "losers" | "active">("gainers");

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
  });

  const { data: ipos = [] } = useQuery({
    queryKey: ["ipos"],
    queryFn: () => fetchIpos(15),
  });

  const { data: market } = useQuery({
    queryKey: ["market"],
    queryFn: () => fetchMarket(12),
  });

  const { data: companies = [] } = useQuery({
    queryKey: ["companies"],
    queryFn: fetchCompanies,
  });

  const { data: pulse } = useQuery({
    queryKey: ["market-pulse"],
    queryFn: fetchMarketPulse,
    refetchInterval: 5 * 60 * 1000,
  });

  const { data: topPredictions = [] } = useQuery({
    queryKey: ["predictions-top"],
    queryFn: () => fetchPredictions(6, 65),
    refetchInterval: 5 * 60 * 1000,
  });

  const refreshMutation = useMutation({
    mutationFn: refresh,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["ipos"] });
      queryClient.invalidateQueries({ queryKey: ["market"] });
    },
  });

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  const removeMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  const signals = data?.signals ?? [];
  const news = data?.news ?? [];
  const watchlist = data?.watchlist ?? [];
  const gainers = market?.gainers ?? [];
  const losers = market?.losers ?? [];
  const mostActive = market?.most_active ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-pulse text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-sell/10 border border-sell/30 p-4 text-sell">
        Failed to load. Ensure the backend is running.
      </div>
    );
  }

  const pulseMoodColor =
    (pulse as { mood_color?: string } | undefined)?.mood_color === "green"  ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400" :
    (pulse as { mood_color?: string } | undefined)?.mood_color === "red"    ? "border-red-500/30 bg-red-500/5 text-red-400" :
    "border-yellow-500/30 bg-yellow-500/5 text-yellow-400";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="px-4 py-2 rounded bg-accent hover:bg-accent/80 text-white font-medium disabled:opacity-50"
        >
          {refreshMutation.isPending ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      {/* Market Pulse mini-banner */}
      {pulse && (
        <div className={`rounded-lg border p-3 flex flex-wrap items-center justify-between gap-3 ${pulseMoodColor}`}>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <span className="text-lg font-bold">
              {(pulse as { mood_score?: number }).mood_score !== undefined
                ? ((pulse as { mood_score: number }).mood_score > 0 ? "+" : "") + (pulse as { mood_score: number }).mood_score
                : "—"}
            </span>
            <span className="font-semibold">{(pulse as { mood_label?: string }).mood_label}</span>
            <span className="text-gray-500 text-xs hidden sm:inline">|</span>
            <span className="text-xs text-gray-400">{(pulse as { news_count_6h?: number }).news_count_6h} news in last 6h</span>
            <span className="text-xs text-gray-400">{(pulse as { high_impact_events?: number }).high_impact_events} high-impact events</span>
          </div>
          <Link to="/intelligence" className="text-xs text-accent hover:underline">
            View Intelligence Feed →
          </Link>
        </div>
      )}

      {/* Top predictions teaser */}
      {(topPredictions as Record<string, unknown>[]).length > 0 && (
        <div className="rounded-lg bg-card border border-border p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">⚡ Today&apos;s Top Predictions</h2>
            <Link to="/intelligence" className="text-xs text-accent hover:underline">See all →</Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
            {(topPredictions as Record<string, unknown>[]).map((p) => {
              const action = p.action as string;
              const direction = p.predicted_direction as string;
              const actionColor =
                action?.includes("BUY")  ? "text-emerald-400" :
                action?.includes("SELL") ? "text-red-400" :
                "text-yellow-400";
              const arrow = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
              return (
                <Link
                  key={p.id as number}
                  to={`/stock/${p.ticker}`}
                  className="p-2 rounded bg-surface border border-border hover:border-accent/50 text-center"
                >
                  <p className="font-bold text-accent text-sm">{p.symbol as string}</p>
                  <p className={`text-xs font-medium ${actionColor}`}>{arrow} {action}</p>
                  <p className="text-xs text-gray-500">{Math.round(p.confidence as number)}% conf</p>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">Watchlist</h2>
        <div className="flex gap-2 mb-3">
          <div className="flex-1 max-w-full sm:max-w-sm">
            <StockSearch
              value={newTicker}
              onChange={(ticker) => {
                if (ticker) {
                  addMutation.mutate(ticker);
                  setNewTicker("");
                } else {
                  setNewTicker(ticker);
                }
              }}
              placeholder="Search any NSE/BSE stock to add…"
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {watchlist.map((t: string) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-surface border border-border"
            >
              <Link to={`/stock/${t}`} className="text-accent hover:underline">
                {t.replace(/\.(NS|BO)$/, "")}
              </Link>
              <button
                onClick={() => removeMutation.mutate(t)}
                className="text-gray-500 hover:text-sell text-xs"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">Today&apos;s Hot Stocks (Nifty 50)</h2>
        <div className="flex gap-2 mb-3">
          {(["gainers", "losers", "active"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setHotTab(t)}
              className={`px-3 py-1.5 rounded text-sm font-medium ${
                hotTab === t ? "bg-accent text-white" : "bg-surface border border-border"
              }`}
            >
              {t === "gainers" ? "Top Gainers" : t === "losers" ? "Top Losers" : "Most Active"}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 max-h-48 overflow-y-auto">
          {(hotTab === "gainers" ? gainers : hotTab === "losers" ? losers : mostActive).map(
            (s: { ticker: string; symbol: string; price: number; change_pct?: number; value_traded?: number }) => (
              <Link
                key={s.ticker}
                to={`/stock/${s.ticker}`}
                className="p-2 rounded bg-surface border border-border hover:border-accent/50"
              >
                <p className="font-medium text-sm">{s.symbol}</p>
                <p className="text-xs text-gray-500">₹{s.price?.toFixed(2)}</p>
                {s.change_pct != null && (
                  <p
                    className={`text-xs font-medium ${
                      s.change_pct >= 0 ? "text-buy" : "text-sell"
                    }`}
                  >
                    {s.change_pct >= 0 ? "+" : ""}
                    {s.change_pct}%
                  </p>
                )}
                {s.value_traded != null && hotTab === "active" && (
                  <p className="text-xs text-gray-500">
                    ₹{(s.value_traded / 1e7).toFixed(1)}Cr
                  </p>
                )}
              </Link>
            )
          )}
        </div>
        {gainers.length === 0 && losers.length === 0 && mostActive.length === 0 && (
          <p className="text-gray-500 text-sm py-2">No market data. Click Refresh.</p>
        )}
      </div>

      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">Latest IPO News</h2>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {(ipos as Record<string, unknown>[]).length === 0 ? (
            <p className="text-gray-500 text-sm">No IPO news yet. Click Refresh.</p>
          ) : (
            (ipos as Record<string, unknown>[]).map((n) => (
              <a
                key={n.id as number}
                href={n.link as string}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-2 rounded bg-surface border border-border hover:border-accent/50"
              >
                <p className="text-sm line-clamp-2">{n.title as string}</p>
                <p className="text-xs text-gray-500">{n.source as string}</p>
              </a>
            ))
          )}
        </div>
      </div>

      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">NSE & BSE Listed Companies (Nifty 50)</h2>
        <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
          {(companies as { ticker: string; symbol: string }[]).map((c) => (
            <Link
              key={c.ticker}
              to={`/stock/${c.ticker}`}
              className="px-3 py-1 rounded-full bg-surface border border-border hover:border-accent/50 text-sm"
            >
              {c.symbol}
            </Link>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-lg bg-card border border-border p-4">
          <h2 className="text-lg font-semibold mb-3">Signals</h2>
          <div className="space-y-2">
            {signals.length === 0 ? (
              <p className="text-gray-500 text-sm">No signals yet. Click Refresh.</p>
            ) : (
              signals.map((s: Record<string, unknown>) => (
                <Link
                  key={String(s.ticker)}
                  to={`/stock/${s.ticker}`}
                  className="block p-3 rounded bg-surface border border-border hover:border-accent/50 transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{s.ticker as string}</span>
                    <SignalBadge signal={s.signal as string} />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{s.reason as string}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Confidence: {Math.round(s.confidence as number)}%
                  </p>
                </Link>
              ))
            )}
          </div>
        </div>

        <div className="rounded-lg bg-card border border-border p-4">
          <h2 className="text-lg font-semibold mb-3">Recent News</h2>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {news.length === 0 ? (
              <p className="text-gray-500 text-sm">No news yet. Click Refresh.</p>
            ) : (
              news.map((n: Record<string, unknown>) => (
                <a
                  key={n.id as number}
                  href={n.link as string}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-2 rounded bg-surface border border-border hover:border-accent/50 transition"
                >
                  <p className="text-sm line-clamp-2">{n.title as string}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {n.source as string}
                    {n.sentiment_score != null && (
                      <span
                        className={
                          (n.sentiment_score as number) > 0
                            ? "text-buy"
                            : (n.sentiment_score as number) < 0
                              ? "text-sell"
                              : "text-gray-500"
                        }
                      >
                        {" "}
                        ({(n.sentiment_score as number).toFixed(2)})
                      </span>
                    )}
                  </p>
                </a>
              ))
            )}
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-600 text-center">
        This tool is for educational purposes only. Not financial advice. Past
        performance does not guarantee future results.
      </p>
    </div>
  );
}
