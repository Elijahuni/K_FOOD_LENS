# modules/translator.py 개선 버전
import logging
from googletrans import Translator
from flask import g, current_app

logger = logging.getLogger(__name__)

# 모듈 레벨 변수로 번역기 저장 (g 객체 대신)
_translator = None

def get_translator():
    """번역기를 가져옵니다."""
    global _translator
    
    # 이미 초기화된 번역기가 있으면 반환
    if _translator is not None:
        return _translator
    
    # 없으면 지연 초기화 수행
    try:
        logger.info("Google 번역기 지연 초기화 중...")
        _translator = Translator()
        logger.info("Google 번역기 지연 초기화 완료")
        return _translator
    except Exception as e:
        logger.error(f"번역기 지연 초기화 중 오류 발생: {e}")
        return None

def init_translator(app):
    """Google 번역기 객체를 초기화합니다."""
    global _translator
    
    try:
        logger.info("Google 번역기 초기화 중...")
        _translator = Translator()
        logger.info("Google 번역기 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"번역기 초기화 중 오류 발생: {e}")
        _translator = None
        return False

def translate_text(text, source='ko', target='en'):
    """텍스트를 번역합니다. (Google Translate 사용)"""
    try:
        if not text or len(text.strip()) == 0:
            return ""
            
        translator = get_translator()
        if translator is None:
            logger.error("번역기가 초기화되지 않았습니다.")
            # 대체 번역기 시도
            try:
                logger.info("대체 번역기 초기화 시도...")
                backup_translator = Translator()
                translation = backup_translator.translate(text, src=source, dest=target)
                return translation.text
            except Exception as backup_error:
                logger.error(f"대체 번역기도 실패: {backup_error}")
                return f"[번역 불가: 번역기 초기화 실패]"
            
        # 긴 텍스트는 분할하여 번역 (API 제한 고려)
        if len(text) > 500:
            parts = []
            # 문장 단위로 분할
            sentences = text.split("\n")
            current_part = ""
            
            for sentence in sentences:
                if len(current_part) + len(sentence) < 500:
                    current_part += sentence + "\n"
                else:
                    if current_part:
                        parts.append(current_part)
                    current_part = sentence + "\n"
            
            if current_part:
                parts.append(current_part)
                
            # 각 부분 번역 후 결합
            translated_parts = []
            for part in parts:
                translation = translator.translate(part, src=source, dest=target)
                translated_parts.append(translation.text)
                
            return "\n".join(translated_parts)
        else:
            # 짧은 텍스트는 한 번에 번역
            translation = translator.translate(text, src=source, dest=target)
            return translation.text
            
    except Exception as e:
        logger.error(f"번역 중 오류 발생: {e}")
        return f"[번역 오류: {str(e)}]"

def process_menu_text(ocr_result):
    """OCR 결과를 번역 처리합니다."""
    try:
        if not ocr_result["success"]:
            return ocr_result
            
        full_text = ocr_result["full_text"]
        
        # 전체 텍스트 번역
        logger.info("인식된 텍스트 번역 중...")
        translated_text = translate_text(full_text)
        
        # 번역이 실패한 경우 처리
        if translated_text.startswith('[번역 오류') or translated_text.startswith('[번역 불가'):
            return {
                "success": False,
                "error": translated_text,
                "original_text": full_text
            }
        
        # 개별 추출 텍스트 번역
        translated_items = []
        for item in ocr_result["extracted_texts"]:
            text = item["text"]
            if len(text.strip()) > 0:
                translated = translate_text(text)
                translated_items.append({
                    "original": text,
                    "translated": translated,
                    "bbox": item["bbox"],
                    "confidence": item["confidence"]
                })
        
        return {
            "success": True,
            "original_text": full_text,
            "translated_text": translated_text,
            "extracted_texts": ocr_result["extracted_texts"],
            "translated_items": translated_items
        }
    except Exception as e:
        logger.error(f"메뉴 텍스트 처리 중 오류 발생: {e}")
        return {"success": False, "error": str(e)}