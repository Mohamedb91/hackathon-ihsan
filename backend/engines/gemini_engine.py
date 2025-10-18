import json
import base64
import io
import logging
from PIL import Image
from typing import Dict, Any
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from schemas import DetectionResult, Box
from core.config import config

logger = logging.getLogger(__name__)

class GeminiEngine:
    """Gemini vision engine for pothole detection."""
    
    def __init__(self):
        """Initialize the Gemini engine."""
        self.api_key = config.GEMINI_API_KEY
        self.model = config.GEMINI_VISION_MODEL
        
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string.
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded image string
        """
        buffer = io.BytesIO()
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        image.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def _build_prompt(self) -> str:
        """Build the strict JSON prompt for Gemini.
        
        Returns:
            Prompt string
        """
        return """Analyze this image for potholes (damaged road surfaces with holes, cracks, or depressions).

Return ONLY a JSON object with these exact keys (no extra text, no markdown, no explanation):

{
  "potholes_present": true or false,
  "count": number of potholes detected (integer),
  "boxes": [
    {"x": top-left x pixel coordinate, "y": top-left y pixel coordinate, "w": width in pixels, "h": height in pixels, "confidence": 0.0 to 1.0}
  ]
}

Rules:
- Set potholes_present to true if ANY potholes are detected, false otherwise
- count must be an integer (0 if none detected)
- boxes array: provide bounding boxes if you can reliably locate potholes. If uncertain about exact locations, return empty array [] but still set potholes_present correctly
- x,y are top-left corner coordinates in the original image pixel space
- w,h are width and height in pixels
- confidence is your certainty for each detection (0.0 to 1.0)

Return ONLY the JSON object, nothing else."""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse and validate Gemini response.
        
        Args:
            response: Raw response from Gemini
            
        Returns:
            Validated dictionary with detection results
            
        Raises:
            ValueError: If response cannot be parsed
        """
        # Strip markdown code fences if present
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()
        
        # Parse JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response (first 500 chars): {response[:500]}")
            raise ValueError(f"Invalid JSON response from Gemini: {str(e)}")
        
        # Validate and coerce fields
        result = {
            'potholes_present': bool(data.get('potholes_present', False)),
            'count': int(data.get('count', 0)),
            'boxes': []
        }
        
        # Parse boxes if present
        boxes = data.get('boxes', [])
        if isinstance(boxes, list):
            for box in boxes:
                try:
                    result['boxes'].append({
                        'x': float(box.get('x', 0)),
                        'y': float(box.get('y', 0)),
                        'w': float(box.get('w', 0)),
                        'h': float(box.get('h', 0)),
                        'confidence': float(box.get('confidence', 0.5))
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid box: {box}, error: {e}")
        
        # Sync count with boxes if count is missing
        if result['count'] == 0 and len(result['boxes']) > 0:
            result['count'] = len(result['boxes'])
        
        return result
    
    async def detect_potholes(self, image: Image.Image) -> DetectionResult:
        """Detect potholes in an image using Gemini.
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            DetectionResult with detection information
            
        Raises:
            Exception: If detection fails
        """
        try:
            # Convert image to base64
            image_b64 = self._image_to_base64(image)
            
            # Create chat instance
            chat = LlmChat(
                api_key=self.api_key,
                session_id="pothole-detection",
                system_message="You are a pothole detection system. Return only valid JSON."
            ).with_model("gemini", self.model)
            
            # Create image content
            image_content = ImageContent(image_base64=image_b64)
            
            # Create message with image
            message = UserMessage(
                text=self._build_prompt(),
                file_contents=[image_content]
            )
            
            # Send to Gemini
            logger.info(f"Sending image to Gemini model: {self.model}")
            response = await chat.send_message(message)
            logger.info(f"Received response from Gemini (length: {len(response)})")
            
            # Parse response
            parsed = self._parse_response(response)
            
            # Create DetectionResult
            boxes = [Box(**box) for box in parsed['boxes']]
            result = DetectionResult(
                engine="gemini",
                potholes_present=parsed['potholes_present'],
                count=parsed['count'],
                boxes=boxes,
                notes=f"Model: {self.model}"
            )
            
            logger.info(f"Detection complete: {result.count} potholes detected")
            return result
            
        except Exception as e:
            logger.error(f"Gemini detection failed: {str(e)}", exc_info=True)
            raise Exception(f"Pothole detection failed: {str(e)}")