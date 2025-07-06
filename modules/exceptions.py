# modules/exceptions.py
class KFoodLensException(Exception):
    """K-FOOD LENS 애플리케이션의 기본 예외 클래스"""
    
    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

# 데이터베이스 관련 예외
class DatabaseError(KFoodLensException):
    """데이터베이스 연산 중 발생하는 예외"""
    pass

class ConnectionError(DatabaseError):
    """데이터베이스 연결 실패 예외"""
    pass

class QueryError(DatabaseError):
    """쿼리 실행 실패 예외"""
    pass

class DataValidationError(DatabaseError):
    """데이터 유효성 검증 실패 예외"""
    pass

# 모델 관련 예외
class ModelError(KFoodLensException):
    """AI 모델 관련 예외"""
    pass

class ModelLoadError(ModelError):
    """모델 로드 실패 예외"""
    pass

class InferenceError(ModelError):
    """모델 추론 실패 예외"""
    pass

# 이미지 처리 관련 예외
class ImageProcessingError(KFoodLensException):
    """이미지 처리 관련 예외"""
    pass

class ImageReadError(ImageProcessingError):
    """이미지 읽기 실패 예외"""
    pass

class InvalidImageError(ImageProcessingError):
    """잘못된 이미지 형식 예외"""
    pass

# OCR 관련 예외
class OCRError(KFoodLensException):
    """OCR 처리 관련 예외"""
    pass

class TextRecognitionError(OCRError):
    """텍스트 인식 실패 예외"""
    pass

# 번역 관련 예외
class TranslationError(KFoodLensException):
    """번역 관련 예외"""
    pass

class APIError(KFoodLensException):
    """외부 API 호출 관련 예외"""
    
    def __init__(self, message, service=None, status_code=None, **kwargs):
        details = {
            'service': service,
            'status_code': status_code,
            **kwargs
        }
        super().__init__(message, code='api_error', details=details)

class RateLimitError(APIError):
    """API 호출 제한 초과 예외"""
    pass

class AuthenticationError(APIError):
    """API 인증 실패 예외"""
    pass