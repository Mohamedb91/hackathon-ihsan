import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, RefreshCw, Camera, AlertCircle, X } from 'lucide-react';
import { toast } from 'sonner';
import L from 'leaflet';

// Fix Leaflet default marker icons
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function MapView({ cameras, onCameraClick }) {
  const map = useMap();

  // Fit bounds to show all cameras
  useEffect(() => {
    if (cameras.length > 0) {
      const bounds = cameras.map(cam => [cam.lat, cam.lon]);
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [cameras, map]);

  return (
    <>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {cameras.map((camera) => (
        <Marker
          key={camera.cameraId}
          position={[camera.lat, camera.lon]}
          eventHandlers={{
            click: () => onCameraClick(camera)
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong>{camera.name}</strong>
              <br />
              <span className="text-xs text-slate-500">Click to view details</span>
            </div>
          </Popup>
        </Marker>
      ))}
    </>
  );
}

function CameraDrawer({ camera, onClose }) {
  const [observation, setObservation] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  useEffect(() => {
    loadCameraData();
  }, [camera]);

  useEffect(() => {
    if (observation && observation.snapshotUrl && imageRef.current && canvasRef.current) {
      drawBoundingBoxes();
    }
  }, [observation]);

  const loadCameraData = async () => {
    setLoading(true);
    try {
      // Load latest observation
      const obsRes = await fetch(`${API}/tii/cameras/${camera.cameraId}/latest`);
      if (obsRes.ok) {
        const obsData = await obsRes.json();
        setObservation(obsData);
      }

      // Load timeline
      const timelineRes = await fetch(`${API}/tii/observations?cameraId=${camera.cameraId}&limit=5`);
      if (timelineRes.ok) {
        const timelineData = await timelineRes.json();
        setTimeline(timelineData);
      }
    } catch (error) {
      console.error('Failed to load camera data:', error);
      toast.error('Failed to load camera data');
    } finally {
      setLoading(false);
    }
  };

  const drawBoundingBoxes = () => {
    const canvas = canvasRef.current;
    const image = imageRef.current;

    if (!canvas || !image || !observation.boxes || observation.boxes.length === 0) return;

    const ctx = canvas.getContext('2d');

    const draw = () => {
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      observation.boxes.forEach((box, index) => {
        const { x, y, w, h, confidence } = box;

        // Draw box
        ctx.strokeStyle = '#ff4444';
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);

        // Draw label
        const label = `Pothole ${index + 1} (${(confidence * 100).toFixed(0)}%)`;
        ctx.font = '14px Arial';
        const textWidth = ctx.measureText(label).width;

        ctx.fillStyle = '#ff4444';
        ctx.fillRect(x, y - 25, textWidth + 10, 20);

        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, x + 5, y - 10);
      });
    };

    if (image.complete) {
      draw();
    } else {
      image.onload = draw;
    }
  };

  return (
    <div className="fixed right-0 top-0 h-full w-full md:w-[500px] bg-white shadow-2xl z-[1000] overflow-y-auto">
      <div className="sticky top-0 bg-white border-b p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {camera.name}
          </h2>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} data-testid="close-drawer">
          <X className="w-5 h-5" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : (
          <>
            {observation && observation.snapshotUrl ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Latest Snapshot</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="relative">
                      <img
                        ref={imageRef}
                        src={observation.snapshotUrl}
                        alt={camera.name}
                        className="w-full rounded-lg"
                        crossOrigin="anonymous"
                        data-testid="camera-snapshot"
                      />
                      {observation.boxes && observation.boxes.length > 0 && (
                        <canvas
                          ref={canvasRef}
                          className="absolute top-0 left-0 w-full h-full pointer-events-none"
                          style={{ maxWidth: '100%' }}
                        />
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      {new Date(observation.timestamp).toLocaleString()}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Detection Result</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {observation.errored ? (
                      <div className="flex items-center gap-2 text-red-600">
                        <AlertCircle className="w-4 h-4" />
                        <span className="text-sm">Error: {observation.errorMessage}</span>
                      </div>
                    ) : (
                      <>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-600 text-sm">Potholes Detected:</span>
                          <span className="text-xl font-bold text-blue-600" data-testid="drawer-pothole-count">
                            {observation.count}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-600 text-sm">Engine:</span>
                          <span className="font-medium text-sm">{observation.engine}</span>
                        </div>
                        {observation.notes && (
                          <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded">
                            {observation.notes}
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              </>
            ) : (
              <Card>
                <CardContent className="py-12 text-center text-slate-500">
                  <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No observations yet for this camera</p>
                </CardContent>
              </Card>
            )}

            {timeline.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Recent History</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {timeline.map((obs, idx) => (
                      <div key={idx} className="flex justify-between items-center text-sm border-b pb-2 last:border-0">
                        <span className="text-slate-600">
                          {new Date(obs.timestamp).toLocaleDateString()}
                        </span>
                        <span className={`font-medium ${obs.errored ? 'text-red-600' : 'text-blue-600'}`}>
                          {obs.errored ? 'Error' : `${obs.count} pothole${obs.count !== 1 ? 's' : ''}`}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function TrafficCams() {
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadStatus, 30000); // Refresh status every 30s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      await Promise.all([loadCameras(), loadStatus()]);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadCameras = async () => {
    try {
      const res = await fetch(`${API}/tii/cameras`);
      if (res.ok) {
        const data = await res.json();
        setCameras(data);
      }
    } catch (error) {
      console.error('Failed to load cameras:', error);
    }
  };

  const loadStatus = async () => {
    try {
      const res = await fetch(`${API}/tii/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (error) {
      console.error('Failed to load status:', error);
    }
  };

  const handleSyncCameras = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API}/tii/sync-cameras`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        toast.success(`Synced: ${data.inserted} new, ${data.updated} updated, ${data.camerasActive} active`);
        await loadData();
      } else {
        throw new Error('Sync failed');
      }
    } catch (error) {
      console.error('Sync error:', error);
      toast.error('Failed to sync cameras');
    } finally {
      setSyncing(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    try {
      const res = await fetch(`${API}/tii/run-once`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        toast.success(`Processed ${data.stats.processed} cameras (${data.stats.ok} ok, ${data.stats.errors} errors)`);
        await loadStatus();
      } else {
        throw new Error('Run failed');
      }
    } catch (error) {
      console.error('Run error:', error);
      toast.error('Failed to run detection cycle');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-12 h-12 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="relative h-screen">
      {/* Map */}
      <MapContainer
        center={[53.3498, -6.2603]} // Dublin, Ireland
        zoom={7}
        style={{ height: '100%', width: '100%' }}
        data-testid="traffic-cams-map"
      >
        <MapView cameras={cameras} onCameraClick={setSelectedCamera} />
      </MapContainer>

      {/* Control Panel */}
      <div className="absolute top-4 left-4 z-[999] space-y-2">
        <Card className="shadow-lg">
          <CardContent className="p-4 space-y-3">
            <h1 className="text-xl font-bold" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              TII Traffic Cameras
            </h1>
            <div className="text-sm text-slate-600 space-y-1">
              <div>Active Cameras: <strong>{status?.camerasActive || 0}</strong></div>
              {status?.lastRunAt && (
                <div className="text-xs">
                  Last run: {new Date(status.lastRunAt).toLocaleString()}
                </div>
              )}
              {status?.lastCycle && (
                <div className="text-xs text-slate-500">
                  Last cycle: {status.lastCycle.ok} ok, {status.lastCycle.errors} errors
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Button
                onClick={handleSyncCameras}
                disabled={syncing}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                size="sm"
                data-testid="sync-cameras-btn"
              >
                {syncing ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Syncing...</>
                ) : (
                  <><RefreshCw className="w-4 h-4 mr-2" />Sync Cameras</>
                )}
              </Button>
              <Button
                onClick={handleRunNow}
                disabled={running}
                className="w-full"
                variant="outline"
                size="sm"
                data-testid="run-now-btn"
              >
                {running ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Running...</>
                ) : (
                  <><Camera className="w-4 h-4 mr-2" />Run Now</>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Attribution */}
      <div className="absolute bottom-4 right-4 z-[999] bg-white rounded-lg shadow-lg px-4 py-2">
        <p className="text-xs text-slate-600">
          Source:{' '}
          <a
            href="https://data.gov.ie/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            Transport Infrastructure Ireland (CC-BY 4.0)
          </a>
        </p>
      </div>

      {/* Camera Drawer */}
      {selectedCamera && (
        <CameraDrawer
          camera={selectedCamera}
          onClose={() => setSelectedCamera(null)}
        />
      )}
    </div>
  );
}