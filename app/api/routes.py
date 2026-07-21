import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ImageRecord, ProcessingStatus, get_db, init_db
from app.models.schemas import (
    AnalysisResponse,
    AnalysisSummary,
    CheckResult,
    ErrorResponse,
    StatusResponse,
    UploadResponse,
)
from app.services.storage import StorageService
from app.workers.tasks import process_image

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    storage = StorageService(settings)
    content = await file.read()

    try:
        storage.validate_upload(file, content)
        _, stored_path = storage.save(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record = ImageRecord(
        original_filename=file.filename or "unknown",
        stored_path=stored_path,
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(content),
        status=ProcessingStatus.PENDING,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    process_image(str(record.id))

    logger.info("Enqueued processing for %s", record.id)
    db.refresh(record)

    return UploadResponse(
    processing_id=record.id,
    status=record.status.value,
    message="Image processed successfully.",
    )


@router.get(
    "/status/{processing_id}",
    response_model=StatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_status(processing_id: UUID, db: Session = Depends(get_db)) -> StatusResponse:
    record = db.query(ImageRecord).filter(ImageRecord.id == processing_id).one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing ID not found: {processing_id}",
        )

    return StatusResponse(
        processing_id=record.id,
        status=record.status.value,
        original_filename=record.original_filename,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        failure_reason=record.failure_reason,
    )


@router.get(
    "/results/{processing_id}",
    response_model=AnalysisResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def get_results(processing_id: UUID, db: Session = Depends(get_db)) -> AnalysisResponse:
    record = db.query(ImageRecord).filter(ImageRecord.id == processing_id).one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing ID not found: {processing_id}",
        )

    if record.status == ProcessingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Processing has not started yet. Check /status for updates.",
        )

    if record.status == ProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Processing is still in progress. Check /status for updates.",
        )

    if record.status == ProcessingStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Processing failed: {record.failure_reason or 'Unknown error'}",
        )

    if record.analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis results not found for completed record.",
        )

    checks = [CheckResult(**c) for c in record.analysis.checks]
    summary = AnalysisSummary(**record.analysis.summary)

    return AnalysisResponse(
        processing_id=record.id,
        status=record.status.value,
        overall_confidence=record.analysis.overall_confidence,
        issue_count=record.analysis.issue_count,
        checks=checks,
        summary=summary,
    )


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {"status": "healthy", "service": "media-processing-pipeline"}
