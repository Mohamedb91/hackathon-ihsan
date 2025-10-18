# Pothole Detection System

A production-ready infrastructure monitoring system that detects potholes in images using **Google Gemini 2.0 Flash** (multimodal vision). Features automated monitoring of Transport Infrastructure Ireland (TII) traffic cameras with real-time pothole detection.

## Features

- **Pothole Detector**: Upload any image for instant AI-powered pothole detection
- **TII Camera Integration**: Automated monitoring of Ireland's traffic camera network
  - Automatic camera discovery from TII ArcGIS FeatureServer
  - Scheduled polling every 15 minutes (configurable)
  - Real-time pothole detection on camera snapshots
  - Interactive map visualization with Leaflet
  - Historical tracking of observations per camera
- **Backend**: FastAPI with Gemini 2.0 Flash integration and MongoDB storage
- **Frontend**: Modern React UI with drag-drop upload, interactive maps, and canvas overlays
- **Batch Evaluator**: Script to process multiple images and generate JSONL results
- **Strict JSON API**: Clean, typed responses with pothole presence, count, and bounding boxes

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, emergentintegrations
- **Frontend**: React 19, Tailwind CSS, shadcn/ui
- **Vision Model**: Google Gemini 2.0 Flash (`gemini-2.0-flash`)

## Project Structure

```
pothole-detector/
├── backend/
│   ├── app.py                 # Main FastAPI application
│   ├── server.py              # Server entry point
│   ├── schemas.py             # Pydantic models
│   ├── utils.py               # Utility functions
│   ├── core/
│   │   └── config.py          # Configuration
│   └── engines/
│       ├── __init__.py
│       └── gemini_engine.py   # Gemini integration
├── frontend/
│   └── src/
│       ├── App.js             # React application
│       └── App.css            # Styles
├── scripts/
│   └── eval_kaggle.py         # Batch evaluator
└── README.md
```

## Setup

### Backend

1. **Install dependencies**:
```bash
cd /app/backend
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
pip install fastapi uvicorn pillow numpy python-dotenv python-multipart
```

2. **Environment variables** (already configured in `.env`):
```bash
EMERGENT_LLM_KEY=sk-emergent-4B6C5048eB9Ec00B6E
GEMINI_VISION_MODEL=gemini-2.0-flash
HOST=0.0.0.0
PORT=8001
```

3. **Restart backend**:
```bash
sudo supervisorctl restart backend
```

### Frontend

Frontend is already set up and running with hot reload.

## API Endpoints

### `POST /api/detect`

Detect potholes in an uploaded image.

**Request**:
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `image` (JPEG/PNG file)

**Response** (200 OK):
```json
{
  "engine": "gemini",
  "potholes_present": true,
  "count": 2,
  "boxes": [
    {
      "x": 120,
      "y": 300,
      "w": 210,
      "h": 95,
      "confidence": 0.87
    },
    {
      "x": 640,
      "y": 260,
      "w": 140,
      "h": 80,
      "confidence": 0.79
    }
  ],
  "notes": "Model: gemini-2.0-flash"
}
```

**Field Descriptions**:
- `x`, `y`: Top-left corner coordinates in pixels (original image space)
- `w`, `h`: Width and height in pixels
- `confidence`: Detection confidence (0.0 to 1.0)
- `boxes`: May be empty `[]` if model is uncertain about locations, but `potholes_present` will still be accurate
- `count`: Number of potholes detected

### `GET /api/health`

Health check endpoint.

**Response**:
```json
{
  "status": "ok"
}
```

## Testing

### Using curl

```bash
# Get backend URL
BACKEND_URL=$(cat /app/frontend/.env | grep REACT_APP_BACKEND_URL | cut -d'=' -f2)

# Test with an image
curl -X POST "${BACKEND_URL}/api/detect" \
  -F "image=@/path/to/city_street.jpg" \
  -H "Accept: application/json"
```

### Using the Web UI

1. Open the frontend in your browser
2. Drag and drop an image or click to browse
3. Click "Detect Potholes"
4. View results and bounding boxes overlaid on the image

### Batch Evaluation

Process multiple images from a directory (e.g., Kaggle pothole dataset):

```bash
# Get backend URL
BACKEND_URL=$(cat /app/frontend/.env | grep REACT_APP_BACKEND_URL | cut -d'=' -f2)

# Run batch evaluation
python /app/scripts/eval_kaggle.py \
  --dir "/path/to/kaggle/images" \
  --out gemini_eval.jsonl \
  --url "${BACKEND_URL}/api/detect"
```

**Output**: JSONL file with one result per line:
```json
{"image": "street1.jpg", "status": "success", "elapsed_seconds": 2.45, "response": {...}}
{"image": "street2.jpg", "status": "success", "elapsed_seconds": 2.31, "response": {...}}
```

## How It Works

1. **Image Upload**: User uploads an image via the API or web UI
2. **Validation**: Image is validated (type, size, format)
3. **Gemini Processing**: 
   - Image is converted to base64
   - Sent to Gemini 2.5 Flash with a strict JSON prompt
   - Model analyzes the image and returns pothole detections
4. **Response Parsing**: 
   - JSON response is parsed and validated
   - Bounding boxes are extracted (if available)
   - Result is returned to the client
