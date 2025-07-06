# modules/cache_manager.py
import logging
import functools
from flask import current_app
from flask_caching import Cache

# 캐시 객체 초기화
cache = Cache()
logger = logging.getLogger(__name__)

def init_cache(app):
    """캐시 초기화 함수"""
    try:
        # 캐시 설정 가져오기
        cache_config = {
            'CACHE_TYPE': app.config.get('CACHE_TYPE', 'SimpleCache'),
            'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_TIMEOUT', 300),
            'CACHE_THRESHOLD': app.config.get('CACHE_THRESHOLD', 500)
        }
        
        if cache_config['CACHE_TYPE'] == 'RedisCache':
            cache_config['CACHE_REDIS_URL'] = app.config.get('CACHE_REDIS_URL', 'redis://localhost:6379/0')
        
        # 캐시 초기화
        cache.init_app(app, config=cache_config)
        logger.info(f"캐시가 초기화되었습니다: {cache_config['CACHE_TYPE']}")
        return True
    except Exception as e:
        logger.error(f"캐시 초기화 중 오류 발생: {e}")
        return False

def cached(timeout=300, key_prefix=''):
    """편리한 캐싱 데코레이터 함수"""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # 캐시가 초기화되지 않은 경우 원본 함수 실행
            if not hasattr(current_app, 'extensions') or 'cache' not in current_app.extensions:
                return f(*args, **kwargs)
            
            # 캐시 키 생성
            cache_key = f"{key_prefix}_{f.__name__}"
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    cache_key += f"_{arg}"
                
            for k, v in kwargs.items():
                if isinstance(v, (str, int, float, bool)):
                    cache_key += f"_{k}_{v}"
            
            # 캐시에서 결과 가져오기 시도
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"캐시 적중: {cache_key}")
                return cached_result
            
            # 캐시 미스 - 원본 함수 실행 및 결과 캐싱
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            logger.debug(f"캐시 저장: {cache_key}, 타임아웃: {timeout}초")
            return result
        
        return decorated_function
    
    return decorator

def invalidate_cache(pattern):
    """특정 패턴과 일치하는 모든 캐시 항목 무효화"""
    try:
        if not hasattr(current_app, 'extensions') or 'cache' not in current_app.extensions:
            logger.warning("캐시가 초기화되지 않아 무효화를 수행할 수 없습니다.")
            return False
            
        if hasattr(cache, 'delete_memoized'):
            # 메모이즈된 함수 캐시 지우기
            if pattern.endswith('*'):
                # 와일드카드 패턴으로 시작하는 모든 항목 삭제
                prefix = pattern[:-1]
                deleted = 0
                for key in cache.cache._cache.keys():
                    if isinstance(key, str) and key.startswith(prefix):
                        cache.delete(key)
                        deleted += 1
                logger.info(f"{deleted}개의 캐시 항목이 '{pattern}' 패턴으로 무효화되었습니다.")
            else:
                # 정확한 키 삭제
                cache.delete(pattern)
                logger.info(f"캐시 항목 '{pattern}'이(가) 무효화되었습니다.")
            return True
        else:
            logger.warning("현재 캐시 백엔드는 패턴 기반 무효화를 지원하지 않습니다.")
            return False
    except Exception as e:
        logger.error(f"캐시 무효화 중 오류 발생: {e}")
        return False