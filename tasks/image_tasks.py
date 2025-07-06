# tasks/image_tasks.py
import os
import logging
import json
from celery import shared_task
from datetime import datetime
from bson import ObjectId

from modules.database import get_db, save_recognition_result
from modules.vision import (
    ensemble_predictions_class_based, 
    get_class_to_metadata_mapping,
    create_text_overlay_image,
    generate_modal_data,
    create_interactive_html
)

logger = logging.getLogger(__name__)

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True
)
def process_food_image(self, image_path, save_history=True):
    """음식 이미지를 비동기적으로 처리합니다."""
    task_id = self.request.id
    logger.info(f"이미지 처리 시작: {image_path} (작업 ID: {task_id})")
    
    # 작업 상태 업데이트
    self.update_state(state='PROCESSING', meta={'status': '이미지 분석 중...'})
    
    try:
        # 이미지 존재 확인
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        
        # 이미지 예측 수행
        boxes, scores, class_ids = ensemble_predictions_class_based(image_path)
        
        # 결과가 비어 있는지 확인
        if len(boxes) == 0:
            return {'success': False, 'error': '음식을 인식하지 못했습니다.'}
        
        # 클래스-메타데이터 매핑 가져오기
        class_mapping = get_class_to_metadata_mapping()
        
        # YOLO 모델의 클래스 이름 가져오기
        from modules.vision import get_models
        model_m, _ = get_models()
        if model_m is None:
            raise RuntimeError("모델 로드 실패")
        
        # 결과 처리
        predictions = []
        detected_foods = []
        food_info_dict = {}  # 클래스 이름별 음식 정보 매핑
        
        # 상태 업데이트
        self.update_state(state='PROCESSING', meta={'status': '인식된 음식 정보 검색 중...'})
        
        # 각 인식 결과 처리
        for i in range(len(boxes)):
            box = boxes[i]
            class_id = int(class_ids[i])
            score = scores[i]
            class_name = model_m.names.get(class_id, f"unknown_{class_id}")
            
            # MongoDB에서 음식 정보 가져오기
            from modules.database import get_food_info
            food_info = get_food_info(class_name, class_mapping)
            
            prediction = {
                'class_id': class_id,
                'class_name': class_name,
                'confidence': float(score),
                'box': {
                    'x1': float(box[0]),
                    'y1': float(box[1]),
                    'x2': float(box[2]),
                    'y2': float(box[3])
                }
            }
            
            # 음식 정보가 있으면 추가
            if food_info:
                food_info_dict[class_name] = food_info
                
                prediction['food_info'] = {
                    'name_ko': food_info.get('nameKo', ''),
                    'name_en': food_info.get('nameEn', ''),
                    'allergens': food_info.get('allergens', []),
                    'vegetarian_status': food_info.get('vegetarianStatus', '알 수 없음'),
                    'description_ko': food_info.get('descriptionKo', ''),
                    'description_en': food_info.get('descriptionEn', ''),
                    'class_id': food_info.get('classId', ''),
                    'class_name': food_info.get('className', '')
                }
                
                # 유사 음식 추천 정보 추가
                if food_info.get('dishId') and 'similarFoods' in food_info:
                    prediction['recommended_foods'] = food_info['similarFoods']
            else:
                # 기본 정보 제공
                prediction['food_info'] = {
                    'name_ko': class_name,
                    'name_en': class_name,
                    'allergens': [],
                    'vegetarian_status': '알 수 없음',
                    'description_ko': '',
                    'description_en': '',
                    'class_id': '',
                    'class_name': ''
                }
            
            predictions.append(prediction)
            detected_foods.append({
                'food_name': class_name,
                'confidence': float(score)
            })
        
        # 시각화 결과 생성 (상태 업데이트)
        self.update_state(state='PROCESSING', meta={'status': '결과 시각화 생성 중...'})
        
        # 1. 텍스트 오버레이 이미지
        overlay_image_path = create_text_overlay_image(
            image_path, boxes, scores, class_ids, model_m.names, food_info_dict
        )
        
        # 2. 인터랙티브 HTML 결과 페이지
        modal_data = generate_modal_data(
            image_path, boxes, scores, class_ids, model_m.names, food_info_dict
        )
        interactive_html_path = create_interactive_html(modal_data)
        
        # 히스토리 저장 (선택적)
        if save_history:
            self.update_state(state='PROCESSING', meta={'status': '인식 기록 저장 중...'})
            record_id = save_recognition_result(image_path, detected_foods)
            logger.info(f"인식 결과 저장 완료: {record_id}")
        
        # 결과 반환
        result = {
            'success': True,
            'predictions': predictions,
            'overlay_image_path': overlay_image_path,
            'interactive_html_path': interactive_html_path,
            'detected_foods': detected_foods
        }
        
        # 직렬화 가능하도록 변환
        return json.loads(json.dumps(result, cls=JSONEncoder))
        
    except Exception as e:
        import traceback
        logger.error(f"이미지 처리 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        raise  # 재시도를 위해 예외 다시 발생

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