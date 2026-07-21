import logging
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


class StorageService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_upload(self, file: UploadFile, content: bytes) -> None:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported content type: {file.content_type}. "
                f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )

        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(
                f"File exceeds maximum size of {self.settings.max_upload_size_mb} MB"
            )

        if len(content) == 0:
            raise ValueError("Empty file uploaded")

    def save(self, file: UploadFile, content: bytes) -> tuple[str, str]:
        extension = Path(file.filename or "upload.jpg").suffix or ".jpg"
        file_id = str(uuid.uuid4())
        stored_name = f"{file_id}{extension.lower()}"
        stored_path = self.upload_dir / stored_name

        with open(stored_path, "wb") as f:
            f.write(content)

        logger.info("Saved upload %s to %s", file_id, stored_path)
        return file_id, str(stored_path)

    def delete(self, path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            logger.warning("Failed to delete file at %s", path, exc_info=True)
