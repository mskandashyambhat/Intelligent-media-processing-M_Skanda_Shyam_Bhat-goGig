"""Run analysis pipeline on sample images and print JSON results."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.pipeline import run_analysis_pipeline
from app.config import get_settings


def analyze(path: Path) -> dict:
    settings = get_settings()
    checks, meta = run_analysis_pipeline(str(path), settings, existing_hashes=[])
    return {
        "filename": path.name,
        "path": str(path.relative_to(Path(__file__).resolve().parent.parent)),
        "overall_confidence": meta["overall_confidence"],
        "issue_count": meta["issue_count"],
        "summary": meta["summary"],
        "checks": [c.to_dict() for c in checks],
    }


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "sample_images" / "real"
    images = sorted(root.glob("*"))
    results = [analyze(p) for p in images if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
