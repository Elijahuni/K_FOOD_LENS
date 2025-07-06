# modules/middleware.py
import time
import uuid
import logging
from functools import wraps
from flask import request, g, jsonify
from werkzeug.exceptions import HTTPException

from modules.exceptions import KFoodLensException

logger = logging.getLogger(__name__)

def setup_middleware(app):
    """Flask 앱에 미들웨어를 설정합니다."""
    
    # 요청 전 미들웨어
    @app.before_request
    def before_request():
        # 요청 ID 생성 (추적용)
        g.request_id = str(uuid.uuid4())
        
        # 요청 시작 시간 기록 (성능 측정용)
        g.start_time = time.time()
        
        # 로그 기록
        logger.info(
            f"요청 시작: {request.method} {request.path}",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'request_ip': request.remote_addr,
                'request_ua': request.user_agent.string,
                'request_id': g.request_id
            }
        )
    
    # 요청 후 미들웨어
    @app.after_request
    def after_request(response):
        # 처리 시간 계산
        if hasattr(g, 'start_time'):
            elapsed_time = time.time() - g.start_time
            response.headers['X-Request-Time'] = str(elapsed_time)
            
            # 성능 로깅 (처리 시간이 1초 이상인 경우 경고)
            if elapsed_time > 1.0:
                logger.warning(
                    f"느린 요청 감지: {request.method} {request.path} ({elapsed_time:.2f}초)",
                    extra={
                        'request_method': request.method,
                        'request_path': request.path,
                        'response_status': response.status_code,
                        'elapsed_time': elapsed_time,
                        'request_id': getattr(g, 'request_id', 'unknown')
                    }
                )
            else:
                logger.info(
                    f"요청 완료: {request.method} {request.path} ({elapsed_time:.2f}초)",
                    extra={
                        'request_method': request.method,
                        'request_path': request.path,
                        'response_status': response.status_code,
                        'elapsed_time': elapsed_time,
                        'request_id': getattr(g, 'request_id', 'unknown')
                    }
                )
        
        # 요청 ID를 응답 헤더에 추가
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        return response
    
    # 오류 핸들러 등록
    @app.errorhandler(Exception)
    def handle_exception(e):
        # KFoodLensException 처리
        if isinstance(e, KFoodLensException):
            logger.error(
                f"KFoodLens 오류: {str(e)}",
                extra={
                    'error_type': e.__class__.__name__,
                    'error_code': getattr(e, 'code', None),
                    'error_details': getattr(e, 'details', {}),
                    'request_id': getattr(g, 'request_id', 'unknown')
                },
                exc_info=True
            )
            
            # API 요청인 경우 JSON 응답
            if request.path.startswith('/api'):
                error_response = {
                    'success': False,
                    'error': {
                        'type': e.__class__.__name__,
                        'message': str(e),
                        'code': getattr(e, 'code', None)
                    }
                }
                
                # 세부 정보 추가 (선택적)
                if hasattr(e, 'details') and e.details:
                    error_response['error']['details'] = e.details
                
                return jsonify(error_response), 400
            
            # 일반 웹 요청인 경우 오류 페이지로 리다이렉트
            from flask import render_template
            return render_template('errors/400.html', error=e), 400
        
        # HTTP 예외 처리
        elif isinstance(e, HTTPException):
            logger.warning(
                f"HTTP 예외: {e.code} - {e.description}",
                extra={
                    'status_code': e.code,
                    'error_type': e.__class__.__name__,
                    'request_id': getattr(g, 'request_id', 'unknown')
                }
            )
            
            # API 요청인 경우 JSON 응답
            if request.path.startswith('/api'):
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'HttpError',
                        'message': e.description,
                        'code': e.code
                    }
                }), e.code
            
            # 일반 오류 페이지는 기본 처리기에 위임
            return e
        
        # 처리되지 않은 예외
        else:
            logger.error(
                f"처리되지 않은 예외: {str(e)}",
                extra={
                    'error_type': e.__class__.__name__,
                    'request_id': getattr(g, 'request_id', 'unknown')
                },
                exc_info=True
            )
            
            # API 요청인 경우 JSON 응답
            if request.path.startswith('/api'):
                return jsonify({
                    'success': False,
                    'error': {
                        'type': 'InternalError',
                        'message': 'Internal server error'
                    }
                }), 500
            
            # 일반 웹 요청인 경우 500 오류 페이지
            from flask import render_template
            return render_template('errors/500.html'), 500

def log_function_call(level=logging.DEBUG):
    """함수 호출을 로깅하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            module_name = func.__module__
            
            logger = logging.getLogger(module_name)
            logger.log(level, f"함수 호출: {func_name}")
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed_time = time.time() - start_time
                
                logger.log(
                    level, 
                    f"함수 완료: {func_name} ({elapsed_time:.2f}초)",
                    extra={'elapsed_time': elapsed_time}
                )
                
                return result
            except Exception as e:
                elapsed_time = time.time() - start_time
                
                logger.error(
                    f"함수 예외: {func_name} ({elapsed_time:.2f}초): {str(e)}",
                    extra={
                        'elapsed_time': elapsed_time,
                        'error_type': e.__class__.__name__
                    },
                    exc_info=True
                )
                
                # 예외를 다시 발생시켜 호출부에서 처리하도록 함
                raise
        
        return wrapper
    return decorator