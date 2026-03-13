const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const API = `${BASE}/api`;

export async function fetchNews(limit = 50) {
  const res = await fetch(`${API}/news?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch news");
  return res.json();
}

export async function fetchStocks() {
  const res = await fetch(`${API}/stocks`);
  if (!res.ok) throw new Error("Failed to fetch stocks");
  return res.json();
}

export async function fetchSignals() {
  const res = await fetch(`${API}/signals`);
  if (!res.ok) throw new Error("Failed to fetch signals");
  return res.json();
}

export async function fetchDashboard() {
  const res = await fetch(`${API}/dashboard`);
  if (!res.ok) throw new Error("Failed to fetch dashboard");
  return res.json();
}

export async function fetchWatchlist() {
  const res = await fetch(`${API}/watchlist`);
  if (!res.ok) throw new Error("Failed to fetch watchlist");
  return res.json();
}

export async function addToWatchlist(ticker: string) {
  const res = await fetch(`${API}/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: ticker.toUpperCase() }),
  });
  if (!res.ok) throw new Error("Failed to add ticker");
  return res.json();
}

export async function removeFromWatchlist(ticker: string) {
  const res = await fetch(`${API}/watchlist/${ticker}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove ticker");
  return res.json();
}

export async function refresh() {
  const res = await fetch(`${API}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to refresh");
  return res.json();
}

export async function fetchStockDetail(ticker: string) {
  const res = await fetch(`${API}/stock/${ticker}`);
  if (!res.ok) throw new Error("Failed to fetch stock");
  return res.json();
}

export async function fetchIpos(limit = 20) {
  const res = await fetch(`${API}/ipos?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch IPOs");
  return res.json();
}

export async function fetchMarket(limit = 15) {
  const res = await fetch(`${API}/market?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch market data");
  return res.json();
}

export async function fetchCompanies() {
  const res = await fetch(`${API}/companies`);
  if (!res.ok) throw new Error("Failed to fetch companies");
  return res.json();
}

export async function fetchSuggestions() {
  const res = await fetch(`${API}/suggestions`);
  if (!res.ok) throw new Error("Failed to fetch suggestions");
  return res.json();
}

export async function fetchHoldings() {
  const res = await fetch(`${API}/holdings`);
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return res.json();
}

export async function addHolding(ticker: string, quantity: number, buyPrice: number, notes?: string) {
  const res = await fetch(`${API}/holdings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, quantity, buy_price: buyPrice, notes: notes || null }),
  });
  if (!res.ok) throw new Error("Failed to add holding");
  return res.json();
}

export async function removeHolding(id: number) {
  const res = await fetch(`${API}/holdings/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove holding");
  return res.json();
}

export async function fetchPredictions(limit = 50, minConfidence = 40) {
  const res = await fetch(`${API}/predictions?limit=${limit}&min_confidence=${minConfidence}`);
  if (!res.ok) throw new Error("Failed to fetch predictions");
  return res.json();
}

export async function fetchPredictionsForTicker(ticker: string) {
  const res = await fetch(`${API}/predictions/${ticker}`);
  if (!res.ok) throw new Error("Failed to fetch predictions for ticker");
  return res.json();
}

export async function fetchEvents(limit = 50, impact?: string) {
  const url = impact ? `${API}/events?limit=${limit}&impact=${impact}` : `${API}/events?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

export async function fetchMarketPulse() {
  const res = await fetch(`${API}/market-pulse`);
  if (!res.ok) throw new Error("Failed to fetch market pulse");
  return res.json();
}

export async function searchStocks(q: string, limit = 15) {
  if (!q || q.trim().length < 1) return [];
  const res = await fetch(`${API}/search?q=${encodeURIComponent(q.trim())}&limit=${limit}`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchQuote(symbol: string) {
  const res = await fetch(`${API}/quote/${symbol.replace(/\.(NS|BO)$/i, "")}`);
  if (!res.ok) throw new Error("Quote not found");
  return res.json();
}

export async function fetchAIAnalysis() {
  const res = await fetch(`${API}/ai/analysis`);
  if (!res.ok) throw new Error("Failed to fetch AI analysis");
  return res.json();
}

export async function chatWithAI(message: string) {
  const res = await fetch(`${API}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error("Failed to chat with AI");
  return res.json();
}
