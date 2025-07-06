# routes/menu.py
import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename

from modules.database import save_menu_recognition_result
from modules.vision import verify_image
from modules.ocr import process_image_text
from modules.translator import process_menu_text

logger = logging.getLogger(__name__)

menu_bp = Blueprint('menu', __name__)

def allowed_file(filename):
    """허용된 파일 확장자인지 확인합니다."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@menu_bp.route('/')
def menu_translate():
    """메뉴판 인식 페이지"""
    # 이전 세션 데이터 초기화
    if 'menu_image_path' in session:
        session.pop('menu_image_path', None)
    return render_template('menu_translate.html', active_page='menu_translate')

@menu_bp.route('/upload', methods=['POST'])
def menu_upload():
    """메뉴판 이미지 업로드 처리"""
    if 'file' not in request.files:
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(url_for('menu.menu_translate'))
        
    file = request.files['file']
    if file.filename == '':
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(url_for('menu.menu_translate'))
    
    try:
        # 파일 저장
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"menu_{timestamp}_{filename}"  # 메뉴판 이미지 구분을 위한 접두어
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 세션에 파일 경로 저장
        session['menu_image_path'] = file_path
        
        # 이미지 URL에 타임스탬프 추가하여 캐싱 방지
        preview_url = f"{url_for('static', filename=f'uploads/{filename}')}?t={timestamp}"
        
        return render_template('menu_translate.html', 
                              active_page='menu_translate',
                              preview_image=preview_url,
                              image_path=file_path)
                               
    except Exception as e:
        logger.error(f"메뉴판 파일 업로드 중 오류 발생: {e}")
        flash('파일 업로드 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('menu.menu_translate'))

@menu_bp.route('/process', methods=['POST'])
def process_menu():
    """메뉴판 텍스트 인식 및 번역 처리"""
    image_path = request.form.get('image_path')
    if not image_path or not os.path.exists(image_path):
        flash('이미지를 먼저 업로드해주세요.', 'error')
        return redirect(url_for('menu.menu_translate'))
    
    try:
        # 이미지 검증
        if not verify_image(image_path):
            flash('이미지 파일을 읽을 수 없습니다. 다른 이미지로 시도해보세요.', 'error')
            return redirect(url_for('menu.menu_translate'))
        
        # 처리 중임을 표시
        processing_started = True
        
        # 메뉴판 이미지 처리
        logger.info(f"메뉴판 이미지 처리 시작: {image_path}")
        
        # 1. OCR 텍스트 인식 - 오류 처리 추가
        try:
            ocr_result = process_image_text(image_path)
            logger.info(f"OCR 결과: {ocr_result}")
        except Exception as e:
            logger.error(f"OCR 처리 중 오류 발생: {e}")
            return render_template('menu_translate.html', 
                               active_page='menu_translate',
                               preview_image=url_for('static', filename=f'uploads/{os.path.basename(image_path)}'),
                               image_path=image_path,
                               ocr_error=f"OCR 처리 중 오류 발생: {e}")
        
        if not ocr_result["success"]:
            error_msg = ocr_result.get("error", "알 수 없는 오류")
            logger.error(f"OCR 실패: {error_msg}")
            return render_template('menu_translate.html', 
                               active_page='menu_translate',
                               preview_image=url_for('static', filename=f'uploads/{os.path.basename(image_path)}'),
                               image_path=image_path,
                               ocr_error=error_msg)
        
        # 2. 번역 처리 - 오류 처리 추가
        try:
            result = process_menu_text(ocr_result)
            logger.info(f"번역 결과: {result}")
        except Exception as e:
            logger.error(f"번역 처리 중 오류 발생: {e}")
            # 실패해도 OCR 결과는 보여주기
            return render_template('menu_translate.html', 
                               active_page='menu_translate',
                               preview_image=url_for('static', filename=f'uploads/{os.path.basename(image_path)}'),
                               image_path=image_path,
                               ocr_result={"success": True, "original_text": ocr_result["full_text"], "translated_text": "Translation service unavailable"},
                               translation_error=f"번역 처리 중 오류 발생: {e}")
        
        # 3. 인식 결과 저장
        try:
            record_id = save_menu_recognition_result(
                image_path, 
                result.get('original_text', ''), 
                result.get('translated_text', '')
            )
            logger.info(f"메뉴판 인식 결과 저장 완료, 기록 ID: {record_id}")
        except Exception as e:
            logger.error(f"메뉴판 인식 결과 저장 중 오류 발생: {e}")
            # 저장 실패는 큰 문제가 아니므로 계속 진행
        
        # 결과 페이지 렌더링
        return render_template('menu_translate.html', 
                               active_page='menu_translate',
                               ocr_result=result,
                               preview_image=url_for('static', filename=f'uploads/{os.path.basename(image_path)}'))
                               
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"메뉴판 인식 처리 중 오류 발생: {e}")
        logger.error(error_traceback)
        return render_template('menu_translate.html', 
                           active_page='menu_translate',
                           preview_image=url_for('static', filename=f'uploads/{os.path.basename(image_path)}'),
                           image_path=image_path,
                           system_error=str(e))