image_1 Output:
{
  "processing_id": "ec8efae5-9c4d-4533-8b54-488cfc01adb1",
  "status": "completed",
  "overall_confidence": 0.736,
  "issue_count": 2,
  "checks": [
    {
      "name": "dimension_validation",
      "passed": true,
      "severity": "info",
      "confidence": 0.99,
      "message": "Image dimensions are acceptable",
      "details": {
        "width": 720,
        "height": 1280,
        "min_width": 320,
        "min_height": 240
      }
    },
    {
      "name": "blur_detection",
      "passed": true,
      "severity": "info",
      "confidence": 0.95,
      "message": "Image sharpness is acceptable",
      "details": {
        "threshold": 100,
        "laplacian_variance": 1554.11
      }
    },
    {
      "name": "brightness_analysis",
      "passed": true,
      "severity": "info",
      "confidence": 0.7,
      "message": "Brightness levels are acceptable",
      "details": {
        "low_threshold": 50,
        "high_threshold": 220,
        "mean_brightness": 116.7
      }
    },
    {
      "name": "duplicate_detection",
      "passed": false,
      "severity": "critical",
      "confidence": 0.9,
      "message": "Possible duplicate of a previously uploaded image",
      "details": {
        "threshold": 5,
        "perceptual_hash": "ab9f953fb0804527",
        "closest_match_id": "0e75136a-1eb6-4613-bcc8-e55483ace3dd",
        "compared_against": 2,
        "hamming_distance": 0
      }
    },
    {
      "name": "screenshot_detection",
      "passed": true,
      "severity": "info",
      "confidence": 0.65,
      "message": "Image does not appear to be a screenshot",
      "details": {
        "ratio_match": true,
        "aspect_ratio": 0.562,
        "signal_count": 1,
        "border_uniformity": false,
        "exif_screenshot_hint": false
      }
    },
    {
      "name": "photo_of_photo_detection",
      "passed": true,
      "severity": "info",
      "confidence": 0.55,
      "message": "No strong photo-of-photo indicators detected",
      "details": {
        "bright_pixel_ratio": 0.0194,
        "large_rectangular_contours": 0
      }
    },
    {
      "name": "number_plate_validation",
      "passed": false,
      "severity": "warning",
      "confidence": 0.65,
      "message": "OCR found text but no valid Indian number plate format",
      "details": {
        "raw_ocr_excerpt": "Cee Se\na 7 OS. SEES ) i lie\nPigme em\n\\t | aa jPUNEFCROAD '\noe) MCERICIN7 758900813 eee\na es a | ==\ns , ¢ i wy Gi. ny g v \\\nS #& he aS\n: | 5 LAKH+ GLOBAL ALUMNI.) BELO Ne Ace CHEAT CAE '\nene Ss Ey |)\n=",
        "invalid_candidates": [
          "JPUNEFCROAD",
          "MCERICIN7",
          "758900813",
          "GLOBAL",
          "ALUMNI"
        ]
      }
    },
    {
      "name": "tampering_heuristic",
      "passed": true,
      "severity": "info",
      "confidence": 0.5,
      "message": "No strong tampering indicators detected",
      "details": {
        "max_compression_diff": 19,
        "std_compression_diff": 1.23,
        "mean_compression_diff": 1.01
      }
    }
  ],
  "summary": {
    "total_checks": 8,
    "issues_found": 2,
    "critical_issues": 1,
    "warnings": 1,
    "recommendation": "Reject or request re-upload due to critical quality issues."
  }
}
