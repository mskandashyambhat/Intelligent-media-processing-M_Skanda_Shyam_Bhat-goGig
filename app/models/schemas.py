from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ProcessingStatusLiteral = Literal["pending", "processing", "completed", "failed"]
SeverityLiteral = Literal["info", "warning", "critical"]


class CheckResult(BaseModel):
    name: str
    passed: bool
    severity: SeverityLiteral
    confidence: float = Field(ge=0.0, le=1.0)
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    processing_id: UUID
    status: ProcessingStatusLiteral
    message: str


class StatusResponse(BaseModel):
    processing_id: UUID
    status: ProcessingStatusLiteral
    original_filename: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None


class AnalysisSummary(BaseModel):
    total_checks: int
    issues_found: int
    critical_issues: int
    warnings: int
    recommendation: str


class AnalysisResponse(BaseModel):
    processing_id: UUID
    status: ProcessingStatusLiteral
    overall_confidence: float
    issue_count: int
    checks: list[CheckResult]
    summary: AnalysisSummary


class ErrorResponse(BaseModel):
    detail: str
