import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Analytics } from "@vercel/analytics/react";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import CommandK from "./components/CommandK";
import Landing from "./views/Landing";
import Leaderboard from "./views/Leaderboard";
import Player from "./views/Player";
import Methodology from "./views/Methodology";
import OpenData from "./views/OpenData";
import Story from "./views/Story";
import Compare from "./views/Compare";
import League from "./views/League";
import Referees from "./views/Referees";
import Referee from "./views/Referee";
import Feedback from "./views/Feedback";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export default function App() {
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-dvh flex-col">
      <ScrollToTop />
      <Nav onSearch={() => setSearchOpen(true)} />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/shot-value" element={<Navigate to="/leaderboard?lens=value" replace />} />
          <Route path="/player/:id" element={<Player />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/data" element={<OpenData />} />
          <Route path="/crackdown" element={<Story />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/league" element={<League />} />
          <Route path="/referees" element={<Referees />} />
          <Route path="/referee/:id" element={<Referee />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </main>
      <Footer />
      <CommandK open={searchOpen} onClose={() => setSearchOpen(false)} />
      <Analytics />
    </div>
  );
}
