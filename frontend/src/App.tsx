import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import StockDetail from "./pages/StockDetail";
import Suggestions from "./pages/Suggestions";
import Intelligence from "./pages/Intelligence";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/intelligence" element={<Intelligence />} />
          <Route path="/suggestions" element={<Suggestions />} />
          <Route path="/stock/:ticker" element={<StockDetail />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
