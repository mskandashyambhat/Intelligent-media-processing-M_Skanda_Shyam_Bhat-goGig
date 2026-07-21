#!/usr/bin/env python3
"""Simple end-to-end smoke test against a running API."""

import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000/api/v1"
SAMPLE = Path(__file__).resolve().parent.parent / "sample_images" / "valid_vehicle.jpg"


def main() -> int:
    if not SAMPLE.exists():
        print("Sample image missing. Run: python scripts/seed_samples.py")
        return 1

    with httpx.Client(timeout=30) as client:
        health = client.get(f"{BASE_URL}/health")
        health.raise_for_status()
        print("Health:", health.json())

        with open(SAMPLE, "rb") as f:
            resp = client.post(
                f"{BASE_URL}/upload",
                files={"file": ("valid_vehicle.jpg", f, "image/jpeg")},
            )
        resp.raise_for_status()
        data = resp.json()
        processing_id = data["processing_id"]
        print("Upload:", data)

        for _ in range(30):
            status_resp = client.get(f"{BASE_URL}/status/{processing_id}")
            status_resp.raise_for_status()
            status = status_resp.json()["status"]
            print("Status:", status)
            if status in ("completed", "failed"):
                break
            time.sleep(1)

        if status == "completed":
            results = client.get(f"{BASE_URL}/results/{processing_id}")
            results.raise_for_status()
            print("Results:", results.json())
            return 0

        print("Processing did not complete successfully.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
