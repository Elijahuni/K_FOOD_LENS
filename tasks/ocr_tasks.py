# tasks/ocr_tasks.py
from celery import shared_task
import logging
import json
from datetime import datetime

from modules.ocr import process_image_text
from modules.translator import process_menu_text
from modules.database import save_menu_recognition_result

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 3},
    retry_backoff=True
)
def process_menu_image(self, image_path, save_history=True):
    """메뉴판 이미지를 비동기적으로 처리합니다."""
    task_id = self.request.id
    logger.info(f"메뉴 이미지 처리 시작: {image_path} (작업 ID: {task_id})")
    
    try:
        # 작업 상태 업데이트
        self.update_state(state='PROCESSING', meta={'status': '텍스트 인식 중...'})
        
        # 1. OCR 텍스트 인식
        ocr_result = process_image_text(image_path)
        
        if not ocr_result["success"]:
            error_msg = ocr_result.get("error", "알 수 없는 오류")
            logger.error(f"OCR 실패: {error_msg}")
            return {
                'success': False, 
                'error': error_msg,
                'stage': 'ocr'
            }
        
        # 작업 상태 업데이트
        self.update_state(state='PROCESSING', meta={'status': '번역 중...'})
        
        # 2. 번역 처리
        result = process_menu_text(ocr_result)
        
        if not result["success"]:
            error_msg = result.get("error", "알 수 없는 오류")
            logger.error(f"번역 실패: {error_msg}")
            return {
                'success': False, 
                'error': error_msg,
                'stage': 'translation',
                'original_text': result.get('original_text', '')
            }
        
        # 3. 히스토리 저장 (선택적)
        if save_history:
            self.update_state(state='PROCESSING', meta={'status': '번역 결과 저장 중...'})
            record_id = save_menu_recognition_result(
                image_path, 
                result.get('original_text', ''), 
                result.get('translated_text', '')
            )
            logger.info(f"메뉴 인식 결과 저장 완료: {record_id}")
        
        # 결과 반환
        return {
            'success': True,
            'ocr_result': result
        }
    
    except Exception as e:
        import traceback
        logger.error(f"메뉴판 인식 처리 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        
        # 재시도를 위해 예외 다시 발생
        raise