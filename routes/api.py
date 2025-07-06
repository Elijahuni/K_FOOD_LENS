# routes/api.py
import logging
from flask import Blueprint, jsonify, request

from modules.database import get_food_info, get_db
from modules.recommender import get_recommender

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/food/<food_name>')
def get_food_api(food_name):
    """특정 음식 정보 조회 API"""
    try:
        food_info = get_food_info(food_name)
        if food_info:
            # MongoDB ObjectId는 JSON으로 직렬화할 수 없으므로 제거
            if '_id' in food_info:
                food_info.pop('_id')
            return jsonify({'success': True, 'food': food_info})
        else:
            return jsonify({'success': False, 'error': '음식 정보를 찾을 수 없습니다.'}), 404
    except Exception as e:
        logger.error(f"API 요청 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/food', methods=['POST'])
def add_food_api():
    """새로운 음식 정보 추가 API"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': '요청 데이터가 없습니다.'}), 400
        
        # 필수 필드 검증
        required_fields = ['nameKo', 'nameEn', 'dishId']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'필수 필드 누락: {field}'}), 400
        
        # 중복 확인
        db = get_db()
        existing = db.foods.find_one({'dishId': data['dishId']})
        if existing:
            return jsonify({'success': False, 'error': f'이미 존재하는 dishId: {data["dishId"]}'}), 409
        
        # 데이터 삽입
        result = db.foods.insert_one(data)
        return jsonify({
            'success': True, 
            'message': '음식 정보가 추가되었습니다.',
            'id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        logger.error(f"음식 정보 추가 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/recommendations/<int:food_id>')
def get_recommendations(food_id):
    """유사 음식 추천 API"""
    try:
        recommender = get_recommender()
        if not recommender:
            return jsonify({'success': False, 'error': '추천 시스템이 초기화되지 않았습니다.'}), 500
            
        top_n = request.args.get('limit', default=3, type=int)
        recommendations = recommender.get_food_recommendations(food_id, top_n=top_n)
        
        return jsonify({'success': True, 'recommendations': recommendations})
    except Exception as e:
        logger.error(f"음식 추천 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/recommendations/<int:food_id>/<criteria>')
def get_recommendations_by_criteria(food_id, criteria):
    """특정 기준에 따른 음식 추천 API"""
    try:
        recommender = get_recommender()
        if not recommender:
            return jsonify({'success': False, 'error': '추천 시스템이 초기화되지 않았습니다.'}), 500
            
        if criteria not in ['taste', 'ingredient', 'cooking']:
            return jsonify({'success': False, 'error': f'지원되지 않는 추천 기준: {criteria}'}), 400
            
        top_n = request.args.get('limit', default=3, type=int)
        recommendations = recommender.get_recommendations_by_criteria(food_id, criteria, top_n=top_n)
        
        return jsonify({'success': True, 'recommendations': recommendations})
    except Exception as e:
        logger.error(f"음식 추천 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/update_similar_foods', methods=['POST'])
def update_similar_foods():
    """전체 음식의 similarFoods 필드를 업데이트하는 API"""
    try:
        recommender = get_recommender()
        if not recommender:
            return jsonify({'success': False, 'error': '추천 시스템이 초기화되지 않았습니다.'}), 500
            
        result = recommender.update_similar_foods_in_db()
        
        if result.get('success', False):
            return jsonify({
                'success': True, 
                'message': 'similarFoods 필드 업데이트 완료',
                'updated_count': result.get('updated_count', 0)
            })
        else:
            return jsonify({'success': False, 'error': result.get('error', '알 수 없는 오류')}), 500
    except Exception as e:
        logger.error(f"similarFoods 필드 업데이트 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/foods')
def get_foods_api():
    """음식 목록 조회 API"""
    try:
        db = get_db()
        
        # 쿼리 파라미터
        limit = request.args.get('limit', default=20, type=int)
        skip = request.args.get('skip', default=0, type=int)
        sort_by = request.args.get('sort', default='nameKo')
        sort_dir = request.args.get('dir', default='asc')
        
        # 정렬 방향 설정
        sort_direction = 1 if sort_dir == 'asc' else -1
        
        # 쿼리 실행
        query = {}
        projection = {'_id': 0}  # _id 필드 제외
        
        # 카테고리 필터링
        category = request.args.get('category')
        if category:
            query['category'] = category
        
        # 채식 여부 필터링
        vegetarian = request.args.get('vegetarian')
        if vegetarian:
            query['vegetarianStatus'] = vegetarian
        
        # 알레르기 필터링 (제외할 알레르기 성분)
        allergens = request.args.getlist('allergen')
        if allergens:
            query['allergens'] = {'$nin': allergens}
        
        foods = list(db.foods.find(query, projection)
                    .sort(sort_by, sort_direction)
                    .skip(skip)
                    .limit(limit))
        
        # 총 개수 조회
        total_count = db.foods.count_documents(query)
        
        return jsonify({
            'success': True,
            'foods': foods,
            'total': total_count,
            'skip': skip,
            'limit': limit
        })
    except Exception as e:
        logger.error(f"음식 목록 조회 중 오류 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500