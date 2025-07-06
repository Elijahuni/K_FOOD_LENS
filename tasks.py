# tasks.py
from celery import shared_task, Celery
import logging
from modules.recommender import get_recommender

logger = logging.getLogger(__name__)

# Celery 애플리케이션 객체 생성
broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery = Celery('k_food_lens',
               broker='redis://localhost:6379/0',
               backend='redis://localhost:6379/0')

# 신 형식 설정 사용
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    worker_prefetch_multiplier=1,
)

@shared_task
def example_task(x, y):
    """예제 Celery 태스크"""
    logger.info(f"Executing example task with args: {x}, {y}")
    return x + y

@shared_task
def update_similar_foods_task():
    """유사 음식 정보를 일괄 업데이트하는 백그라운드 태스크"""
    try:
        logger.info("유사 음식 정보 업데이트 태스크 시작")
        recommender = get_recommender()
        
        if not recommender:
            logger.error("추천 시스템이 초기화되지 않았습니다.")
            return {"success": False, "error": "추천 시스템이 초기화되지 않았습니다."}
        
        # 유사 음식 정보 업데이트 실행
        result = recommender.update_similar_foods_in_db()
        
        if result.get("success", False):
            logger.info(f"유사 음식 정보 업데이트 완료: {result.get('updated_count', 0)}개 업데이트됨")
            return {
                "success": True,
                "message": "유사 음식 업데이트 완료",
                "updated_count": result.get('updated_count', 0)
            }
        else:
            logger.error(f"유사 음식 정보 업데이트 실패: {result.get('error', '알 수 없는 오류')}")
            return {
                "success": False,
                "error": result.get('error', '알 수 없는 오류')
            }
    except Exception as e:
        logger.error(f"유사 음식 정보 업데이트 태스크 실행 중 오류 발생: {e}")
        return {"success": False, "error": str(e)}

@shared_task
def process_uploaded_image_task(image_path):
    """이미지 처리를 위한 백그라운드 태스크"""
    try:
        from modules.vision import ensemble_predictions_class_based, get_class_to_metadata_mapping
        from modules.database import get_food_info, save_recognition_result
        
        logger.info(f"이미지 처리 태스크 시작: {image_path}")
        
        # 이미지 인식 수행
        boxes, scores, class_ids = ensemble_predictions_class_based(image_path)
        
        if len(boxes) == 0:
            logger.warning(f"인식된 음식이 없습니다: {image_path}")
            return {"success": False, "error": "인식된 음식이 없습니다."}
        
        # 클래스-메타데이터 매핑 가져오기
        class_mapping = get_class_to_metadata_mapping()
        
        # 결과 포맷팅
        detected_foods = []
        
        # 모델 클래스 이름 가져오기
        from modules.vision import get_models
        model_m, _ = get_models()
        
        for i in range(len(boxes)):
            class_id = int(class_ids[i])
            score = scores[i]
            class_name = model_m.names.get(class_id, f"unknown_{class_id}")
            
            detected_foods.append({
                'food_name': class_name,
                'confidence': float(score)
            })
        
        # 인식 결과 저장
        save_recognition_result(image_path, detected_foods)
        
        return {
            "success": True,
            "detected_foods": detected_foods,
            "image_path": image_path
        }
    except Exception as e:
        logger.error(f"이미지 처리 태스크 실행 중 오류 발생: {e}")
        return {"success": False, "error": str(e)}