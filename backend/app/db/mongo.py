"""Async MongoDB client using Motor.

Provides a lazy-initialised client and collection accessor for storing
raw OCR text from the ingestion pipeline.

Collections
-----------
atlas_raw.raw_ocr   — one document per ingested PDF, containing the full
                      raw_text and parsed field summary for the ML pipeline.
"""

from __future__ import annotations

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import MONGO_URL

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Return the module-level Motor client, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
        logger.info("MongoDB client initialised at %s.", MONGO_URL)
    return _client


def get_raw_ocr_collection() -> AsyncIOMotorCollection:
    """Return the ``atlas_raw.raw_ocr`` collection."""
    return get_mongo_client()["atlas_raw"]["raw_ocr"]
