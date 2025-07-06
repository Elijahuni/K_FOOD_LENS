# celery_config.py
import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

def init_celery(app=None):
    # Celery 설정
    broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    celery = Celery(
        'k_food_lens',
        broker=broker_url,
        backend=result_backend,
        include=['tasks']
    )
    
    # Celery 기본 설정 - 신 형식 사용
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        enable_utc=True,
        task_track_started=True,
        worker_hijack_root_logger=False,
        worker_prefetch_multiplier=1,
    )
    
    # 앱 설정에서 Celery 설정 가져올 때 신/구 형식 변환 추가
    if app:
        # 앱 설정에서 Celery 설정 가져오기
        celery_config = {}
        for key, value in app.config.items():
            # 구 형식(CELERY_*)을 신 형식으로 변환
            if key.startswith('CELERY_'):
                new_key = key[7:].lower()
                celery_config[new_key] = value
            # 이미 신 형식인 경우 그대로 사용
            elif key.islower() and not key.startswith('celery_'):
                celery_config[key] = value
                
        celery.conf.update(celery_config)
        
        # Flask 앱 컨텍스트 통합
        class FlaskTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = FlaskTask
        
        logger.info("Celery가 Flask 앱과 함께 초기화되었습니다.")
    else:
        logger.info("Celery가 독립 모드로 초기화되었습니다.")
    
    return celery

# 빈 tasks.py 파일 생성
def create_tasks_file():
    tasks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.py')
    if not os.path.exists(tasks_path):
        with open(tasks_path, 'w', encoding='utf-8') as f:
            f.write('''from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def example_task(x, y):
    """예제 Celery 태스크"""
    logger.info(f"Executing example task with args: {x}, {y}")
    return x + y
''')
        logger.info("tasks.py 파일이 생성되었습니다.")

# 파일이 직접 실행될 때 tasks.py 파일 생성
if __name__ == "__main__":
    create_tasks_file()