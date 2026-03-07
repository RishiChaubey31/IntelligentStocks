import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  fetchPredictions,
  fetchEvents,
  fetchMarketPulse,
  refresh,
  addToWatchlist,
  fetchAIAnalysis,
  chatWithAI,
} from "../api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface NewsItem {
  id: number;
  title: string;
  link: string;
  source: string;
  published_at: string | null;
}

interface Prediction {
  id: number;
  ticker: string;
  symbol: string;
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
  sector_impact: string[];
  affected_tickers: string[];
  created_at: string;
  news: NewsItem | null;
}

interface MarketEvent {
  id: number;
  event_type: string;
  impact: string;
  affected_tickers: string[];
  affected_sectors: string[];
  sentiment_hint: string;
  keywords: string[];
  title: string;
  source: string;
  published_at: string;
}

interface MarketPulse {
  mood_score: number;
  mood_label: string;
  mood_color: string;
  avg_sentiment: number;
  news_count_6h: number;
  news_count_24h: number;
  high_impact_events: number;
  positive_events: number;
  negative_events: number;
  top_predictions: {
    ticker: string;
    symbol: string;
    action: string;
    confidence: number;
    predicted_direction: string;
    event_type: string;
  }[];
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

const ACTION_STYLES: Record<string, string> = {
  "BUY NOW":      "bg-emerald-500/20 text-emerald-400 border-emerald-500/50",
  "BUY AT OPEN":  "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  "SELL":         "bg-red-500/20 text-red-400 border-red-500/50",
  "SELL AT OPEN": "bg-red-500/15 text-red-300 border-red-500/40",
  "WATCH":        "bg-yellow-500/15 text-yellow-400 border-yellow-500/40",
  "WAIT":         "bg-blue-500/15 text-blue-400 border-blue-500/40",
  "AVOID":        "bg-gray-500/20 text-gray-400 border-gray-500/40",
};

function ActionBadge({ action }: { action: string }) {
  const cls = ACTION_STYLES[action] ?? "bg-gray-500/20 text-gray-400 border-gray-500/40";
  return (
    <span className={`inline-block px-2.5 py-1 rounded text-xs font-bold border uppercase tracking-wide ${cls}`}>
      {action}
    </span>
  );
}

function DirectionArrow({ direction }: { direction: string }) {
  if (direction === "up")
    return <span className="text-emerald-400 text-lg font-bold">↑</span>;
  if (direction === "down")
    return <span className="text-red-400 text-lg font-bold">↓</span>;
  return <span className="text-yellow-400 text-lg font-bold">→</span>;
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const color =
    confidence >= 75 ? "bg-emerald-500" :
    confidence >= 55 ? "bg-yellow-500" :
    "bg-gray-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${confidence}%` }} />
      </div>
      <span className="text-xs text-gray-400 w-10 text-right">{confidence}%</span>
    </div>
  );
}

function ImpactDot({ impact }: { impact: string }) {
  const cls =
    impact === "high"   ? "bg-red-500" :
    impact === "medium" ? "bg-yellow-500" :
    "bg-gray-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${cls}`} />;
}

function SentimentDot({ hint }: { hint: string }) {
  if (hint === "positive") return <span className="text-emerald-400 text-sm">●</span>;
  if (hint === "negative") return <span className="text-red-400 text-sm">●</span>;
  return <span className="text-yellow-400 text-sm">●</span>;
}

