# worker.py
import os
from app import create_app

# Flask 앱 생성
app = create_app()

# Celery 앱 가져오기
celery_app = app.celery

if __name__ == '__main__':
    # 현재 파일 위치를 기준으로 프로젝트 루트 설정
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 워커 실행
    celery_app.worker_main(['worker', '--loglevel=info', '-E'])