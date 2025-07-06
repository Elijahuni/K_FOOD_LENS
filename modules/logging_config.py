# modules/logging_config.py
import os
import json
import logging
import logging.config
import traceback
from datetime import datetime
from pythonjsonlogger import jsonlogger
from flask import request, has_request_context, g

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """사용자 정의 JSON 포맷터"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # 표준 필드 추가
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # 예외 정보 추가
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # 요청 컨텍스트 정보 추가
        if has_request_context():
            log_record['request'] = {
                'method': request.method,
                'path': request.path,
                'ip': request.remote_addr
            }
            
            # 사용자 정보 추가 (로그인된 경우)
            if hasattr(g, 'user'):
                log_record['user'] = g.user.get('username', 'anonymous')
            
            # 요청 ID 추가 (있는 경우)
            if hasattr(g, 'request_id'):
                log_record['request_id'] = g.request_id

class RequestIdFilter(logging.Filter):
    """요청 ID를 로그에 추가하는 필터"""
    
    def filter(self, record):
        if has_request_context() and hasattr(g, 'request_id'):
            record.request_id = g.request_id
        else:
            record.request_id = 'no_request_id'
        return True

def setup_logging(app):
    """애플리케이션의 로깅 시스템을 설정합니다."""
    
    # 로그 디렉토리 생성
    log_dir = os.path.join(app.root_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 로깅 설정
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s'
            },
            'json': {
                '()': CustomJsonFormatter,
                'format': '%(timestamp)s %(level)s %(module)s %(function)s %(line)s %(message)s'
            }
        },
        'filters': {
            'request_id': {
                '()': RequestIdFilter,
            }
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'filters': ['request_id']
            },
            'file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'kfood_lens.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'formatter': 'standard',
                'filters': ['request_id']
            },
            'error_file': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'error.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'formatter': 'json',
                'filters': ['request_id']
            },
            'json_file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'kfood_lens.json'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'formatter': 'json',
                'filters': ['request_id']
            }
        },
        'loggers': {
            '': {  # 루트 로거
                'handlers': ['console', 'file', 'error_file', 'json_file'],
                'level': 'INFO',
                'propagate': True
            },
            'kfood_lens': {
                'handlers': ['console', 'file', 'error_file', 'json_file'],
                'level': 'INFO',
                'propagate': False
            },
            'modules.vision': {
                'level': 'DEBUG',
                'propagate': True
            },
            'modules.ocr': {
                'level': 'DEBUG',
                'propagate': True
            }
        }
    }
    
    # 로깅 설정 적용
    logging.config.dictConfig(logging_config)
    
    # 앱 로거 생성
    app.logger.setLevel(logging.INFO)
    
    app.logger.info("로깅 시스템 초기화 완료")