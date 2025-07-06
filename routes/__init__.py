# 라우트 패키지 초기화
from .main import main_bp
from .menu import menu_bp
from .history import history_bp
from .api import api_bp
from .auth import auth_bp

# 모든 블루프린트 목록
blueprints = [main_bp, menu_bp, history_bp, api_bp, auth_bp]