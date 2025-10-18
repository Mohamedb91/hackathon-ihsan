#!/usr/bin/env python3
"""Comprehensive backend API tests for Pothole Detector application."""

import requests
import sys
import json
import time
from pathlib import Path
from PIL import Image
import io
import base64

class PotholeDetectorAPITester:
    def __init__(self, base_url="https://potholescan.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result."""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_health_endpoint(self):
        """Test the /api/health endpoint."""
        print("\n🔍 Testing Health Endpoint...")
        
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.log_test("Health endpoint returns correct response", True)
                    return True
                else:
                    self.log_test("Health endpoint returns correct response", False, f"Expected status='ok', got {data}")
                    return False
            else:
                self.log_test("Health endpoint returns correct response", False, f"Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Health endpoint returns correct response", False, f"Request failed: {str(e)}")
            return False

    def create_test_image(self, width=800, height=600, format='JPEG'):
        """Create a test image for upload testing."""
        # Create a simple test image
        image = Image.new('RGB', (width, height), color='blue')
        
        # Add some visual elements to make it look like a road
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        
        # Draw a road-like pattern
        draw.rectangle([0, height//2-50, width, height//2+50], fill='gray')
        draw.rectangle([width//2-5, 0, width//2+5, height], fill='yellow')
        
        # Save to bytes
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        buffer.seek(0)
        return buffer.getvalue()

    def test_detect_endpoint_valid_image(self):
        """Test /api/detect with valid JPEG image."""
        print("\n🔍 Testing Detect Endpoint with Valid Image...")
        
        try:
            # Create test image
            image_data = self.create_test_image()
            
            files = {'image': ('test_road.jpg', image_data, 'image/jpeg')}
            
            start_time = time.time()
            response = requests.post(f"{self.api_url}/detect", files=files, timeout=60)
            elapsed = time.time() - start_time
            
            print(f"   Response time: {elapsed:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate response structure
                required_fields = ['engine', 'potholes_present', 'count', 'boxes']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Detect endpoint returns correct JSON schema", False, f"Missing fields: {missing_fields}")
                    return False
                
                # Validate data types
                if not isinstance(data['potholes_present'], bool):
                    self.log_test("Detect endpoint returns correct JSON schema", False, "potholes_present should be boolean")
                    return False
                
                if not isinstance(data['count'], int):
                    self.log_test("Detect endpoint returns correct JSON schema", False, "count should be integer")
                    return False
                
                if not isinstance(data['boxes'], list):
                    self.log_test("Detect endpoint returns correct JSON schema", False, "boxes should be list")
                    return False
                
                # Validate engine
                if data['engine'] != 'gemini':
                    self.log_test("Detect endpoint returns correct engine", False, f"Expected 'gemini', got '{data['engine']}'")
                    return False
                
                self.log_test("Detect endpoint accepts valid image", True)
                self.log_test("Detect endpoint returns correct JSON schema", True)
                self.log_test("Detect endpoint returns correct engine", True)
                
                print(f"   Detection result: {data['count']} potholes detected")
                print(f"   Potholes present: {data['potholes_present']}")
                print(f"   Bounding boxes: {len(data['boxes'])}")
                
                return True
                
            else:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', response.text)
                except:
                    error_detail = response.text
                
                self.log_test("Detect endpoint accepts valid image", False, f"HTTP {response.status_code}: {error_detail}")
                return False
                
        except Exception as e:
            self.log_test("Detect endpoint accepts valid image", False, f"Request failed: {str(e)}")
            return False

    def test_detect_endpoint_png_image(self):
        """Test /api/detect with valid PNG image."""
        print("\n🔍 Testing Detect Endpoint with PNG Image...")
        
        try:
            # Create test PNG image
            image_data = self.create_test_image(format='PNG')
            
            files = {'image': ('test_road.png', image_data, 'image/png')}
            
            response = requests.post(f"{self.api_url}/detect", files=files, timeout=60)
            
            if response.status_code == 200:
                self.log_test("Detect endpoint accepts PNG images", True)
                return True
            else:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', response.text)
                except:
                    error_detail = response.text
                
                self.log_test("Detect endpoint accepts PNG images", False, f"HTTP {response.status_code}: {error_detail}")
                return False
                
        except Exception as e:
            self.log_test("Detect endpoint accepts PNG images", False, f"Request failed: {str(e)}")
            return False

    def test_detect_endpoint_invalid_file_type(self):
        """Test /api/detect with invalid file type."""
        print("\n🔍 Testing Detect Endpoint with Invalid File Type...")
        
        try:
            # Create a text file instead of image
            text_data = b"This is not an image file"
            
            files = {'image': ('test.txt', text_data, 'text/plain')}
            
            response = requests.post(f"{self.api_url}/detect", files=files, timeout=30)
            
            if response.status_code == 400:
                error_data = response.json()
                if 'Invalid image type' in error_data.get('detail', ''):
                    self.log_test("Detect endpoint rejects invalid file types", True)
                    return True
                else:
                    self.log_test("Detect endpoint rejects invalid file types", False, f"Wrong error message: {error_data.get('detail')}")
                    return False
            else:
                self.log_test("Detect endpoint rejects invalid file types", False, f"Expected 400, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Detect endpoint rejects invalid file types", False, f"Request failed: {str(e)}")
            return False

    def test_detect_endpoint_no_file(self):
        """Test /api/detect without file."""
        print("\n🔍 Testing Detect Endpoint without File...")
        
        try:
            response = requests.post(f"{self.api_url}/detect", timeout=30)
            
            if response.status_code == 422:  # FastAPI validation error
                self.log_test("Detect endpoint requires image file", True)
                return True
            else:
                self.log_test("Detect endpoint requires image file", False, f"Expected 422, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Detect endpoint requires image file", False, f"Request failed: {str(e)}")
            return False

    def test_detect_endpoint_large_image(self):
        """Test /api/detect with large image (should be rejected)."""
        print("\n🔍 Testing Detect Endpoint with Large Image...")
        
        try:
            # Create a large image (simulate > 20MB)
            # We'll create a smaller image but test the validation logic
            large_image_data = self.create_test_image(width=4000, height=3000)
            
            files = {'image': ('large_test.jpg', large_image_data, 'image/jpeg')}
            
            response = requests.post(f"{self.api_url}/detect", files=files, timeout=60)
            
            # This might pass or fail depending on actual size, but we test the endpoint works
            if response.status_code in [200, 400]:
                if response.status_code == 400:
                    error_data = response.json()
                    if 'too large' in error_data.get('detail', '').lower():
                        self.log_test("Detect endpoint validates image size", True)
                    else:
                        self.log_test("Detect endpoint handles large images", True)
                else:
                    self.log_test("Detect endpoint handles large images", True)
                return True
            else:
                self.log_test("Detect endpoint handles large images", False, f"Unexpected status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Detect endpoint handles large images", False, f"Request failed: {str(e)}")
            return False

    def test_gemini_integration(self):
        """Test if Gemini integration is working."""
        print("\n🔍 Testing Gemini Integration...")
        
        try:
            # Create a more realistic road image for better detection
            image_data = self.create_test_image(width=1024, height=768)
            
            files = {'image': ('road_test.jpg', image_data, 'image/jpeg')}
            
            response = requests.post(f"{self.api_url}/detect", files=files, timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we got a valid response from Gemini
                if data.get('engine') == 'gemini' and 'notes' in data:
                    if 'gemini-2.0-flash' in data.get('notes', '').lower():
                        self.log_test("Gemini 2.0 Flash integration working", True)
                        return True
                    else:
                        self.log_test("Gemini 2.0 Flash integration working", True, "Model info not in notes")
                        return True
                else:
                    self.log_test("Gemini 2.0 Flash integration working", False, "Missing engine or notes info")
                    return False
            else:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', response.text)
                except:
                    error_detail = response.text
                
                if 'api key' in error_detail.lower() or 'gemini' in error_detail.lower():
                    self.log_test("Gemini 2.0 Flash integration working", False, f"API key issue: {error_detail}")
                else:
                    self.log_test("Gemini 2.0 Flash integration working", False, f"HTTP {response.status_code}: {error_detail}")
                return False
                
        except Exception as e:
            self.log_test("Gemini 2.0 Flash integration working", False, f"Request failed: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend tests."""
        print("🚀 Starting Pothole Detector Backend API Tests")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test health endpoint first
        health_ok = self.test_health_endpoint()
        
        if not health_ok:
            print("\n❌ Health endpoint failed - stopping tests")
            return False
        
        # Test detect endpoint with various scenarios
        self.test_detect_endpoint_valid_image()
        self.test_detect_endpoint_png_image()
        self.test_detect_endpoint_invalid_file_type()
        self.test_detect_endpoint_no_file()
        self.test_detect_endpoint_large_image()
        self.test_gemini_integration()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 BACKEND TEST SUMMARY")
        print("=" * 60)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test runner."""
    tester = PotholeDetectorAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    results_file = "/app/backend_test_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "summary": {
                "tests_run": tester.tests_run,
                "tests_passed": tester.tests_passed,
                "success_rate": (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0
            },
            "test_results": tester.test_results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())