function EventTypePill({ type }: { type: string }) {
  const label = type.replace(/_/g, " ");
  const cls =
    type.includes("contract") || type.includes("defence")
      ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
      : type.includes("earnings_beat") || type.includes("funding") || type.includes("ipo")
        ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
        : type.includes("miss") || type.includes("regulatory") || type.includes("geopolitical")
          ? "bg-red-500/20 text-red-300 border-red-500/30"
          : "bg-gray-500/20 text-gray-300 border-gray-500/30";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs border capitalize ${cls}`}>
      {label}
    </span>
  );
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function formatPctRange(low: number, high: number, direction: string): string {
  if (direction === "down") return `${low.toFixed(1)}% to ${high.toFixed(1)}%`;
  const sign = direction === "up" ? "+" : "";
  const absLow = Math.abs(low);
  const absHigh = Math.abs(high);
  if (absLow === absHigh) return `${sign}${absLow.toFixed(1)}%`;
  return `${sign}${absLow.toFixed(1)}% to ${sign}${absHigh.toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// PredictionCard
// ---------------------------------------------------------------------------
function PredictionCard({ pred }: { pred: Prediction }) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  const pctLabel = formatPctRange(pred.predicted_pct_low, pred.predicted_pct_high, pred.predicted_direction);

  return (
    <div className="rounded-xl bg-card border border-border hover:border-accent/40 transition-all">
      <div className="p-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              to={`/stock/${pred.ticker}`}
              className="text-lg font-bold text-accent hover:underline"
            >
              {pred.symbol}
            </Link>
            <DirectionArrow direction={pred.predicted_direction} />
            <span className={`text-sm font-semibold ${pred.predicted_direction === "up" ? "text-emerald-400" : pred.predicted_direction === "down" ? "text-red-400" : "text-yellow-400"}`}>
              {pctLabel}
            </span>
          </div>
          <ActionBadge action={pred.action} />
        </div>

        {/* Event type + source */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <EventTypePill type={pred.event_type} />
          {pred.news && (
            <span className="text-xs text-gray-500">
              {pred.news.source} · {timeAgo(pred.news.published_at)}
            </span>
          )}
        </div>

        {/* News headline */}
        {pred.news && (
          <a
            href={pred.news.link}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-sm text-gray-300 hover:text-white mb-3 line-clamp-2 leading-snug"
          >
            {pred.news.title}
          </a>
        )}

        {/* Confidence bar */}
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1">Confidence</p>
          <ConfidenceBar confidence={pred.confidence} />
        </div>

        {/* Timing */}
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-3">
          <span className="text-yellow-400">⏱</span>
          <span className="font-medium">Entry:</span>
          <span>{pred.entry_time}</span>
          {pred.stop_loss_pct > 0 && (
            <>
              <span className="text-gray-600 mx-1">|</span>
              <span className="text-red-400">SL:</span>
              <span>{pred.stop_loss_pct}% below entry</span>
            </>
          )}
        </div>

        {/* Affected sectors */}
        {pred.sector_impact.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {pred.sector_impact.slice(0, 4).map((s) => (
              <span key={s} className="px-1.5 py-0.5 rounded bg-surface border border-border text-xs text-gray-400">
                {s}
              </span>
            ))}
          </div>
        )}

        {/* Expand reasoning */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-accent hover:underline flex items-center gap-1"
        >
          {expanded ? "▲ Hide reasoning" : "▼ Why this stock?"}
        </button>

        {expanded && (
          <div className="mt-3 p-3 rounded-lg bg-surface border border-border">
            <p className="text-xs text-gray-300 leading-relaxed mb-2">{pred.reasoning}</p>
            <p className="text-xs text-gray-500 italic leading-relaxed">{pred.timing_window}</p>
            {pred.affected_tickers.length > 1 && (
              <div className="mt-2">
                <p className="text-xs text-gray-500 mb-1">Related tickers:</p>
                <div className="flex flex-wrap gap-1">
                  {pred.affected_tickers.filter(t => t !== pred.symbol).slice(0, 6).map((t) => (
                    <Link
                      key={t}
                      to={`/stock/${t}.NS`}
                      className="px-1.5 py-0.5 rounded bg-card border border-border text-xs text-accent hover:underline"
                    >
                      {t}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add to watchlist */}
      <div className="px-4 pb-3">
        <button
          onClick={() => addMutation.mutate(pred.ticker)}
          disabled={addMutation.isPending}
          className="text-xs text-gray-500 hover:text-accent disabled:opacity-50 flex items-center gap-1"
        >
          + Add to watchlist
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EventCard
// ---------------------------------------------------------------------------
function EventCard({ event }: { event: MarketEvent }) {
  return (
    <div className="flex gap-3 p-3 rounded-lg bg-surface border border-border hover:border-accent/30 transition">
      <div className="pt-0.5">
        <SentimentDot hint={event.sentiment_hint} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <ImpactDot impact={event.impact} />
          <EventTypePill type={event.event_type} />
          <span className="text-xs text-gray-500">{event.source}</span>
          <span className="text-xs text-gray-600">{timeAgo(event.published_at)}</span>
        </div>
        <p className="text-sm text-gray-200 leading-snug mb-1 line-clamp-2">{event.title}</p>
        {event.affected_tickers.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {event.affected_tickers.slice(0, 5).map((t) => (
              <Link
                key={t}
                to={`/stock/${t}.NS`}
                className="px-1.5 py-0.5 rounded bg-card border border-border text-xs text-accent hover:underline"
              >
                {t}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Market Pulse Banner
// ---------------------------------------------------------------------------
function MarketPulseBanner({ pulse }: { pulse: MarketPulse }) {
  const moodColor =
    pulse.mood_color === "green"  ? "border-emerald-500/40 bg-emerald-500/5" :
    pulse.mood_color === "red"    ? "border-red-500/40 bg-red-500/5" :
    "border-yellow-500/40 bg-yellow-500/5";

  const scoreColor =
    pulse.mood_color === "green" ? "text-emerald-400" :
    pulse.mood_color === "red"   ? "text-red-400" :
    "text-yellow-400";

  return (
    <div className={`rounded-xl border p-4 ${moodColor}`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Market Pulse Today</p>
          <div className="flex items-center gap-3">
            <span className={`text-2xl font-bold ${scoreColor}`}>
              {pulse.mood_score > 0 ? "+" : ""}{pulse.mood_score}
            </span>
            <span className={`text-lg font-semibold ${scoreColor}`}>{pulse.mood_label}</span>
          </div>
        </div>
        <div className="flex gap-6 text-center">
          <div>
            <p className="text-xs text-gray-500">News (6h)</p>
            <p className="text-lg font-bold text-white">{pulse.news_count_6h}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">High Impact</p>
            <p className="text-lg font-bold text-red-400">{pulse.high_impact_events}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Positive Events</p>
            <p className="text-lg font-bold text-emerald-400">{pulse.positive_events}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Negative Events</p>
            <p className="text-lg font-bold text-red-400">{pulse.negative_events}</p>
          </div>
        </div>
      </div>
      {pulse.top_predictions.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-xs text-gray-500 mb-2">Top signals right now:</p>
          <div className="flex flex-wrap gap-2">
            {pulse.top_predictions.map((p) => (
              <Link
                key={p.ticker}
                to={`/stock/${p.ticker}`}
                className="flex items-center gap-1.5 px-2 py-1 rounded bg-card border border-border hover:border-accent/40"
              >
                <span className="font-medium text-sm text-accent">{p.symbol}</span>
                <ActionBadge action={p.action} />
                <span className="text-xs text-gray-400">{p.confidence}%</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI Types
// ---------------------------------------------------------------------------
interface AIPick {
  ticker: string;
  action: string;
  confidence: number;
  target_pct: number;
  timeframe: string;
  reasoning: string;
  risk: string;
}

interface AISectorView {
  sector: string;
  outlook: string;
  reason: string;
}

interface AIAnalysis {
  summary: string;
  market_outlook: string;
  picks: AIPick[];
  sector_views: AISectorView[];
  key_risks: string[];
  generated_at: string;
  error?: string;
}

interface ChatMessage {
  role: "user" | "ai";
  text: string;
}

// ---------------------------------------------------------------------------
// AI Pick Card
// ---------------------------------------------------------------------------
const AI_ACTION_STYLES: Record<string, string> = {
  BUY:   "bg-emerald-500/20 text-emerald-400 border-emerald-500/50",
  SELL:  "bg-red-500/20 text-red-400 border-red-500/50",
  HOLD:  "bg-yellow-500/15 text-yellow-400 border-yellow-500/40",
  WATCH: "bg-blue-500/15 text-blue-400 border-blue-500/40",
};

function AIPickCard({ pick }: { pick: AIPick }) {
  const [expanded, setExpanded] = useState(false);
  const actionCls = AI_ACTION_STYLES[pick.action] ?? "bg-gray-500/20 text-gray-400 border-gray-500/40";
  const targetColor = pick.target_pct >= 0 ? "text-emerald-400" : "text-red-400";
  const targetSign = pick.target_pct >= 0 ? "+" : "";

  return (
    <div className="rounded-xl bg-card border border-border hover:border-accent/40 transition-all p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <Link to={`/stock/${pick.ticker}.NS`} className="text-lg font-bold text-accent hover:underline">
          {pick.ticker}
        </Link>
        <span className={`inline-block px-2.5 py-1 rounded text-xs font-bold border uppercase tracking-wide ${actionCls}`}>
          {pick.action}
        </span>
      </div>

      <div className="flex items-center gap-3 mb-3">
        <span className={`text-sm font-semibold ${targetColor}`}>
          {targetSign}{pick.target_pct.toFixed(1)}%
        </span>
        <span className="text-xs text-gray-500">in {pick.timeframe}</span>
      </div>

      <div className="mb-3">
        <p className="text-xs text-gray-500 mb-1">AI Confidence</p>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${pick.confidence >= 75 ? "bg-emerald-500" : pick.confidence >= 55 ? "bg-yellow-500" : "bg-gray-500"}`}
              style={{ width: `${pick.confidence}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 w-10 text-right">{pick.confidence}%</span>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-accent hover:underline flex items-center gap-1"
      >
        {expanded ? "▲ Hide analysis" : "▼ View AI reasoning"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          <div className="p-3 rounded-lg bg-surface border border-border">
            <p className="text-xs text-gray-400 mb-1 font-medium">Analysis</p>
            <p className="text-xs text-gray-300 leading-relaxed">{pick.reasoning}</p>
          </div>
          <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
            <p className="text-xs text-red-400 mb-1 font-medium">⚠ Risk</p>
            <p className="text-xs text-gray-400 leading-relaxed">{pick.risk}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI Chat Component
// ---------------------------------------------------------------------------
function AIChat({ db_context_ready }: { db_context_ready: boolean }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "ai",
      text: "Hello! I'm your Gemini AI stock analyst with live access to Indian market data — news, technical signals, and predictions. Ask me anything about stocks, sectors, buy/sell decisions, or market trends. I answer without restrictions.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isTyping) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setIsTyping(true);
    try {
      const data = await chatWithAI(text);
      setMessages((prev) => [...prev, { role: "ai", text: data.reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Sorry, I couldn't reach the AI. Make sure the backend is running and try again." },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="rounded-xl bg-card border border-border flex flex-col" style={{ height: "520px" }}>
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span className="font-semibold text-sm">Ask AI Anything</span>
        <span className="text-xs text-gray-500 ml-1">— powered by Gemini</span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] px-3 py-2 rounded-xl text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-accent text-white rounded-br-sm"
                  : "bg-surface border border-border text-gray-200 rounded-bl-sm"
              }`}
            >
              {msg.role === "ai" && (
                <span className="text-xs text-accent font-semibold block mb-1">Gemini AI</span>
              )}
              {msg.text}
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-surface border border-border px-4 py-3 rounded-xl rounded-bl-sm">
              <div className="flex gap-1 items-center">
                <span className="text-xs text-accent font-semibold mr-2">Gemini AI</span>
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 pb-4 pt-2 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
            placeholder="Ask about any stock, sector, or strategy..."
            className="flex-1 px-3 py-2 rounded-lg bg-surface border border-border text-sm placeholder-gray-600 focus:outline-none focus:border-accent"
            disabled={isTyping}
          />
          <button
            onClick={sendMessage}
            disabled={isTyping || !input.trim()}
            className="px-4 py-2 rounded-lg bg-accent hover:bg-accent/80 text-white text-sm font-medium disabled:opacity-40 transition"
          >
            Send
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {["Best stocks to buy today?", "Which sectors look bullish?", "Show me sell signals", "What's driving Nifty today?"].map((q) => (
            <button
              key={q}
              onClick={() => { setInput(q); }}
              className="text-xs px-2 py-1 rounded bg-surface border border-border text-gray-400 hover:text-gray-200 hover:border-accent/40 transition"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI Analysis Panel
// ---------------------------------------------------------------------------
function AIAnalysisPanel() {
  const queryClient = useQueryClient();

  const {
    data: analysis,
    isLoading,
    isFetching,
    refetch,
  } = useQuery<AIAnalysis>({
    queryKey: ["ai-analysis"],
    queryFn: fetchAIAnalysis,
    staleTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
    enabled: false,
  });

  const OUTLOOK_STYLES: Record<string, string> = {
    bullish: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    bearish: "text-red-400 bg-red-500/10 border-red-500/30",
    neutral: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
    mixed:   "text-blue-400 bg-blue-500/10 border-blue-500/30",
  };

  const SECTOR_OUTLOOK: Record<string, string> = {
    positive: "text-emerald-400",
    negative: "text-red-400",
    neutral:  "text-yellow-400",
  };

  return (
    <div className="space-y-4">
      {/* Header with generate button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-base">Gemini AI Analysis</h3>
          {analysis?.generated_at && (
            <p className="text-xs text-gray-500 mt-0.5">
              Generated {timeAgo(analysis.generated_at)}
            </p>
          )}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="px-4 py-2 rounded-lg bg-accent hover:bg-accent/80 text-white text-sm font-medium disabled:opacity-50 flex items-center gap-2 transition"
        >
          {isFetching ? (
            <>
              <span className="animate-spin inline-block">⟳</span> Analyzing...
            </>
          ) : analysis ? (
            "Refresh Analysis"
          ) : (
            "✦ Generate AI Analysis"
          )}
        </button>
      </div>

      {/* Idle state */}
      {!analysis && !isLoading && !isFetching && (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <div className="text-4xl mb-3">✦</div>
          <p className="text-gray-300 font-medium mb-1">Gemini AI is ready</p>
          <p className="text-gray-500 text-sm">
            Click "Generate AI Analysis" to get Gemini's buy/sell picks based on live news, signals, and market data.
          </p>
        </div>
      )}

      {/* Loading skeleton */}
      {(isLoading || isFetching) && !analysis && (
        <div className="space-y-4">
          <div className="rounded-xl bg-card border border-border p-4 animate-pulse h-24" />
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="rounded-xl bg-card border border-border p-4 animate-pulse h-40" />
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {analysis && !isFetching && (
        <div className="space-y-5">
          {/* Summary banner */}
          <div className={`rounded-xl border p-4 ${OUTLOOK_STYLES[analysis.market_outlook] ?? OUTLOOK_STYLES.neutral}`}>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider">Market Outlook</span>
              <span className={`px-2 py-0.5 rounded border text-xs font-bold uppercase ${OUTLOOK_STYLES[analysis.market_outlook] ?? ""}`}>
                {analysis.market_outlook}
              </span>
            </div>
            <p className="text-sm text-gray-200 leading-relaxed">{analysis.summary}</p>
          </div>

          {/* Stock picks grid */}
          {analysis.picks.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-400 mb-3">
                AI Stock Picks ({analysis.picks.length})
              </h4>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {analysis.picks.map((pick, i) => (
                  <AIPickCard key={`${pick.ticker}-${i}`} pick={pick} />
                ))}
              </div>
            </div>
          )}

          {/* Sector views + key risks */}
          <div className="grid md:grid-cols-2 gap-4">
            {analysis.sector_views.length > 0 && (
              <div className="rounded-xl bg-card border border-border p-4">
                <h4 className="text-sm font-semibold text-gray-400 mb-3">Sector Outlook</h4>
                <div className="space-y-2">
                  {analysis.sector_views.map((sv, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className={`text-xs font-bold mt-0.5 ${SECTOR_OUTLOOK[sv.outlook] ?? "text-gray-400"}`}>
                        {sv.outlook === "positive" ? "▲" : sv.outlook === "negative" ? "▼" : "→"}
                      </span>
                      <div>
                        <span className="text-sm text-gray-300 font-medium">{sv.sector}</span>
                        <p className="text-xs text-gray-500">{sv.reason}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analysis.key_risks.length > 0 && (
              <div className="rounded-xl bg-card border border-red-500/20 p-4">
                <h4 className="text-sm font-semibold text-red-400 mb-3">⚠ Key Risks</h4>
                <ul className="space-y-1.5">
                  {analysis.key_risks.map((risk, i) => (
                    <li key={i} className="text-xs text-gray-400 flex items-start gap-2">
                      <span className="text-red-500 mt-0.5">•</span>
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {analysis.error && (
            <p className="text-xs text-red-400 text-center">Note: {analysis.error}</p>
          )}
        </div>
      )}

      {/* Refreshing overlay */}
      {isFetching && analysis && (
        <div className="text-center py-2">
          <span className="text-xs text-gray-500 animate-pulse">Gemini is re-analyzing the market...</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Intelligence Page
// ---------------------------------------------------------------------------
export default function Intelligence() {
  const queryClient = useQueryClient();
  const [predFilter, setPredFilter] = useState<"all" | "buy" | "sell" | "watch">("all");
  const [activeTab, setActiveTab] = useState<"predictions" | "events" | "ai">("predictions");
  const [minConf, setMinConf] = useState(40);

  const { data: pulse, isLoading: pulseLoading } = useQuery<MarketPulse>({
    queryKey: ["market-pulse"],
    queryFn: fetchMarketPulse,
    refetchInterval: 5 * 60 * 1000,
  });

  const { data: predictions = [], isLoading: predsLoading } = useQuery<Prediction[]>({
    queryKey: ["predictions", minConf],
    queryFn: () => fetchPredictions(80, minConf),
    refetchInterval: 5 * 60 * 1000,
  });

  const { data: events = [], isLoading: eventsLoading } = useQuery<MarketEvent[]>({
    queryKey: ["events"],
    queryFn: () => fetchEvents(60),
    refetchInterval: 5 * 60 * 1000,
  });

  const refreshMutation = useMutation({
    mutationFn: refresh,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["predictions"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["market-pulse"] });
    },
  });

  const filteredPredictions = predictions.filter((p) => {
    if (predFilter === "buy")   return p.action.includes("BUY");
    if (predFilter === "sell")  return p.action.includes("SELL");
    if (predFilter === "watch") return p.action === "WATCH" || p.action === "WAIT";
    return true;
  });

  const highImpactEvents = events.filter((e) => e.impact === "high");
  const recentEvents = events.slice(0, 30);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Intelligence Feed</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Event detection · Predictive signals · Timing intelligence
          </p>
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="px-4 py-2 rounded bg-accent hover:bg-accent/80 text-white font-medium disabled:opacity-50 flex items-center gap-2"
        >
          {refreshMutation.isPending ? (
            <>
              <span className="animate-spin">⟳</span> Analyzing...
            </>
          ) : (
            "Refresh Intelligence"
          )}
        </button>
      </div>

      {/* Market Pulse */}
      {pulseLoading ? (
        <div className="rounded-xl border border-border bg-card p-4 animate-pulse h-24" />
      ) : pulse ? (
        <MarketPulseBanner pulse={pulse} />
      ) : null}

      {/* Breaking events banner (high-impact only) */}
      {highImpactEvents.length > 0 && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
          <p className="text-xs text-red-400 font-bold mb-2">⚡ HIGH-IMPACT EVENTS (Last 48h)</p>
          <div className="space-y-2">
            {highImpactEvents.slice(0, 5).map((e) => (
              <EventCard key={e.id} event={e} />
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab("predictions")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "predictions"
              ? "border-accent text-accent"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          Predictions ({filteredPredictions.length})
        </button>
        <button
          onClick={() => setActiveTab("events")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "events"
              ? "border-accent text-accent"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          Events ({recentEvents.length})
        </button>
        <button
          onClick={() => setActiveTab("ai")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "ai"
              ? "border-accent text-accent"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <span>✦</span> AI Assistant
        </button>
      </div>

      {/* Predictions Tab */}
      {activeTab === "predictions" && (
        <div>
          {/* Filter bar */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="flex gap-2">
              {(["all", "buy", "sell", "watch"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setPredFilter(f)}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition ${
                    predFilter === f
                      ? "bg-accent text-white"
                      : "bg-surface border border-border text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {f === "all" ? "All" : f === "buy" ? "Buy signals" : f === "sell" ? "Sell signals" : "Watch"}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <label className="text-xs text-gray-500">Min confidence:</label>
              <select
                value={minConf}
                onChange={(e) => setMinConf(Number(e.target.value))}
                className="px-2 py-1 rounded bg-surface border border-border text-sm"
              >
                {[30, 40, 50, 60, 70].map((v) => (
                  <option key={v} value={v}>{v}%</option>
                ))}
              </select>
            </div>
          </div>

          {predsLoading ? (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="rounded-xl bg-card border border-border p-4 animate-pulse h-48" />
              ))}
            </div>
          ) : filteredPredictions.length === 0 ? (
            <div className="rounded-xl bg-card border border-border p-8 text-center">
              <p className="text-gray-400 text-lg mb-2">No predictions yet</p>
              <p className="text-gray-600 text-sm mb-4">
                Click "Refresh Intelligence" to fetch latest news and generate predictions.
              </p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredPredictions.map((pred) => (
                <PredictionCard key={pred.id} pred={pred} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Events Tab */}
      {activeTab === "events" && (
        <div>
          {eventsLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-16 rounded-lg bg-card border border-border animate-pulse" />
              ))}
            </div>
          ) : recentEvents.length === 0 ? (
            <div className="rounded-xl bg-card border border-border p-8 text-center">
              <p className="text-gray-400">No events detected yet. Click Refresh Intelligence.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentEvents.map((e) => (
                <EventCard key={e.id} event={e} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI Assistant Tab */}
      {activeTab === "ai" && (
        <div className="space-y-6">
          <AIAnalysisPanel />
          <AIChat db_context_ready={true} />
        </div>
      )}

      <p className="text-xs text-gray-600 text-center pb-4">
        Predictions are rule-based estimates for educational purposes only. Not financial advice.
      </p>
    </div>
  );
}
