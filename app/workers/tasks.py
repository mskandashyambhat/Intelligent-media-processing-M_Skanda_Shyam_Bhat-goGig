import logging
from datetime import datetime, timezone
from uuid import UUID

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.analysis.pipeline import run_analysis_pipeline
from app.config import get_settings
from app.db.models import AnalysisResult, ImageRecord, ProcessingStatus, SessionLocal
from app.services.queue import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(name="app.workers.tasks.process_image", bind=True)
def process_image(self, image_id: str) -> dict:
    db: Session = SessionLocal()
    try:
        record = db.query(ImageRecord).filter(ImageRecord.id == UUID(image_id)).one_or_none()
        if record is None:
            raise ValueError(f"Image record not found: {image_id}")

        record.status = ProcessingStatus.PROCESSING
        record.started_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("Processing image %s", image_id)

        # Compute and persist perceptual hash for future duplicate checks
        phash = str(imagehash.phash(Image.open(record.stored_path)))
        record.perceptual_hash = phash
        db.commit()

        existing = (
            db.query(ImageRecord.id, ImageRecord.perceptual_hash)
            .filter(
                ImageRecord.id != record.id,
                ImageRecord.perceptual_hash.isnot(None),
                ImageRecord.status == ProcessingStatus.COMPLETED,
            )
            .all()
        )
        existing_hashes = [(str(row.id), row.perceptual_hash) for row in existing]

        checks, meta = run_analysis_pipeline(
            record.stored_path,
            settings,
            existing_hashes=existing_hashes,
        )

        analysis = AnalysisResult(
            image_id=record.id,
            overall_confidence=meta["overall_confidence"],
            issue_count=meta["issue_count"],
            checks=[c.to_dict() for c in checks],
            summary=meta["summary"],
        )
        db.add(analysis)

        record.status = ProcessingStatus.COMPLETED
        record.completed_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        record.failure_reason = None
        db.commit()

        logger.info("Completed processing image %s", image_id)
        return {"image_id": image_id, "status": "completed", "issue_count": meta["issue_count"]}

    except Exception as exc:
        logger.exception("Failed processing image %s", image_id)
        db.rollback()

        record = db.query(ImageRecord).filter(ImageRecord.id == UUID(image_id)).one_or_none()
        if record:
            record.status = ProcessingStatus.FAILED
            record.failure_reason = str(exc)
            record.updated_at = datetime.now(timezone.utc)
            db.commit()

        raise exc
    finally:
        db.close()
