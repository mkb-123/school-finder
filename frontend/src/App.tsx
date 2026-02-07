import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import SchoolList from "./pages/SchoolList";
import SchoolDetail from "./pages/SchoolDetail";
import PrivateSchools from "./pages/PrivateSchools";
import PrivateSchoolDetail from "./pages/PrivateSchoolDetail";
import Compare from "./pages/Compare";
import TermDates from "./pages/TermDates";
import DecisionSupport from "./pages/DecisionSupport";
import Journey from "./pages/Journey";

export default function App() {
  return (
    <div className="min-h-screen bg-stone-50">
      {/* Skip to content link for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-brand-600 focus:px-4 focus:py-2 focus:text-white focus:outline-none"
      >
        Skip to main content
      </a>
      <Navbar />
      <div id="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/schools" element={<SchoolList />} />
          <Route path="/schools/:id" element={<SchoolDetail />} />
          <Route path="/private-schools" element={<PrivateSchools />} />
          <Route path="/private-schools/:id" element={<PrivateSchoolDetail />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/term-dates" element={<TermDates />} />
          <Route path="/decision-support" element={<DecisionSupport />} />
          <Route path="/journey" element={<Journey />} />
        </Routes>
      </div>
    </div>
  );
}
