import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import Results from './pages/Results'
import Dashboard from './pages/Dashboard'
import Reports from './pages/Reports'
import About from './pages/About'

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-surface-base">
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/results/:scanId" element={<Results />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </div>
    </Router>
  )
}
