from typing import Dict, Optional


class NinjaRMMError(Exception):
    """Base exception for NinjaRMM API errors"""
    pass

class NinjaRMMAuthError(NinjaRMMError):
    """Authentication error"""
    pass

class NinjaRMMAPIError(NinjaRMMError):
    """API-specific error with status code and details"""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

class NinjaRMMValidationError(NinjaRMMError):
    """Validation error for request parameters"""
    def __init__(self, message: str, field: Optional[str] = None):
        if field:
            super().__init__(f"{message} (field: {field})")
        else:
            super().__init__(message)
        self.message = message
        self.field = field