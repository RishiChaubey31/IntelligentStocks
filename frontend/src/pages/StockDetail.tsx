import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi } from "lightweight-charts";
import { fetchStockDetail, fetchPredictionsForTicker } from "../api";

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

const ACTION_COLORS: Record<string, string> = {
  "BUY NOW":      "bg-emerald-500/20 text-emerald-400 border-emerald-500/50",
  "BUY AT OPEN":  "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  "SELL":         "bg-red-500/20 text-red-400 border-red-500/50",
  "SELL AT OPEN": "bg-red-500/15 text-red-300 border-red-500/40",
  "WATCH":        "bg-yellow-500/15 text-yellow-400 border-yellow-500/40",
  "WAIT":         "bg-blue-500/15 text-blue-400 border-blue-500/40",
  "AVOID":        "bg-gray-500/20 text-gray-400 border-gray-500/40",
};

interface PredItem {
  id: number;
  event_type: string;
  predicted_direction: string;
  predicted_pct_low: number;
  predicted_pct_high: number;
  confidence: number;
  action: string;
  timing_window: string;
  entry_time: string;
  stop_loss_pct: number;
  reasoning: string;
  created_at: string;
  news: { title: string; link: string; source: string } | null;
}

export default function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const [expandedPred, setExpandedPred] = useState<number | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const baseTicker = ticker?.replace(/\.(NS|BO)$/i, "") ?? "";

  const { data, isLoading, error } = useQuery({
    queryKey: ["stock", ticker],
    queryFn: () => fetchStockDetail(ticker!),
    enabled: !!ticker,
  });

  const { data: predictions = [] } = useQuery<PredItem[]>({
    queryKey: ["predictions-ticker", baseTicker],
    queryFn: () => fetchPredictionsForTicker(baseTicker),
    enabled: !!baseTicker,
  });

  useEffect(() => {
    if (!chartRef.current || !data?.price_history?.length) return;

    const history = data.price_history as { date: string; open: number; high: number; low: number; close: number }[];
    const candleData = history.map((p) => ({
      time: p.date.split("T")[0],
      open: p.open,
      high: p.high,
      low: p.low,
      close: p.close,
    }));

    if (chartInstance.current) {
      chartInstance.current.remove();
    }

    const chart = createChart(chartRef.current, {
      layout: {
        background: { color: "#16161a" },
        textColor: "#94a3b8",
      },
      grid: { vertLines: { color: "#2a2a2e" }, horzLines: { color: "#2a2a2e" } },
      width: chartRef.current.clientWidth,
      height: 300,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
    });

    candlestickSeries.setData(candleData);
    chart.timeScale().fitContent();

    chartInstance.current = chart;
    seriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartInstance.current = null;
    };
  }, [data?.price_history]);

  if (isLoading || !ticker) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-pulse text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg bg-sell/10 border border-sell/30 p-4 text-sell">
        Failed to load stock. <Link to="/" className="underline">Back to Dashboard</Link>
      </div>
    );
  }

  const ind = data.indicators ?? {};
  const signal = data.signal as { signal: string; confidence: number; reason: string } | null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/" className="text-gray-500 hover:text-accent">← Back</Link>
        <h1 className="text-2xl font-bold">
          {(data.ticker as string).replace(/\.(NS|BO)$/, "")}
        </h1>
        {signal?.signal && <SignalBadge signal={signal.signal} />}
      </div>

      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">Price Chart</h2>
        <div ref={chartRef} className="w-full h-[300px]" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-lg bg-card border border-border p-4">
          <h2 className="text-lg font-semibold mb-3">Indicators</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Current Price</dt>
              <dd className="font-mono">₹{ind.current_price?.toFixed(2) ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">RSI (14)</dt>
              <dd className="font-mono">{ind.rsi?.toFixed(2) ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">MACD</dt>
              <dd className="font-mono">{ind.macd_signal ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">SMA 20</dt>
              <dd className="font-mono">₹{ind.sma_20?.toFixed(2) ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">SMA 50</dt>
              <dd className="font-mono">₹{ind.sma_50?.toFixed(2) ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Trend</dt>
              <dd className="font-mono">{ind.trend ?? "—"}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg bg-card border border-border p-4">
          <h2 className="text-lg font-semibold mb-3">Signal</h2>
          {signal ? (
            <div className="space-y-2">
              <p><strong>Action:</strong> <SignalBadge signal={signal.signal} /></p>
              <p className="text-sm text-gray-500">Confidence: {Math.round(signal.confidence)}%</p>
              <p className="text-sm">{signal.reason}</p>
            </div>
          ) : (
            <p className="text-gray-500">No signal computed yet.</p>
          )}
        </div>
      </div>

      {/* Predictions Panel */}
      {predictions.length > 0 && (
        <div className="rounded-lg bg-card border border-accent/30 p-4">
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-lg font-semibold">⚡ Predictions for {baseTicker}</h2>
            <span className="text-xs text-gray-500">(last 72h)</span>
          </div>
          <div className="space-y-3">
            {predictions.map((p) => {
              const actionCls = ACTION_COLORS[p.action] ?? "bg-gray-500/20 text-gray-400 border-gray-500/40";
              const dirArrow = p.predicted_direction === "up" ? "↑" : p.predicted_direction === "down" ? "↓" : "→";
              const dirColor = p.predicted_direction === "up" ? "text-emerald-400" : p.predicted_direction === "down" ? "text-red-400" : "text-yellow-400";
              const pctLow = Math.abs(p.predicted_pct_low);
              const pctHigh = Math.abs(p.predicted_pct_high);
              const sign = p.predicted_direction === "up" ? "+" : p.predicted_direction === "down" ? "" : "";
              const pctLabel = pctLow === pctHigh ? `${sign}${pctLow.toFixed(1)}%` : `${sign}${pctLow.toFixed(1)}% to ${sign}${pctHigh.toFixed(1)}%`;

              return (
                <div key={p.id} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs border uppercase font-bold ${actionCls}`}>
                        {p.action}
                      </span>
                      <span className={`font-semibold ${dirColor}`}>{dirArrow} {pctLabel}</span>
                      <span className="text-xs text-gray-500 capitalize">
                        {p.event_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-20 bg-card rounded-full overflow-hidden">
                        <div
                          className={`h-full ${p.confidence >= 75 ? "bg-emerald-500" : p.confidence >= 55 ? "bg-yellow-500" : "bg-gray-500"}`}
                          style={{ width: `${p.confidence}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400">{p.confidence}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-yellow-400 mb-1">⏱ Entry: {p.entry_time}</p>
                  {p.news && (
                    <a href={p.news.link} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-gray-400 hover:text-gray-200 line-clamp-1 mb-1 block">
                      {p.news.title}
                    </a>
                  )}
                  <button
                    onClick={() => setExpandedPred(expandedPred === p.id ? null : p.id)}
                    className="text-xs text-accent hover:underline"
                  >
                    {expandedPred === p.id ? "▲ Hide reasoning" : "▼ Why?"}
                  </button>
                  {expandedPred === p.id && (
                    <div className="mt-2 text-xs text-gray-300 leading-relaxed border-t border-border pt-2">
                      <p className="mb-1">{p.reasoning}</p>
                      <p className="text-gray-500 italic">{p.timing_window}</p>
                      {p.stop_loss_pct > 0 && (
                        <p className="text-red-400 mt-1">Stop-loss: {p.stop_loss_pct}% below entry</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="rounded-lg bg-card border border-border p-4">
        <h2 className="text-lg font-semibold mb-3">Related News</h2>
        <div className="space-y-2">
          {data.news?.length === 0 ? (
            <p className="text-gray-500 text-sm">No related news.</p>
          ) : (
            data.news?.map((n: { id: number; title: string; link: string; source: string; sentiment_score: number | null }) => (
              <a
                key={n.id}
                href={n.link}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-2 rounded bg-surface border border-border hover:border-accent/50"
              >
                <p className="text-sm line-clamp-2">{n.title}</p>
                <p className="text-xs text-gray-500">
                  {n.source}
                  {n.sentiment_score != null && (
                    <span className={n.sentiment_score > 0 ? "text-buy" : n.sentiment_score < 0 ? "text-sell" : ""}>
                      {" "}({n.sentiment_score.toFixed(2)})
                    </span>
                  )}
                </p>
              </a>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
