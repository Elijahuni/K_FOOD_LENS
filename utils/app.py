# app.py
from flask import Flask, render_template
from datetime import datetime
import os
import logging

from config import get_config
from modules.database import init_db
from modules.vision import init_vision_models
from modules.ocr import init_ocr
from modules.translator import init_translator
from modules.recommender import init_recommender
from modules.cache_manager import init_cache
from routes.info import info_bp

from celery_config import init_celery

# 라우트 블루프린트 임포트
from routes.main import main_bp
from routes.menu import menu_bp
from routes.history import history_bp
from routes.api import api_bp
from routes.auth import auth_bp

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    """애플리케이션 팩토리 함수: Flask 앱 인스턴스를 생성하고 설정합니다."""
    app = Flask(__name__)
    
    # 설정 로드
    config = get_config()
    app.config.from_object(config)
    
    # 세션 설정 확인
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'kfood_lens_defalut_secret_key'
        logger.info("SECRET_KEY가 설정되지 않아 자동으로 생성되었습니다.")
    
    # 업로드 폴더 생성
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 데이터베이스 초기화
    init_db(app)
    
    # 캐시 초기화
    init_cache(app)
    
    # 모델 초기화
    init_vision_models(app)
    init_ocr(app)
    init_translator(app)
    init_recommender(app)
    
    # Celery 초기화
    celery = init_celery(app)
    app.celery = celery
    
    # 블루프린트 등록
    app.register_blueprint(main_bp)
    app.register_blueprint(menu_bp, url_prefix='/menu')
    app.register_blueprint(history_bp, url_prefix='/history')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(info_bp, url_prefix='/info')
    
    # 템플릿 전역 변수 추가
    @app.context_processor
    def inject_globals():
        return {
            'current_year': datetime.now().year
        }
    
    # 오류 핸들러 등록
    register_error_handlers(app)
    
    return app

def register_error_handlers(app):
    """애플리케이션의 오류 핸들러를 등록합니다."""
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

def add_setup_code_to_app():
    """
    app.py 파일에 셋업 코드를 추가하는 함수
    """
    app_path = 'app.py'
    
    # 백업 파일 생성
    backup_path = 'app.py.bak'
    shutil.copy2(app_path, backup_path)
    print(f"app.py 파일 백업 생성: {backup_path}")
    
    with open(app_path, 'r', encoding='utf-8') as f:
        app_content = f.read()
        
        # 수정된 내용 저장
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(app_content)
        
        print(f"app.py 파일에 셋업 코드가 추가되었습니다: {app_path}")    
app = create_app()
celery = app.celery
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)