import logging
import re
from dataclasses import dataclass, field
from typing import Any

import cv2
import imagehash
import numpy as np
import pytesseract
from PIL import Image, ExifTags

from app.config import Settings

logger = logging.getLogger(__name__)

# Indian vehicle registration patterns (simplified but practical)
# Examples: KA01AB1234, DL3CAB1234, MH12DE1433
INDIAN_PLATE_PATTERNS = [
    re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$"),
    re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$"),
    re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$"),
]

# Common mobile screenshot aspect ratios (width/height)
SCREENSHOT_RATIOS = {
    9 / 19.5,  # iPhone
    9 / 16,
    9 / 18,
    9 / 20,
    3 / 4,
    10 / 16,
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str
    confidence: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "confidence": self.confidence,
            "message": self.message,
            "details": self.details,
        }


def _load_cv_image(path: str) -> np.ndarray:
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"Unable to read image at {path}")
    return image


def check_blur(path: str, settings: Settings) -> CheckResult:
    """Laplacian variance: lower values indicate more blur."""
    gray = cv2.cvtColor(_load_cv_image(path), cv2.COLOR_BGR2GRAY)
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blurry = variance < settings.blur_threshold

    return CheckResult(
        name="blur_detection",
        passed=not is_blurry,
        severity="warning" if is_blurry else "info",
        confidence=min(0.95, abs(variance - settings.blur_threshold) / settings.blur_threshold),
        message="Image appears blurry" if is_blurry else "Image sharpness is acceptable",
        details={"laplacian_variance": round(variance, 2), "threshold": settings.blur_threshold},
    )


def check_brightness(path: str, settings: Settings) -> CheckResult:
    """Mean pixel brightness in grayscale space."""
    gray = cv2.cvtColor(_load_cv_image(path), cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))

    too_dark = mean_brightness < settings.low_brightness_threshold
    too_bright = mean_brightness > settings.high_brightness_threshold
    issue = too_dark or too_bright

    if too_dark:
        message = "Image is underexposed (low light)"
        severity = "warning"
    elif too_bright:
        message = "Image is overexposed"
        severity = "warning"
    else:
        message = "Brightness levels are acceptable"
        severity = "info"

    return CheckResult(
        name="brightness_analysis",
        passed=not issue,
        severity=severity,
        confidence=0.85 if issue else 0.7,
        message=message,
        details={
            "mean_brightness": round(mean_brightness, 2),
            "low_threshold": settings.low_brightness_threshold,
            "high_threshold": settings.high_brightness_threshold,
        },
    )


def check_dimensions(path: str, settings: Settings) -> CheckResult:
    image = _load_cv_image(path)
    height, width = image.shape[:2]
    too_small = width < settings.min_image_width or height < settings.min_image_height

    return CheckResult(
        name="dimension_validation",
        passed=not too_small,
        severity="critical" if too_small else "info",
        confidence=0.99,
        message="Image resolution is too low for reliable analysis"
        if too_small
        else "Image dimensions are acceptable",
        details={
            "width": width,
            "height": height,
            "min_width": settings.min_image_width,
            "min_height": settings.min_image_height,
        },
    )


def check_duplicate(path: str, existing_hashes: list[tuple[str, str]], settings: Settings) -> CheckResult:
    """Perceptual hash comparison against previously uploaded images."""
    current_hash = str(imagehash.phash(Image.open(path)))

    closest_match: tuple[str, int] | None = None
    for record_id, stored_hash in existing_hashes:
        distance = imagehash.hex_to_hash(current_hash) - imagehash.hex_to_hash(stored_hash)
        if closest_match is None or distance < closest_match[1]:
            closest_match = (record_id, distance)

    is_duplicate = (
        closest_match is not None
        and closest_match[1] <= settings.duplicate_hamming_distance
    )

    return CheckResult(
        name="duplicate_detection",
        passed=not is_duplicate,
        severity="critical" if is_duplicate else "info",
        confidence=0.9 if is_duplicate else 0.6,
        message="Possible duplicate of a previously uploaded image"
        if is_duplicate
        else "No duplicate detected among prior uploads",
        details={
            "perceptual_hash": current_hash,
            "closest_match_id": closest_match[0] if closest_match else None,
            "hamming_distance": closest_match[1] if closest_match else None,
            "threshold": settings.duplicate_hamming_distance,
            "compared_against": len(existing_hashes),
        },
    )


def _normalize_plate_text(text: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]", "", text.upper())
    return cleaned


def _validate_indian_plate(plate: str) -> bool:
    if not plate or len(plate) < 8 or len(plate) > 10:
        return False
    return any(pattern.match(plate) for pattern in INDIAN_PLATE_PATTERNS)


def check_ocr_plate(path: str) -> CheckResult:
    """Extract text via OCR and validate against Indian number plate formats."""
    pil_image = Image.open(path)
    raw_text = pytesseract.image_to_string(pil_image, config="--psm 6")
    normalized_tokens = [_normalize_plate_text(token) for token in raw_text.split()]
    candidates = [t for t in normalized_tokens if len(t) >= 6]

    valid_plates = [plate for plate in candidates if _validate_indian_plate(plate)]
    invalid_candidates = [plate for plate in candidates if not _validate_indian_plate(plate)]

    if valid_plates:
        return CheckResult(
            name="number_plate_validation",
            passed=True,
            severity="info",
            confidence=0.75,
            message=f"Valid Indian number plate detected: {valid_plates[0]}",
            details={
                "detected_plates": valid_plates,
                "raw_ocr_excerpt": raw_text[:200],
            },
        )

    has_invalid_format = len(invalid_candidates) > 0
    return CheckResult(
        name="number_plate_validation",
        passed=not has_invalid_format,
        severity="warning" if has_invalid_format else "info",
        confidence=0.65 if has_invalid_format else 0.5,
        message="OCR found text but no valid Indian number plate format"
        if has_invalid_format
        else "No readable number plate text detected",
        details={
            "invalid_candidates": invalid_candidates[:5],
            "raw_ocr_excerpt": raw_text[:200],
        },
    )


