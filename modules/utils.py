# modules/utils.py
import os
import logging
import json
from datetime import datetime
from flask import url_for

logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions):
    """허용된 파일 확장자인지 확인합니다."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def generate_unique_filename(original_filename, prefix=''):
    """타임스탬프를 포함한 고유한 파일명을 생성합니다."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{prefix}_{timestamp}_{original_filename}" if prefix else f"{timestamp}_{original_filename}"
    return filename

def get_file_url(file_path):
    """파일 경로에서 URL을 생성합니다."""
    if not file_path:
        return None
    
    filename = os.path.basename(file_path)
    return url_for('static', filename=f'uploads/{filename}')

def load_json_file(file_path):
    """JSON 파일을 로드합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"JSON 파일 로드 중 오류 발생: {e}")
        return None

def save_json_file(data, file_path):
    """데이터를 JSON 파일로 저장합니다."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"JSON 파일 저장 중 오류 발생: {e}")
        return False

def format_percentage(value, decimal_places=1):
    """소수값을 백분율 문자열로 변환합니다."""
    if value is None:
        return "0%"
    return f"{value * 100:.{decimal_places}f}%"

def format_datetime(dt, format_str='%Y-%m-%d %H:%M'):
    """날짜 시간 객체를 지정된 형식의 문자열로 변환합니다."""
    if not dt:
        return ""
    return dt.strftime(format_str)

def sanitize_input(text):
    """사용자 입력 텍스트를 안전하게 처리합니다."""
    if not text:
        return ""
    # HTML 태그 제거
    import re
    text = re.sub(r'<[^>]*>', '', text)
    # 공백 정리
    text = text.strip()
    return text

def get_pagination_data(total_items, page, per_page):
    """페이지네이션 데이터를 계산합니다."""
    total_pages = (total_items + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    return {
        'total_items': total_items,
        'total_pages': total_pages,
        'current_page': page,
        'per_page': per_page,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': page - 1 if has_prev else None,
        'next_page': page + 1 if has_next else None
    }