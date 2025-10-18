#!/usr/bin/env python3
"""Batch evaluator for pothole detection on Kaggle images.

Usage:
    python scripts/eval_kaggle.py --dir /path/to/images --out results.jsonl
"""

import argparse
import json
import time
from pathlib import Path
import requests
import sys

def main():
    parser = argparse.ArgumentParser(description='Batch evaluate pothole detection')
    parser.add_argument('--dir', type=str, required=True, help='Directory containing images')
    parser.add_argument('--out', type=str, default='gemini_eval.jsonl', help='Output JSONL file')
    parser.add_argument('--url', type=str, default='http://localhost:8001/api/detect', help='API endpoint URL')
    args = parser.parse_args()
    
    image_dir = Path(args.dir)
    if not image_dir.exists():
        print(f"Error: Directory {image_dir} does not exist")
        sys.exit(1)
    
    # Find all image files
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
        image_files.extend(image_dir.glob(ext))
    
    if not image_files:
        print(f"Error: No image files found in {image_dir}")
        sys.exit(1)
    
    print(f"Found {len(image_files)} images to process")
    print(f"API endpoint: {args.url}")
    print(f"Output file: {args.out}")
    print("\nStarting evaluation...\n")
    
    results = []
    success_count = 0
    error_count = 0
    
    with open(args.out, 'w') as out_file:
        for i, image_path in enumerate(image_files, 1):
            print(f"[{i}/{len(image_files)}] Processing {image_path.name}...", end=' ')
            
            start_time = time.time()
            
            try:
                with open(image_path, 'rb') as f:
                    files = {'image': (image_path.name, f, 'image/jpeg')}
                    response = requests.post(args.url, files=files, timeout=60)
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    result_entry = {
                        'image': image_path.name,
                        'image_path': str(image_path),
                        'status': 'success',
                        'elapsed_seconds': round(elapsed, 2),
                        'response': result
                    }
                    success_count += 1
                    print(f"✓ ({elapsed:.2f}s) - {result['count']} potholes")
                else:
                    result_entry = {
                        'image': image_path.name,
                        'image_path': str(image_path),
                        'status': 'error',
                        'elapsed_seconds': round(elapsed, 2),
                        'error': f"HTTP {response.status_code}: {response.text}"
                    }
                    error_count += 1
                    print(f"✗ HTTP {response.status_code}")
                
            except Exception as e:
                elapsed = time.time() - start_time
                result_entry = {
                    'image': image_path.name,
                    'image_path': str(image_path),
                    'status': 'error',
                    'elapsed_seconds': round(elapsed, 2),
                    'error': str(e)
                }
                error_count += 1
                print(f"✗ {str(e)}")
            
            # Write to JSONL
            out_file.write(json.dumps(result_entry) + '\n')
            out_file.flush()
            results.append(result_entry)
    
    # Print summary
    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    print(f"Total images: {len(image_files)}")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Success rate: {success_count/len(image_files)*100:.1f}%")
    
    if success_count > 0:
        avg_time = sum(r['elapsed_seconds'] for r in results if r['status'] == 'success') / success_count
        total_potholes = sum(r['response']['count'] for r in results if r['status'] == 'success')
        print(f"Average time per image: {avg_time:.2f}s")
        print(f"Total potholes detected: {total_potholes}")
    
    print(f"\nResults saved to: {args.out}")

if __name__ == '__main__':
    main()