def check_screenshot(path: str) -> CheckResult:
    """Heuristics: common mobile aspect ratios and uniform borders."""
    image = _load_cv_image(path)
    height, width = image.shape[:2]
    ratio = width / height if height else 0
    ratio_alt = height / width if width else 0

    ratio_match = any(abs(r - ratio) < 0.02 or abs(r - ratio_alt) < 0.02 for r in SCREENSHOT_RATIOS)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    border_samples = np.concatenate(
        [
            gray[0, :],
            gray[-1, :],
            gray[:, 0],
            gray[:, -1],
        ]
    )
    border_uniformity = float(np.std(border_samples)) < 8.0

    exif_screenshot = False
    try:
        pil = Image.open(path)
        exif = pil.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag == "Software" and isinstance(value, str):
                    software_lower = value.lower()
                    if any(k in software_lower for k in ("android", "ios", "screenshot")):
                        exif_screenshot = True
    except Exception:
        logger.debug("EXIF read failed for screenshot check", exc_info=True)

    signals = sum([ratio_match, border_uniformity, exif_screenshot])
    is_screenshot = signals >= 2

    return CheckResult(
        name="screenshot_detection",
        passed=not is_screenshot,
        severity="warning" if is_screenshot else "info",
        confidence=min(0.9, 0.5 + signals * 0.15),
        message="Image appears to be a screenshot" if is_screenshot else "Image does not appear to be a screenshot",
        details={
            "aspect_ratio": round(ratio, 3),
            "ratio_match": ratio_match,
            "border_uniformity": border_uniformity,
            "exif_screenshot_hint": exif_screenshot,
            "signal_count": signals,
        },
    )


def check_photo_of_photo(path: str) -> CheckResult:
    """Detect rectangular frame-like edges and elevated highlight regions."""
    image = _load_cv_image(path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    image_area = h * w

    large_rectangles = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.15:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4:
            large_rectangles += 1

    # Glare / reflection heuristic
    bright_ratio = float(np.mean(gray > 240))

    is_photo_of_photo = large_rectangles >= 1 and bright_ratio > 0.02

    return CheckResult(
        name="photo_of_photo_detection",
        passed=not is_photo_of_photo,
        severity="warning" if is_photo_of_photo else "info",
        confidence=0.7 if is_photo_of_photo else 0.55,
        message="Image may be a photo of another photo or screen"
        if is_photo_of_photo
        else "No strong photo-of-photo indicators detected",
        details={
            "large_rectangular_contours": large_rectangles,
            "bright_pixel_ratio": round(bright_ratio, 4),
        },
    )


def check_tampering_heuristic(path: str) -> CheckResult:
    """Error Level Analysis (ELA) lite: inconsistent compression regions."""
    pil = Image.open(path).convert("RGB")
    resaved = pil.copy()
    resaved_path = path + ".ela.tmp.jpg"
    resaved.save(resaved_path, "JPEG", quality=90)

    original = np.array(pil, dtype=np.float32)
    compressed = np.array(Image.open(resaved_path).convert("RGB"), dtype=np.float32)

    import os

    try:
        os.remove(resaved_path)
    except OSError:
        pass

    diff = np.abs(original - compressed)
    mean_diff = float(np.mean(diff))
    max_diff = float(np.max(diff))
    std_diff = float(np.std(diff))

    # High variance in compression residuals can suggest editing
    suspicious = std_diff > 12.0 and max_diff > 80.0

    return CheckResult(
        name="tampering_heuristic",
        passed=not suspicious,
        severity="warning" if suspicious else "info",
        confidence=0.6 if suspicious else 0.5,
        message="Possible editing or tampering detected via compression analysis"
        if suspicious
        else "No strong tampering indicators detected",
        details={
            "mean_compression_diff": round(mean_diff, 2),
            "max_compression_diff": round(max_diff, 2),
            "std_compression_diff": round(std_diff, 2),
        },
    )


def run_analysis_pipeline(
    path: str,
    settings: Settings,
    existing_hashes: list[tuple[str, str]] | None = None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    existing_hashes = existing_hashes or []

    checks = [
        check_dimensions(path, settings),
        check_blur(path, settings),
        check_brightness(path, settings),
        check_duplicate(path, existing_hashes, settings),
        check_screenshot(path),
        check_photo_of_photo(path),
        check_ocr_plate(path),
        check_tampering_heuristic(path),
    ]

    issues = [c for c in checks if not c.passed and c.severity in ("warning", "critical")]
    critical = [c for c in issues if c.severity == "critical"]
    warnings = [c for c in issues if c.severity == "warning"]

    if critical:
        recommendation = "Reject or request re-upload due to critical quality issues."
    elif warnings:
        recommendation = "Review recommended; image has quality or authenticity concerns."
    else:
        recommendation = "Image passes automated checks; proceed with manual review if needed."

    confidences = [c.confidence for c in checks]
    overall_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    summary = {
        "total_checks": len(checks),
        "issues_found": len(issues),
        "critical_issues": len(critical),
        "warnings": len(warnings),
        "recommendation": recommendation,
    }

    return checks, {
        "overall_confidence": overall_confidence,
        "issue_count": len(issues),
        "summary": summary,
    }
