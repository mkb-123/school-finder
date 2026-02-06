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
    <div className="min-h-screen bg-gray-50">
      <Navbar />
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
  );
}
