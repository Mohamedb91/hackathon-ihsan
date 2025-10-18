import { useState, useRef, useEffect } from 'react';
import '@/App.css';
import { Upload, Loader2, AlertCircle, CheckCircle2, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function PotholeDetector() {
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [detectionResult, setDetectionResult] = useState(null);
  const [latency, setLatency] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  const handleFileSelect = (file) => {
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
      toast.error('Please select a valid image file');
      return;
    }

    setSelectedImage(file);
    setDetectionResult(null);
    setLatency(null);
    
    const reader = new FileReader();
    reader.onload = (e) => {
      setImagePreview(e.target.result);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    handleFileSelect(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const detectPotholes = async () => {
    if (!selectedImage) return;

    setIsDetecting(true);
    const startTime = Date.now();

    try {
      const formData = new FormData();
      formData.append('image', selectedImage);

      const response = await fetch(`${API}/detect`, {
        method: 'POST',
        body: formData,
      });

      const elapsed = Date.now() - startTime;
      setLatency(elapsed);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Detection failed');
      }

      const result = await response.json();
      setDetectionResult(result);
      
      toast.success(`Detected ${result.count} pothole${result.count !== 1 ? 's' : ''}`);
    } catch (error) {
      console.error('Detection error:', error);
      toast.error(`Detection failed: ${error.message}`);
    } finally {
      setIsDetecting(false);
    }
  };

  // Draw bounding boxes on canvas
  useEffect(() => {
    if (!imagePreview || !detectionResult || !canvasRef.current || !imageRef.current) return;

    const canvas = canvasRef.current;
    const image = imageRef.current;
    const ctx = canvas.getContext('2d');

    // Wait for image to load
    const drawBoxes = () => {
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw bounding boxes
      detectionResult.boxes.forEach((box, index) => {
        const { x, y, w, h, confidence } = box;
        
        // Draw box
        ctx.strokeStyle = '#ff4444';
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);
        
        // Draw label background
        const label = `Pothole ${index + 1} (${(confidence * 100).toFixed(0)}%)`;
        ctx.font = '14px Arial';
        const textWidth = ctx.measureText(label).width;
        
        ctx.fillStyle = '#ff4444';
        ctx.fillRect(x, y - 25, textWidth + 10, 20);
        
        // Draw label text
        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, x + 5, y - 10);
      });
    };

    if (image.complete) {
      drawBoxes();
    } else {
      image.onload = drawBoxes;
    }
  }, [imagePreview, detectionResult]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header with Back Button */}
        <div className="mb-6">
          <Link to="/">
            <Button variant="ghost" className="gap-2">
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </Button>
          </Link>
        </div>

        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 mb-3" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            Pothole Detector
          </h1>
          <p className="text-lg text-slate-600" style={{ fontFamily: 'Inter, sans-serif' }}>
            AI-powered pothole detection using Google Gemini 2.0 Flash
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Upload Section */}
          <Card className="shadow-lg border-slate-200">
            <CardContent className="p-6">
              <h2 className="text-xl font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Upload Image
              </h2>
              
              <div
                data-testid="drop-zone"
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
                  isDragging
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-slate-300 hover:border-blue-400 hover:bg-slate-50'
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-12 h-12 mx-auto mb-4 text-slate-400" />
                <p className="text-slate-700 mb-2 font-medium">Drop an image here or click to browse</p>
                <p className="text-sm text-slate-500">Supports JPEG and PNG files</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png"
                  className="hidden"
                  onChange={(e) => handleFileSelect(e.target.files[0])}
                  data-testid="file-input"
                />
              </div>

              {selectedImage && (
                <div className="mt-4">
                  <p className="text-sm text-slate-600 mb-3">Selected: <span className="font-medium">{selectedImage.name}</span></p>
                  <Button
                    data-testid="detect-button"
                    onClick={detectPotholes}
                    disabled={isDetecting}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {isDetecting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Detecting...
                      </>
                    ) : (
                      'Detect Potholes'
                    )}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Results Section */}
          <Card className="shadow-lg border-slate-200">
            <CardContent className="p-6">
              <h2 className="text-xl font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Detection Results
              </h2>
              
              {!detectionResult ? (
                <div className="text-center py-12 text-slate-500">
                  <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>Upload an image and click "Detect Potholes" to see results</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                    <span className="text-slate-600">Status:</span>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-green-600" />
                      <span className="font-semibold text-slate-900">Complete</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                    <span className="text-slate-600">Potholes Detected:</span>
                    <span className="text-2xl font-bold text-blue-600" data-testid="pothole-count">{detectionResult.count}</span>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                    <span className="text-slate-600">Detection Time:</span>
                    <span className="font-semibold text-slate-900" data-testid="latency">{(latency / 1000).toFixed(2)}s</span>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                    <span className="text-slate-600">Engine:</span>
                    <span className="font-semibold text-slate-900" data-testid="engine">{detectionResult.engine}</span>
                  </div>
                  
                  {detectionResult.notes && (
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <p className="text-sm text-blue-800">{detectionResult.notes}</p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Image Preview with Bounding Boxes */}
        {imagePreview && (
          <Card className="mt-6 shadow-lg border-slate-200">
            <CardContent className="p-6">
              <h2 className="text-xl font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                Image Analysis
              </h2>
              <div className="relative inline-block max-w-full">
                <img
                  ref={imageRef}
                  src={imagePreview}
                  alt="Preview"
                  className="max-w-full h-auto rounded-lg"
                  data-testid="preview-image"
                />
                <canvas
                  ref={canvasRef}
                  className="absolute top-0 left-0 max-w-full h-auto pointer-events-none"
                  style={{ width: imageRef.current?.clientWidth, height: imageRef.current?.clientHeight }}
                  data-testid="canvas-overlay"
                />
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default PotholeDetector;