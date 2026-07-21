"""Generate sample test images for manual API testing."""

from pathlib import Path

import cv2
import numpy as np

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_images"
SAMPLE_DIR.mkdir(exist_ok=True)


def save_sharp_bright(path: Path) -> None:
    img = np.full((720, 1280, 3), 180, dtype=np.uint8)
    cv2.putText(img, "KA01AB1234", (200, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
    cv2.imwrite(str(path), img)


def save_blurry(path: Path) -> None:
    img = np.random.randint(80, 140, (480, 640, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(img, (31, 31), 0)
    cv2.imwrite(str(path), blurred)


def save_dark(path: Path) -> None:
    img = np.full((600, 800, 3), 25, dtype=np.uint8)
    cv2.putText(img, "DL3CAB1234", (120, 320), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (200, 200, 200), 3)
    cv2.imwrite(str(path), img)


def main() -> None:
    save_sharp_bright(SAMPLE_DIR / "valid_vehicle.jpg")
    save_blurry(SAMPLE_DIR / "blurry_vehicle.jpg")
    save_dark(SAMPLE_DIR / "low_light_vehicle.jpg")
    print(f"Sample images written to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
