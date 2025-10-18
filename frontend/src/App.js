import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import axios from "axios";
import { Toaster } from 'sonner';
import PotholeDetector from './pages/PotholeDetector';
import TrafficCams from './pages/TrafficCams';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Home = () => {
  const helloWorldApi = async () => {
    try {
      const response = await axios.get(`${API}/health`);
      console.log('Health check:', response.data);
    } catch (e) {
      console.error(e, `errored out requesting health api`);
    }
  };

  useEffect(() => {
    helloWorldApi();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-16 max-w-4xl">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-slate-900 mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Pothole Detection System
          </h1>
          <p className="text-lg text-slate-600" style={{ fontFamily: 'Inter, sans-serif' }}>
            AI-powered infrastructure monitoring using Google Gemini
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <Link to="/detector" className="group">
            <div className="bg-white rounded-xl shadow-lg p-8 transition-all hover:shadow-xl hover:-translate-y-1">
              <div className="text-4xl mb-4">📸</div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Pothole Detector
              </h2>
              <p className="text-slate-600">
                Upload any image to detect potholes with AI-powered analysis
              </p>
            </div>
          </Link>

          <Link to="/traffic-cams" className="group">
            <div className="bg-white rounded-xl shadow-lg p-8 transition-all hover:shadow-xl hover:-translate-y-1">
              <div className="text-4xl mb-4">🚦</div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Traffic Cameras
              </h2>
              <p className="text-slate-600">
                Monitor TII traffic cameras and track pothole detections in real-time
              </p>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
};

function App() {
  return (
    <>
      <Toaster position="top-right" />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/detector" element={<PotholeDetector />} />
          <Route path="/traffic-cams" element={<TrafficCams />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;