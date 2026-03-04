from __future__ import annotations

from typing import Any, Optional


class ApiError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int, details: Optional[Any] = None):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
