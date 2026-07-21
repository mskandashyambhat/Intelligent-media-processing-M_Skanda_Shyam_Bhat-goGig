"""Seed database with a completed sample record for demo purposes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_samples import main as generate_samples

if __name__ == "__main__":
    generate_samples()
    print("Run 'docker compose up' then upload sample_images/valid_vehicle.jpg via the API.")
