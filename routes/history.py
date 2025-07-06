# routes/history.py
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from bson.objectid import ObjectId
import os
from datetime import datetime

from modules.database import get_recent_recognitions, get_recent_menu_recognitions, get_food_info, get_db

logger = logging.getLogger(__name__)

history_bp = Blueprint('history', __name__)

@history_bp.route('/')
def index():
    """인식 기록 메인 페이지"""
    try:
        # 페이지네이션을 위한 파라미터
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # 필터링 옵션
        filter_type = request.args.get('type', 'all')  # 'all', 'food', 'menu'
        
        # 사용자별 필터링 (로그인한 경우)
        user_filter = {}
        if 'user_id' in session:
            user_filter = {'user_id': session['user_id']}
        
        # 검색어 처리
        search_query = request.args.get('search', '')
        search_filter = {}
        if search_query:
            # 음식 이름이나 메뉴 텍스트에서 검색
            search_filter = {
                '$or': [
                    {'detected_foods.food_name': {'$regex': search_query, '$options': 'i'}},
                    {'detected_foods.nameKo': {'$regex': search_query, '$options': 'i'}},
                    {'detected_foods.nameEn': {'$regex': search_query, '$options': 'i'}},
                    {'original_text': {'$regex': search_query, '$options': 'i'}},
                    {'translated_text': {'$regex': search_query, '$options': 'i'}}
                ]
            }
        
        # 필터 조합
        combined_filter = {**user_filter, **search_filter}
        
        db = get_db()
        records = []
        total_records = 0
        
        # 기록 유형에 따라 다른 컬렉션에서 데이터 가져오기
        if filter_type == 'menu':
            # 메뉴판 인식 기록만 조회
            menu_records = list(db.menu_recognitions.find(combined_filter).sort('timestamp', -1).skip((page - 1) * per_page).limit(per_page))
            records = menu_records
            total_records = db.menu_recognitions.count_documents(combined_filter)
        elif filter_type == 'food':
            # 음식 인식 기록만 조회
            food_records = list(db.recognitions.find(combined_filter).sort('timestamp', -1).skip((page - 1) * per_page).limit(per_page))
            records = food_records
            total_records = db.recognitions.count_documents(combined_filter)
        else:
            # 모든 인식 기록을 통합하여 조회 (타임스탬프 기준 정렬)
            food_records = list(db.recognitions.find(combined_filter).sort('timestamp', -1))
            menu_records = list(db.menu_recognitions.find(combined_filter).sort('timestamp', -1))
            
            # 두 컬렉션의 레코드를 타임스탬프로 통합하여 정렬
            all_records = food_records + menu_records
            all_records.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # 페이지네이션 적용
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            records = all_records[start_index:end_index] if start_index < len(all_records) else []
            total_records = len(all_records)
        
        # 각 레코드에 타입 정보 추가
        for record in records:
            if 'detected_foods' in record:
                record['type'] = 'food'
            else:
                record['type'] = 'menu'
            
            # 이미지 URL 생성
            if 'image_filename' in record:
                record['image_url'] = url_for('static', filename=f'uploads/{record["image_filename"]}')
            elif 'image_path' in record:
                image_filename = os.path.basename(record['image_path'])
                record['image_url'] = url_for('static', filename=f'uploads/{image_filename}')
            
            # 타임스탬프 포맷팅
            if 'timestamp' in record:
                record['formatted_timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M')
        
        # 음식 인식 기록에 음식 정보 추가
        for record in records:
            if record['type'] == 'food' and 'detected_foods' in record and record['detected_foods']:
                # 이미 음식 세부 정보가 저장되어 있는지 확인
                if not any('nameKo' in food for food in record['detected_foods']):
                    for i, food_data in enumerate(record['detected_foods']):
                        food_name = food_data['food_name']
                        food_info = get_food_info(food_name)
                        if food_info:
                            # ObjectId 제거
                            if '_id' in food_info:
                                food_info.pop('_id')
                            
                            # 기존 정보에 음식 세부 정보 추가
                            record['detected_foods'][i].update({
                                'nameKo': food_info.get('nameKo', food_name),
                                'nameEn': food_info.get('nameEn', food_name),
                                'allergens': food_info.get('allergens', []),
                                'vegetarianStatus': food_info.get('vegetarianStatus', '알 수 없음')
                            })
        
        # 페이지네이션 정보
        total_pages = (total_records + per_page - 1) // per_page
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
        
        return render_template('history.html', 
                              active_page='history', 
                              history=records, 
                              pagination=pagination, 
                              filter_type=filter_type,
                              search_query=search_query)
    except Exception as e:
        logger.error(f"기록 조회 중 오류 발생: {e}")
        flash('인식 기록을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

@history_bp.route('/food')
def food_history():
    """음식 인식 기록 페이지"""
    try:
        # URL 파라미터를 그대로 전달하되 type만 'food'로 고정
        args = request.args.copy()
        args['type'] = 'food'
        return redirect(url_for('history.index', **args))
    except Exception as e:
        logger.error(f"음식 인식 기록 조회 중 오류 발생: {e}")
        flash('음식 인식 기록을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

@history_bp.route('/menu')
def menu_history():
    """메뉴판 인식 기록 페이지"""
    try:
        # URL 파라미터를 그대로 전달하되 type만 'menu'로 고정
        args = request.args.copy()
        args['type'] = 'menu'
        return redirect(url_for('history.index', **args))
    except Exception as e:
        logger.error(f"메뉴판 인식 기록 조회 중 오류 발생: {e}")
        flash('메뉴판 인식 기록을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('main.index'))

@history_bp.route('/detail/<record_id>')
def view_detail(record_id):
    """특정 인식 기록 상세 조회"""
    try:
        # MongoDB ObjectId로 변환
        try:
            record_object_id = ObjectId(record_id)
        except Exception as id_error:
            logger.error(f"Invalid ObjectId format: {id_error}")
            flash('잘못된 기록 ID입니다.', 'error')
            return redirect(url_for('history.index'))
        
        # 기록 ID를 사용하여 데이터베이스에서 기록 조회
        db = get_db()
        
        # 먼저 음식 인식 기록에서 검색
        record = None
        record_type = None
        
        try:
            record = db.recognitions.find_one({'_id': record_object_id})
            if record:
                record_type = 'food'
        except Exception as db_error:
            logger.error(f"Error retrieving food recognition: {db_error}")
        
        # 음식 인식 기록에 없으면 메뉴판 인식 기록에서 검색
        if not record:
            try:
                record = db.menu_recognitions.find_one({'_id': record_object_id})
                if record:
                    record_type = 'menu'
            except Exception as db_error:
                logger.error(f"Error retrieving menu recognition: {db_error}")
        
        if not record:
            flash('요청한 기록을 찾을 수 없습니다.', 'error')
            return redirect(url_for('history.index'))
        
        # 사용자 권한 확인 (자신의 기록만 볼 수 있도록)
        if 'user_id' in record and 'user_id' in session and record['user_id'] != session['user_id']:
            flash('접근 권한이 없습니다.', 'error')
            return redirect(url_for('history.index'))
        
        # 음식 인식 기록인 경우 세부 정보 추가
        if record_type == 'food' and 'detected_foods' in record and record['detected_foods']:
            for i, food in enumerate(record['detected_foods']):
                food_name = food['food_name']
                food_info = get_food_info(food_name)
                
                
                if food_info:
                    # MongoDB ObjectId는 JSON으로 직렬화할 수 없으므로 제거
                    if '_id' in food_info:
                        food_info.pop('_id')
                    # 기존 정보에 음식 세부 정보 추가
                    record['detected_foods'][i]['food_info'] = food_info
                    print(f"Food Name: {food_name}")
                    print(f"Food Info: {food_info}")
        
        # 이미지 URL 생성
        if 'image_path' in record:
            image_filename = record.get('image_filename') or os.path.basename(record['image_path'])
            record['image_url'] = url_for('static', filename=f'uploads/{image_filename}')
        
        return render_template('detail_history.html', 
                              active_page='history', 
                              record=record, 
                              record_type=record_type)
    except Exception as e:
        logger.error(f"기록 상세 조회 중 오류 발생: {e}")
        flash('기록 세부 정보를 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('history.index'))

@history_bp.route('/toggle_favorite/<record_id>', methods=['POST'])
def toggle_favorite(record_id):
    """즐겨찾기 토글"""
    try:
        # 로그인 상태 확인
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '로그인이 필요합니다.'}), 401
        
        # ObjectId 변환
        try:
            record_object_id = ObjectId(record_id)
        except Exception as id_error:
            logger.error(f"Invalid ObjectId format: {id_error}")
            return jsonify({'success': False, 'error': '잘못된 기록 ID입니다.'}), 400
        
        db = get_db()
        
        # 먼저 음식 인식 기록에서 검색
        record = None
        collection = None
        
        try:
            record = db.recognitions.find_one({'_id': record_object_id})
            if record:
                collection = db.recognitions
        except Exception as db_error:
            logger.error(f"Error retrieving food recognition: {db_error}")
        
        # 음식 인식 기록에 없으면 메뉴판 인식 기록에서 검색
        if not record:
            try:
                record = db.menu_recognitions.find_one({'_id': record_object_id})
                if record:
                    collection = db.menu_recognitions
            except Exception as db_error:
                logger.error(f"Error retrieving menu recognition: {db_error}")
        
        if not record:
            return jsonify({'success': False, 'error': '기록을 찾을 수 없습니다.'}), 404
        
        # 사용자 권한 확인
        if 'user_id' in record and record['user_id'] != session['user_id']:
            return jsonify({'success': False, 'error': '접근 권한이 없습니다.'}), 403
        
        # 현재 즐겨찾기 상태 확인 및 토글
        is_favorite = record.get('is_favorite', False)
        
        # 즐겨찾기 상태 업데이트
        try:
            collection.update_one(
                {'_id': record_object_id},
                {'$set': {'is_favorite': not is_favorite}}
            )
        except Exception as update_error:
            logger.error(f"Error updating favorite status: {update_error}")
            return jsonify({'success': False, 'error': '즐겨찾기 업데이트 중 오류가 발생했습니다.'}), 500
        
        return jsonify({'success': True, 'is_favorite': not is_favorite})
        
    except Exception as e:
        logger.error(f"즐겨찾기 토글 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@history_bp.route('/delete/<record_id>', methods=['POST'])
def delete_record(record_id):
    """특정 인식 기록 삭제"""
    try:
        # 로그인 상태 확인 (로그인한 사용자만 삭제 가능)
        if 'user_id' not in session:
            flash('기록을 삭제하려면 로그인이 필요합니다.', 'error')
            return redirect(url_for('history.index'))
        
        # MongoDB ObjectId로 변환
        try:
            record_object_id = ObjectId(record_id)
        except Exception as id_error:
            logger.error(f"Invalid ObjectId format: {id_error}")
            flash('잘못된 기록 ID입니다.', 'error')
            return redirect(url_for('history.index'))
        
        db = get_db()
        
        # 먼저 음식 인식 기록에서 검색
        record = None
        collection = None
        
        try:
            record = db.recognitions.find_one({'_id': record_object_id})
            if record:
                collection = db.recognitions
        except Exception as db_error:
            logger.error(f"Error retrieving food recognition: {db_error}")
        
        # 음식 인식 기록에 없으면 메뉴판 인식 기록에서 검색
        if not record:
            try:
                record = db.menu_recognitions.find_one({'_id': record_object_id})
                if record:
                    collection = db.menu_recognitions
            except Exception as db_error:
                logger.error(f"Error retrieving menu recognition: {db_error}")
        
        if not record:
            flash('요청한 기록을 찾을 수 없습니다.', 'error')
            return redirect(url_for('history.index'))
        
        # 사용자 ID 확인 (자신의 기록만 삭제 가능)
        if 'user_id' in record and record['user_id'] != session['user_id']:
            flash('다른 사용자의 기록은 삭제할 수 없습니다.', 'error')
            return redirect(url_for('history.index'))
        
        # 기록 삭제
        try:
            collection.delete_one({'_id': record_object_id})
        except Exception as delete_error:
            logger.error(f"Error deleting record: {delete_error}")
            flash('기록 삭제 중 오류가 발생했습니다.', 'error')
            return redirect(url_for('history.index'))
        
        flash('기록이 성공적으로 삭제되었습니다.', 'success')
        return redirect(url_for('history.index'))
        
    except Exception as e:
        logger.error(f"기록 삭제 중 오류 발생: {e}")
        flash('기록 삭제 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('history.index'))