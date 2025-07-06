# modules/ocr.py 개선 버전
import logging
import easyocr
from flask import current_app
import os
import threading

logger = logging.getLogger(__name__)

class OCRReader:
    """OCR 리더 싱글톤 클래스"""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, app=None):
        """스레드 안전한 싱글톤 인스턴스 반환 메서드"""
        # 이중 체크 락킹(Double-checked locking) 패턴 적용
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(app)
        return cls._instance
    
    def __init__(self, app=None):
        """초기화 - 직접 호출하지 말고 get_instance() 사용"""
        self.reader = None
        self.app = app
        self.initialized = False
    
    def initialize(self, app=None):
        """모델 지연 초기화 메서드"""
        if self.initialized:
            return True
            
        with self._lock:
            if self.initialized:  # 이중 체크
                return True
                
            if app:
                self.app = app
                
            try:
                logger.info("EasyOCR 모델 지연 로딩 중...")
                
                # 애플리케이션 컨텍스트에서 설정 가져오기
                if self.app:
                    model_path = self.app.config.get('OCR_MODEL_PATH', 
                                 os.path.join(os.path.expanduser('~'), '.EasyOCR'))
                else:
                    # 앱이 없는 경우 기본값 사용
                    model_path = os.path.join(os.path.expanduser('~'), '.EasyOCR')
                
                if not os.path.exists(model_path):
                    os.makedirs(model_path, exist_ok=True)
                
                # 한국어와 영어를 인식하도록 설정
                self.reader = easyocr.Reader(['ko', 'en'], gpu=False, model_storage_directory=model_path)
                self.initialized = True
                logger.info("EasyOCR 모델 로딩 완료")
                return True
            except Exception as e:
                logger.error(f"EasyOCR 모델 로딩 중 오류 발생: {e}")
                return False
    
    def read_text(self, image_path, min_confidence=0.3):
        """이미지에서 텍스트를 인식하는 메서드"""
        if not self.initialized:
            success = self.initialize()
            if not success:
                return {"success": False, "error": "OCR 모델을 초기화할 수 없습니다."}
        
        try:
            logger.info(f"이미지 텍스트 인식 중: {image_path}")
            results = self.reader.readtext(image_path)
            
            # 인식된 텍스트 추출 및 정리
            extracted_texts = []
            for bbox, text, prob in results:
                # 신뢰도가 min_confidence 이상인 텍스트만 선택
                if prob > min_confidence and len(text.strip()) > 0:
                    extracted_texts.append({
                        'text': text,
                        'bbox': bbox,
                        'confidence': prob
                    })
            
            if not extracted_texts:
                return {"success": False, "error": "인식된 텍스트가 없습니다."}
            
            # 추출된 텍스트를 하나로 합치기
            full_text = "\n".join([item['text'] for item in extracted_texts])
            
            return {
                "success": True,
                "extracted_texts": extracted_texts,
                "full_text": full_text
            }
        
        except Exception as e:
            logger.error(f"텍스트 인식 중 오류 발생: {e}")
            return {"success": False, "error": str(e)}

# 기존 함수를 대체하는 래퍼 함수들 (호환성 유지)
def get_ocr_reader():
    """OCR 리더 인스턴스를 가져오는 함수 (기존 코드와의 호환성 유지)"""
    instance = OCRReader.get_instance()
    if not instance.initialized:
        instance.initialize()
    return instance.reader

def init_ocr(app):
    """애플리케이션 초기화 시 OCR 리더를 초기화하는 함수"""
    ocr = OCRReader.get_instance(app)
    return ocr.initialize(app)

def process_image_text(image_path, min_confidence=0.3):
    """이미지에서 텍스트를 인식하는 함수 (기존 코드와의 호환성 유지)"""
    ocr = OCRReader.get_instance()
    return ocr.read_text(image_path, min_confidence)

# 기존 함수를 대체하는 래퍼 함수들 (호환성 유지)
def get_ocr_reader():
    """OCR 리더 인스턴스를 가져오는 함수 (기존 코드와의 호환성 유지)"""
    instance = OCRReader.get_instance()
    if not instance.initialized:
        instance.initialize()
    return instance.reader

def init_ocr(app):
    """애플리케이션 초기화 시 OCR 리더를 초기화하는 함수"""
    ocr = OCRReader.get_instance(app)
    return ocr.initialize(app)

def process_image_text(image_path, min_confidence=0.3):
    """이미지에서 텍스트를 인식하는 함수 (기존 코드와의 호환성 유지)"""
    ocr = OCRReader.get_instance()
    return ocr.read_text(image_path, min_confidence)