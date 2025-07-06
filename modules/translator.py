# modules/translator.py - deep-translator 구현
import logging
from deep_translator import GoogleTranslator, MicrosoftTranslator
from flask import current_app

logger = logging.getLogger(__name__)

# 모듈 레벨 변수로 번역기 저장
_translator = None

def get_translator():
    """번역기를 가져옵니다."""
    global _translator
    
    if _translator is not None:
        return _translator
    
    try:
        logger.info("번역기 지연 초기화 중...")
        _translator = GoogleTranslator(source='ko', target='en')
        
        # 테스트 번역으로 작동 확인
        test = _translator.translate("테스트")
        logger.info(f"번역기 테스트: '테스트' -> '{test}'")
        
        logger.info("번역기 지연 초기화 완료")
        return _translator
    except Exception as e:
        logger.error(f"번역기 지연 초기화 중 오류 발생: {e}")
        return None

def init_translator(app):
    """번역기 객체를 초기화합니다."""
    global _translator
    
    try:
        logger.info("번역기 초기화 중...")
        _translator = GoogleTranslator(source='ko', target='en')
        
        # 테스트 번역
        test = _translator.translate("테스트")
        logger.info(f"번역기 테스트: '테스트' -> '{test}'")
        
        logger.info("번역기 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"번역기 초기화 중 오류 발생: {e}")
        _translator = None
        return False

def translate_text(text, source='ko', target='en'):
    """텍스트를 번역합니다."""
    if not text or len(text.strip()) == 0:
        return ""
    
    try:
        translator = get_translator()
        if translator is None:
            logger.warning("기본 번역기 사용 불가, 임시 번역기 생성 시도...")
            # 임시 번역기 생성
            temp_translator = GoogleTranslator(source=source, target=target)
            return temp_translator.translate(text)
        
        # deep-translator는 자동으로 텍스트 길이 제한을 처리합니다
        return translator.translate(text)
    except Exception as e:
        logger.error(f"번역 중 오류 발생: {e}")
        
        # Google 번역기가 실패하면 대체 방법 시도
        try:
            logger.info("대체 번역 방법 시도 중...")
            
            # 대체 방법 1: 다른 인스턴스로 재시도
            alt_translator = GoogleTranslator(source=source, target=target)
            return alt_translator.translate(text)
            
            # 대체 방법 2: Microsoft 번역기 (API 키 필요)
            # if 'MICROSOFT_TRANSLATOR_KEY' in current_app.config:
            #     ms_key = current_app.config['MICROSOFT_TRANSLATOR_KEY']
            #     ms_translator = MicrosoftTranslator(api_key=ms_key, source=source, target=target)
            #     return ms_translator.translate(text)
            
        except Exception as alt_error:
            logger.error(f"대체 번역 방법도 실패: {alt_error}")
            return f"[번역 오류: {str(e)}]"

def process_menu_text(ocr_result):
    """OCR 결과를 번역 처리합니다."""
    try:
        if not ocr_result["success"]:
            return ocr_result
            
        full_text = ocr_result["full_text"]
        
        # 전체 텍스트 번역
        logger.info("인식된 텍스트 번역 중...")
        
        try:
            translated_text = translate_text(full_text)
        except Exception as e:
            logger.warning(f"기본 번역 실패, 대체 번역 시도: {e}")
            # 간단한 대체 번역 결과 생성 (예시)
            translated_text = "Translation service is temporarily unavailable. Original text:\n" + full_text
        
        # 번역이 실패한 경우 처리
        if translated_text.startswith('[번역 오류') or translated_text.startswith('[번역 불가'):
            return {
                "success": True,  # 오류지만 원본 텍스트는 보여주기 위해 success=True
                "error": translated_text,
                "original_text": full_text,
                "translated_text": "Translation service unavailable"
            }
        
        return {
            "success": True,
            "original_text": full_text,
            "translated_text": translated_text
        }
    except Exception as e:
        logger.error(f"메뉴 텍스트 처리 중 오류 발생: {e}")
        return {"success": False, "error": str(e)}