5. **Visualization**: Frontend displays the image with bounding boxes overlaid on a canvas

## Model Behavior

- **Gemini 2.5 Flash** is instructed to return strict JSON with:
  - `potholes_present`: Boolean indicating if any potholes are detected
  - `count`: Number of potholes
  - `boxes`: Array of bounding boxes (may be empty if uncertain)
  
- If the model can't reliably determine bounding box locations, it returns an empty `boxes` array but still sets `potholes_present` correctly.

- Boxes from Gemini are heuristic; for production use cases requiring higher accuracy, a fine-tuned detector (like YOLO) can be added later.

## Troubleshooting

### Backend not starting

```bash
# Check backend logs
tail -n 100 /var/log/supervisor/backend.err.log

# Verify environment variables
cat /app/backend/.env

# Restart backend
sudo supervisorctl restart backend
```

### API key issues

The Emergent Universal Key (`EMERGENT_LLM_KEY`) is pre-configured. If you see authentication errors:
- Check that the key is in `/app/backend/.env`
- Verify your key balance in Profile → Universal Key
- Restart the backend after updating the key

### Frontend not connecting to backend

```bash
# Check backend URL
cat /app/frontend/.env | grep REACT_APP_BACKEND_URL

# Test backend health
BACKEND_URL=$(cat /app/frontend/.env | grep REACT_APP_BACKEND_URL | cut -d'=' -f2)
curl "${BACKEND_URL}/api/health"
```

### TII camera integration issues

```bash
# Check TII scheduler status
curl "${BACKEND_URL}/api/tii/status"

# Manually sync cameras
curl -X POST "${BACKEND_URL}/api/tii/sync-cameras"

# Manually trigger detection cycle
curl -X POST "${BACKEND_URL}/api/tii/run-once"

# View cameras
curl "${BACKEND_URL}/api/tii/cameras" | python -m json.tool
```

**Common issues:**
- **No cameras synced**: Verify `TII_ARCGIS_LAYER_URL` is correct in `.env`
- **Detection errors**: Check snapshot URLs are accessible from the server
- **Scheduler not running**: Check backend logs for startup errors

## Traffic Cameras Setup

### Prerequisites

You need a valid ArcGIS FeatureServer layer URL that provides camera data with:
- Geometry (lat/lon coordinates)
- Attributes including camera metadata and snapshot URLs

### Configuration

1. **Set the FeatureServer URL** in `/app/backend/.env`:

```bash
TII_ARCGIS_LAYER_URL=https://example.com/FeatureServer/0
```

**Important**: The URL must be the **layer root** (ending with `/FeatureServer/0` or similar), NOT the query endpoint.

2. **Optional**: If auto-detection fails to find the snapshot URL field, specify it explicitly:

```bash
TII_SNAPSHOT_FIELD=SNAPSHOT_URL
```

### Validation

Test your FeatureServer URL before configuring:

```bash
curl "YOUR_LAYER_URL/query?where=1%3D1&outFields=*&returnGeometry=true&f=json"
```

This should return JSON with a `features` array containing camera data.

**Example Response Structure**:
```json
{
  "features": [
    {
      "attributes": {
        "OBJECTID": 1,
        "Name": "Camera 1",
        "SNAPSHOT_URL": "https://example.com/snapshot.jpg"
      },
      "geometry": {
        "x": -6.2603,
        "y": 53.3498
      }
    }
  ]
}
```

### Usage

1. **Restart Backend** after updating `.env`:
   ```bash
   sudo supervisorctl restart backend
   ```

2. **Sync Cameras**:
   - Navigate to `/traffic-cams` page
   - Click "Sync Cameras" button
   - Or use API: `curl -X POST "${BACKEND_URL}/api/tii/sync-cameras"`

3. **Verify**:
   ```bash
   # Check status
   curl "${BACKEND_URL}/api/tii/status"
   
   # List cameras
   curl "${BACKEND_URL}/api/tii/cameras"
   ```

4. **Automatic Polling**:
   - Once cameras are synced, the scheduler automatically polls every 15 minutes
   - Or manually trigger: Click "Run Now" or `curl -X POST "${BACKEND_URL}/api/tii/run-once?limit=50"`

### Snapshot Field Auto-Detection

The system automatically detects snapshot URL fields by:
1. Checking if `TII_SNAPSHOT_FIELD` is set and exists
2. Searching for attribute keys matching: `image|snapshot|url|photo|picture|jpeg|jpg|camera` (case-insensitive)
3. Validating the value looks like an image URL: `^https?://.*\.(jpg|jpeg|png)(\?.*)?$`

If no valid field is found, the camera is marked as `active: false` with `inactiveReason: "No snapshot field detected"`.

### Frontend Features

- **Empty State**: Shows helpful setup instructions when no cameras are loaded
- **Search**: Filter cameras by name or ID
- **Active Only**: Toggle to show only active cameras
- **Help Modal**: Click "Help" button for detailed setup instructions
- **Per-Camera Detection**: Click any marker, then "Run Detection Now" to process that specific camera
- **Attribution**: TII data source attribution displayed in footer (CC-BY 4.0 compliance)

### Troubleshooting

## License

MIT