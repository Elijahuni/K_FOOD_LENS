# routes/main.py
import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId

from modules.database import get_db, get_food_info, save_recognition_result
from modules.vision import ensemble_predictions_class_based, verify_image, get_class_to_metadata_mapping
from modules.visualization import create_text_overlay_image, generate_modal_data, create_interactive_html

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

def allowed_file(filename):
    """허용된 파일 확장자인지 확인합니다."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@main_bp.route('/')
def index():
    """메인 페이지 - 음식 인식 기능 제공"""
    return render_template('index.html', active_page='index')

@main_bp.route('/upload', methods=['POST'])
def upload():
    logger.info("Upload 라우트 호출됨")
    """이미지 업로드 처리"""
    if 'file' not in request.files:
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(url_for('main.index'))
        
    file = request.files['file']
    if file.filename == '':
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(url_for('main.index'))
    
    if not allowed_file(file.filename):
        flash('지원되지 않는 파일 형식입니다. 이미지 파일(png, jpg, jpeg, gif)만 업로드 가능합니다.', 'error')
        return redirect(url_for('main.index'))
        
    try: 
        # 파일 저장
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"파일 저장 시도: {filename}")
        file.save(file_path)
        logger.info(f"파일 저장 성공: {file_path}")
        
        # 세션에 파일 경로 저장
        session['image_path'] = file_path
        
        return render_template('index.html', 
                               active_page='index',
                               preview_image=url_for('static', filename=f'uploads/{filename}'),
                               image_path=file_path)
                               
    except Exception as e:
        logger.error(f"파일 업로드 중 오류 발생: {e}")
        flash('파일 업로드 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

@main_bp.route('/info')
def info():
    """도움말 페이지"""
    return render_template('info.html', active_page='info')

@main_bp.route('/predict', methods=['POST'])
def predict():
    """음식 이미지 인식 처리"""
    image_path = request.form.get('image_path')
    
    if not image_path or not os.path.exists(image_path):
        flash('이미지를 먼저 업로드해주세요.', 'error')
        return redirect(url_for('main.index'))
    
    try:
        # 이미지 검증
        if not verify_image(image_path):
            flash('이미지 파일을 읽을 수 없습니다. 다른 이미지로 시도해보세요.', 'error')
            return redirect(url_for('main.index'))
        
        # 클래스 기반 앙상블 예측 수행
        logger.info(f"이미지 경로: {image_path} 인식 중...")
        boxes, scores, class_ids = ensemble_predictions_class_based(image_path)
        
        # 결과가 비어 있는지 확인
        if len(boxes) == 0:
            flash('음식을 인식하지 못했습니다. 다른 이미지로 시도해보세요.', 'error')
            return redirect(url_for('main.index'))
        
        # 클래스-메타데이터 매핑 가져오기
        class_mapping = get_class_to_metadata_mapping()
        
        # 결과 포맷팅 및 음식 정보 추가
        predictions = []
        detected_foods = []
        food_info_dict = {}  # 클래스 이름별 음식 정보 매핑
        
        # 모델 가져오기 (클래스 이름을 위해)
        from modules.vision import get_models
        model_m, _ = get_models()
        if model_m is None:
            flash('모델을 로드하는 중 오류가 발생했습니다.', 'error')
            return redirect(url_for('main.index'))
        
        class_names = model_m.names
        
        for i in range(len(boxes)):
            try:
                box = boxes[i]
                class_id = int(class_ids[i])
                score = scores[i]
                
                class_name = class_names.get(class_id, f"unknown_{class_id}")
                logger.info(f"인식된 음식: {class_name} (신뢰도: {score:.2f})")
                
                # MongoDB에서 음식 정보 가져오기
                food_info = get_food_info(class_name, class_mapping)
                
                prediction = {
                    'class_id': class_id,
                    'class_name': class_name,
                    'confidence': float(score),
                    'box': {
                        'x1': float(box[0]),
                        'y1': float(box[1]),
                        'x2': float(box[2]),
                        'y2': float(box[3])
                    }
                }
                
                # 음식 정보가 있으면 추가
                if food_info:
                    # MongoDB의 네이밍 규칙에 따라 필드 이름 매핑
                    food_info_dict[class_name] = food_info
                    
                    # 직접 food_info를 prediction에 할당
                    prediction['food_info'] = food_info
                else:
                    # 기본 정보라도 제공
                    prediction['food_info'] = {
                        'nameKo': class_name,
                        'nameEn': class_name,
                        'allergens': [],
                        'vegetarianStatus': '알 수 없음',
                        'descriptionKo': '',
                        'descriptionEn': '',
                        'classId': '',
                        'className': ''
                    }
                
                predictions.append(prediction)
                detected_foods.append({
                    'food_name': class_name,
                    'confidence': float(score),
                    'nameKo': prediction['food_info'].get('nameKo', class_name),
                    'nameEn': prediction['food_info'].get('nameEn', class_name),
                    'allergens': prediction['food_info'].get('allergens', []),
                    'vegetarianStatus': prediction['food_info'].get('vegetarianStatus', '알 수 없음')
                })
                
            except Exception as e:
                logger.error(f"개별 예측 결과 처리 중 오류: {e}")
                continue
        
        # 디버깅을 위한 로그 추가
        for pred in predictions:
            logger.info(f"예측 결과: {pred['class_name']}, 정보: nameKo={pred['food_info'].get('nameKo')}, nameEn={pred['food_info'].get('nameEn')}")                
        
        # 시각화 결과 생성
        # 1. 텍스트 오버레이 이미지
        overlay_image_path = create_text_overlay_image(image_path, boxes, scores, class_ids, class_names, food_info_dict)
        # 오버레이 이미지 URL 생성 (처리된 이미지를 표시하기 위함)
        overlay_image_url = None
        if overlay_image_path:
            overlay_image_filename = os.path.basename(overlay_image_path)
            overlay_image_url = url_for('static', filename=f'uploads/results/{overlay_image_filename}')
        
        # 바운딩 박스 정보 생성
        bounding_boxes = []
        for i in range(len(boxes)):
            box = boxes[i]
            class_id = int(class_ids[i])
            score = scores[i]
            class_name = class_names.get(class_id, f"unknown_{class_id}")
            
            bounding_boxes.append({
                'x1': float(box[0]),
                'y1': float(box[1]),
                'x2': float(box[2]),
                'y2': float(box[3]),
                'class_name': class_name,
                'confidence': float(score)
            })
            
        # 세션에 사용자가 로그인한 경우, 사용자 기록 업데이트
        if 'user_id' in session:
            try:
                # 사용자 통계 업데이트
                db = get_db()
                db.users.update_one(
                    {'_id': ObjectId(session['user_id'])},
                    {'$inc': {'stats.recognitions': 1}}
                )
                logger.info(f"사용자 {session['user_id']} 통계 업데이트 완료")
            except Exception as e:
                logger.error(f"사용자 통계 업데이트 중 오류: {e}")
        
        # 인식 결과를 MongoDB에 저장
        record_id = save_recognition_result(image_path, detected_foods, overlay_image_path)
        logger.info(f"인식 결과 저장 완료, 기록 ID: {record_id}")    
        # 결과 페이지 렌더링
        return render_template('index.html', 
                              active_page='index',
                              predictions=predictions,
                              preview_image=url_for('static', filename=f'uploads/{os.path.basename(image_path)}'),
                              overlay_image_url=overlay_image_url,  # 오버레이 이미지 URL 추가
                              bounding_boxes=bounding_boxes,  # 바운딩 박스 정보 추가
                              record_id=str(record_id)  # 기록 ID 추가
                              )
                               
    except Exception as e:
        logger.error(f"예측 중 오류 발생: {e}", exc_info=True)
        flash('음식 인식 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

@main_bp.route('/processing')
def processing():
    """작업 처리 중 페이지"""
    task_id = request.args.get('task_id')
    task_type = request.args.get('type', 'food')  # food 또는 menu
    
    if not task_id:
        flash('작업 ID가 필요합니다.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template(
        'processing.html', 
        task_id=task_id, 
        task_type=task_type,
        check_url=url_for('main.check_task_status', task_id=task_id)
    )

@main_bp.route('/check-task/<task_id>')
def check_task_status(task_id):
    """작업 상태 확인 API"""
    try:
        # Celery 사용 중인 경우
        try:
            from celery.result import AsyncResult
            celery_app = current_app.celery
            task_result = AsyncResult(task_id, app=celery_app)
            
            if task_result.state == 'PENDING':
                response = {
                    'state': 'PENDING',
                    'status': '작업 대기 중...'
                }
            elif task_result.state == 'PROCESSING':
                response = {
                    'state': 'PROCESSING',
                    'status': task_result.info.get('status', '처리 중...')
                }
            elif task_result.state == 'SUCCESS':
                response = {
                    'state': 'SUCCESS',
                    'result': task_result.result
                }
            elif task_result.state == 'FAILURE':
                response = {
                    'state': 'FAILURE',
                    'error': str(task_result.result)
                }
            else:
                response = {
                    'state': task_result.state,
                    'status': '작업 진행 중...'
                }
        except ImportError:
            # Celery가 설치되지 않은 경우 간단한 응답
            response = {
                'state': 'NOT_SUPPORTED',
                'error': 'Celery task queue is not configured'
            }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"작업 상태 확인 중 오류: {e}")
        return jsonify({
            'state': 'ERROR',
            'error': str(e)
        }), 500

@main_bp.route('/result/<task_id>')
def show_result(task_id):
    """작업 결과 페이지"""
    try:
        # Celery 사용 중인 경우
        try:
            from celery.result import AsyncResult
            celery_app = current_app.celery
            task_result = AsyncResult(task_id, app=celery_app)
            
            if task_result.state != 'SUCCESS':
                flash('작업이 아직 완료되지 않았습니다.', 'error')
                return redirect(url_for('main.processing', task_id=task_id))
            
            result = task_result.result
        except ImportError:
            # Celery가 설치되지 않은 경우 간단한 응답
            flash('작업 큐가 설정되지 않았습니다.', 'error')
            return redirect(url_for('main.index'))
        
        if not result.get('success', False):
            flash('인식에 실패했습니다: ' + result.get('error', '알 수 없는 오류'), 'error')
            return redirect(url_for('main.index'))
        
        # 결과 화면 렌더링
        task_type = request.args.get('type', 'food')
        
        if task_type == 'food':
            return render_template(
                'index.html', 
                active_page='index',
                predictions=result.get('predictions', []),
                preview_image=url_for('static', filename=f'uploads/{os.path.basename(result["overlay_image_path"])}'),
                interactive_result_url=url_for(
                    'main.view_interactive_result', 
                    filename=os.path.basename(result.get('interactive_html_path', ''))
                )
            )
        else:  # menu
            return render_template(
                'menu_translate.html', 
                active_page='menu_translate',
                ocr_result=result.get('ocr_result', {}),
                preview_image=url_for('static', filename=f'uploads/{os.path.basename(result["image_path"])}')
            )
            
    except Exception as e:
        logger.error(f"결과 표시 중 오류: {e}")
        flash('결과를 표시하는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

@main_bp.route('/interactive/<filename>')
def view_interactive_result(filename):
    """인터랙티브 결과 페이지 제공"""
    results_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'results')
    return send_from_directory(results_dir, filename)