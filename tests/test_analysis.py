import numpy as np
import pytest
from PIL import Image

from app.analysis.pipeline import (
    _normalize_plate_text,
    _validate_indian_plate,
    check_blur,
    check_brightness,
    check_dimensions,
)
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def sharp_image(tmp_path) -> str:
    path = tmp_path / "sharp.jpg"
    arr = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return str(path)


@pytest.fixture
def blurry_image(tmp_path) -> str:
    import cv2

    path = tmp_path / "blurry.jpg"
    arr = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(arr, (31, 31), 0)
    cv2.imwrite(str(path), blurred)
    return str(path)


@pytest.fixture
def dark_image(tmp_path) -> str:
    path = tmp_path / "dark.jpg"
    arr = np.full((480, 640, 3), 20, dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return str(path)


def test_dimension_check_passes(sharp_image, settings):
    result = check_dimensions(sharp_image, settings)
    assert result.passed is True


def test_dimension_check_fails_tiny_image(tmp_path, settings):
    path = tmp_path / "tiny.jpg"
    Image.new("RGB", (100, 100), color=(128, 128, 128)).save(path)
    result = check_dimensions(str(path), settings)
    assert result.passed is False
    assert result.severity == "critical"


def test_blur_check_detects_blur(blurry_image, settings):
    result = check_blur(blurry_image, settings)
    assert result.passed is False
    assert result.name == "blur_detection"


def test_brightness_check_detects_low_light(dark_image, settings):
    result = check_brightness(dark_image, settings)
    assert result.passed is False
    assert "low light" in result.message.lower()


def test_indian_plate_validation():
    assert _validate_indian_plate("KA01AB1234") is True
    assert _validate_indian_plate("DL3CAB1234") is True
    assert _validate_indian_plate("INVALID") is False


def test_normalize_plate_text():
    assert _normalize_plate_text("ka 01 ab 1234") == "KA01AB1234"
