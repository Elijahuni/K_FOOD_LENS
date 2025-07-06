# modules/recommender.py - 성능 최적화 버전
import numpy as np
import logging
from functools import lru_cache
from flask import current_app, g
from modules.database import get_db

logger = logging.getLogger(__name__)

# 모듈 레벨 변수로 추천 시스템 인스턴스와 MongoDB 클라이언트 저장
_recommender_instance = None
_mongo_client = None

class FoodRecommender:
    """유사 음식 추천 시스템 클래스 - 성능 최적화 버전"""
    
    def __init__(self, db):
        self.db = db
        self.taste_attributes = ['sweet', 'sour', 'salty', 'bitter', 'umami', 'spicy']
        self.taste_vectors = {}  # 사전 계산된 맛 벡터
        self.ingredient_sets = {}  # 사전 계산된 재료 세트
        self.cooking_info = {}  # 사전 계산된 조리법 정보
        self.initialized = False
        logger.info("음식 추천 시스템 초기화")
    
    def initialize(self):
        """추천 시스템 초기화 및 사전 계산"""
        if self.initialized:
            return True
            
        try:
            # 전체 음식 데이터 로드
            all_foods = list(self.db.foods.find())
            logger.info(f"총 {len(all_foods)}개 음식 데이터 로드 완료")
            
            # 맛 벡터 사전 계산
            for food in all_foods:
                food_id = food.get('dishId')
                if not food_id:
                    continue
                    
                # 맛 벡터 계산
                taste_data = food.get('taste', {})
                taste_vector = np.array([taste_data.get(attr, 0) for attr in self.taste_attributes], dtype=np.float32)
                self.taste_vectors[food_id] = taste_vector
                
                # 재료 세트 계산
                ingredients = food.get('ingredients', [])
                if ingredients:
                    self.ingredient_sets[food_id] = set(ingredients)
                
                # 조리법 정보 저장
                cooking = food.get('cooking', {})
                if cooking:
                    self.cooking_info[food_id] = cooking
            
            # 맛 벡터 정규화 (길이가 0이 아닌 경우만)
            for food_id, vector in self.taste_vectors.items():
                norm = np.linalg.norm(vector)
                if norm > 0:
                    self.taste_vectors[food_id] = vector / norm
            
            self.initialized = True
            logger.info("추천 시스템 데이터 사전 계산 완료")
            return True
        except Exception as e:
            logger.error(f"추천 시스템 초기화 중 오류: {e}")
            return False
    
    def get_food_recommendations(self, food_id, top_n=3):
        """특정 음식과 유사한 음식을 추천합니다."""
        try:
            # 시스템 초기화 확인
            if not self.initialized:
                self.initialize()
            
            # 대상 음식 정보 가져오기
            target_food = self.db.foods.find_one({"dishId": food_id})
            if not target_food:
                logger.warning(f"음식 ID {food_id}에 대한 정보를 찾을 수 없습니다.")
                return []
            
            # 이미 계산된 유사 음식 정보가 있는지 확인
            if 'similarFoods' in target_food and target_food['similarFoods']:
                logger.info(f"미리 계산된 유사 음식 정보 사용: {food_id}")
                similar_foods = []
                
                # 카테고리별 추천 통합
                categories = ['taste', 'ingredient', 'cooking']
                for category in categories:
                    if category in target_food['similarFoods']:
                        for similar in target_food['similarFoods'][category][:top_n]:
                            similar_food = self.db.foods.find_one({"dishId": similar['dishId']})
                            if similar_food:
                                similar_foods.append({
                                    'dishId': similar_food['dishId'],
                                    'nameKo': similar_food['nameKo'],
                                    'nameEn': similar_food['nameEn'],
                                    'category': category,
                                    'similarity': similar['similarity']
                                })
                
                return similar_foods
            
            # 실시간 계산 (fallback) - 최적화된 계산 사용
            all_foods = list(self.db.foods.find())
            similar_foods = []
            
            # 타겟 음식의 특성 가져오기
            target_taste_vector = self.taste_vectors.get(food_id)
            target_ingredients = self.ingredient_sets.get(food_id, set())
            
            for food in all_foods:
                compare_id = food.get('dishId')
                if not compare_id or compare_id == food_id:
                    continue
                
                # 유사도 계산 - 벡터화된 연산 사용
                taste_similarity = 0.0
                ingredient_similarity = 0.0
                
                # 맛 유사도 (코사인 유사도)
                if target_taste_vector is not None and compare_id in self.taste_vectors:
                    # 정규화된 벡터 간의 내적은 코사인 유사도와 동일
                    taste_similarity = float(np.dot(target_taste_vector, self.taste_vectors[compare_id]))
                
                # 재료 유사도 (자카드 유사도)
                if target_ingredients and compare_id in self.ingredient_sets:
                    compare_ingredients = self.ingredient_sets[compare_id]
                    intersection = len(target_ingredients.intersection(compare_ingredients))
                    union = len(target_ingredients.union(compare_ingredients))
                    if union > 0:
                        ingredient_similarity = intersection / union
                
                # 종합 유사도 (가중치 적용)
                similarity = (taste_similarity * 0.7) + (ingredient_similarity * 0.3)
                
                similar_foods.append({
                    'dishId': food['dishId'],
                    'nameKo': food['nameKo'],
                    'nameEn': food['nameEn'],
                    'similarity': similarity
                })
            
            # 유사도 기준 정렬 및 상위 N개 선택
            similar_foods.sort(key=lambda x: x['similarity'], reverse=True)
            result = similar_foods[:top_n]
            
            return result
            
        except Exception as e:
            logger.error(f"음식 추천 중 오류 발생: {e}")
            return []
    
    def get_recommendations_by_criteria(self, food_id, criteria, top_n=3):
        """특정 기준에 따른 음식 추천을 반환합니다."""
        try:
            # 대상 음식 정보 가져오기
            target_food = self.db.foods.find_one({"dishId": food_id})
            if not target_food:
                logger.warning(f"음식 ID {food_id}에 대한 정보를 찾을 수 없습니다.")
                return []
            
            # 이미 계산된 유사 음식 정보가 있는지 확인
            if ('similarFoods' in target_food and 
                target_food['similarFoods'] and 
                criteria in target_food['similarFoods']):
                
                logger.info(f"미리 계산된 {criteria} 기준 유사 음식 정보 사용: {food_id}")
                similar_items = target_food['similarFoods'][criteria][:top_n]
                
                # 기본 정보 추가
                result = []
                for item in similar_items:
                    similar_food = self.db.foods.find_one({"dishId": item['dishId']})
                    if similar_food:
                        result.append({
                            'dishId': similar_food['dishId'],
                            'nameKo': similar_food['nameKo'],
                            'nameEn': similar_food['nameEn'],
                            'category': criteria,
                            'similarity': item['similarity']
                        })
                
                return result
            
            # 실시간 계산 (fallback)
            if criteria == 'taste':
                return self._get_taste_recommendations(target_food, top_n)
            elif criteria == 'ingredient':
                return self._get_ingredient_recommendations(target_food, top_n)
            elif criteria == 'cooking':
                return self._get_cooking_recommendations(target_food, top_n)
            else:
                logger.warning(f"알 수 없는 추천 기준: {criteria}")
                return []
                
        except Exception as e:
            logger.error(f"{criteria} 기준 추천 중 오류 발생: {e}")
            return []
    
    @lru_cache(maxsize=128)  # 파이썬 내장 메모이제이션 사용
    def _calculate_taste_similarity_cached(self, food1_id, food2_id):
        """두 음식의 맛 유사도를 계산하는 캐시된 메서드 (ID 기반)"""
        if food1_id in self.taste_vectors and food2_id in self.taste_vectors:
            # 사전 계산된 정규화 벡터 사용
            vec1 = self.taste_vectors[food1_id]
            vec2 = self.taste_vectors[food2_id]
            return float(np.dot(vec1, vec2))
        return 0.0
    
    def _calculate_taste_similarity(self, taste1, taste2):
        """두 음식의 맛 유사도를 계산합니다. (딕셔너리 기반)"""
        try:
            if not taste1 or not taste2:
                return 0.0
            
            # 맛 벡터 생성
            vec1 = np.array([taste1.get(attr, 0) for attr in self.taste_attributes], dtype=np.float32)
            vec2 = np.array([taste2.get(attr, 0) for attr in self.taste_attributes], dtype=np.float32)
            
            # 벡터 정규화
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # 정규화된 벡터
            vec1_normalized = vec1 / norm1
            vec2_normalized = vec2 / norm2
            
            # 코사인 유사도 계산 (벡터화된 연산)
            similarity = np.dot(vec1_normalized, vec2_normalized)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"맛 유사도 계산 중 오류: {e}")
            return 0.0
    
    @lru_cache(maxsize=128)
    def _calculate_ingredient_similarity_cached(self, food1_id, food2_id):
        """두 음식의 재료 유사도를 계산하는 캐시된 메서드 (ID 기반)"""
        if food1_id in self.ingredient_sets and food2_id in self.ingredient_sets:
            set1 = self.ingredient_sets[food1_id]
            set2 = self.ingredient_sets[food2_id]
            
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            if union == 0:
                return 0.0
            
            return intersection / union
        return 0.0
    
    def _calculate_ingredient_similarity(self, ingredients1, ingredients2):
        """두 음식의 재료 유사도를 계산합니다."""
        try:
            if not ingredients1 or not ingredients2:
                return 0.0
            
            # 자카드 유사도 계산
            set1 = set(ingredients1)
            set2 = set(ingredients2)
            
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            if union == 0:
                return 0.0
            
            return intersection / union
            
        except Exception as e:
            logger.error(f"재료 유사도 계산 중 오류: {e}")
            return 0.0
    
    def _calculate_cooking_similarity(self, cooking1, cooking2):
        """두 음식의 조리법 유사도를 계산합니다."""
        try:
            if not cooking1 or not cooking2:
                return 0.0
                
            # 조리법 카테고리 비교
            if cooking1.get('category') == cooking2.get('category'):
                return 1.0
            
            # 조리 시간 유사도 계산
            time1 = cooking1.get('time', 0)
            time2 = cooking2.get('time', 0)
            
            if time1 == 0 or time2 == 0:
                time_similarity = 0.0
            else:
                time_diff = abs(time1 - time2)
                max_time = max(time1, time2)
                time_similarity = 1.0 - (time_diff / max_time)
            
            # 조리 난이도 유사도 계산
            difficulty1 = cooking1.get('difficulty', 0)
            difficulty2 = cooking2.get('difficulty', 0)
            
            difficulty_similarity = 1.0 - (abs(difficulty1 - difficulty2) / 5.0)
            
            # 종합 유사도 계산
            similarity = (time_similarity * 0.4) + (difficulty_similarity * 0.6)
            return similarity
            
        except Exception as e:
            logger.error(f"조리법 유사도 계산 중 오류: {e}")
            return 0.0
    
    # batch 계산 방식 추가 (여러 음식 한번에 비교)
    def calculate_batch_similarities(self, target_food_id, food_ids, criteria='taste'):
        """여러 음식에 대한 유사도를 한번에 계산합니다."""
        try:
            # 시스템 초기화 확인
            if not self.initialized:
                self.initialize()
            
            results = {}
            
            if criteria == 'taste':
                # 타겟 음식의 맛 벡터 가져오기
                if target_food_id not in self.taste_vectors:
                    return {}
                
                target_vector = self.taste_vectors[target_food_id]
                
                # 벡터화된 방식으로 한 번에 계산
                similarities = {}
                for food_id in food_ids:
                    if food_id in self.taste_vectors:
                        similarities[food_id] = float(np.dot(target_vector, self.taste_vectors[food_id]))
                
                return similarities
                
            elif criteria == 'ingredient':
                # 타겟 음식의 재료 세트 가져오기
                if target_food_id not in self.ingredient_sets:
                    return {}
                
                target_ingredients = self.ingredient_sets[target_food_id]
                
                # 각 음식에 대해 자카드 유사도 계산
                similarities = {}
                for food_id in food_ids:
                    if food_id in self.ingredient_sets:
                        # 캐시된 메서드 활용
                        similarities[food_id] = self._calculate_ingredient_similarity_cached(
                            target_food_id, food_id
                        )
                
                return similarities
                
            return {}
        except Exception as e:
            logger.error(f"배치 유사도 계산 중 오류: {e}")
            return {}
    
    def _get_taste_recommendations(self, target_food, top_n=3, minimal=False):
        """맛 기준 추천 계산"""
        try:
            target_taste = target_food.get('taste', {})
            food_id = target_food['dishId']
            
            # 시스템 초기화 확인
            if not self.initialized:
                self.initialize()
            
            # 맛 벡터가 없으면 DB에서 전체 음식 가져오기
            all_foods = list(self.db.foods.find())
            similar_foods = []
            
            for food in all_foods:
                compare_id = food.get('dishId')
                if not compare_id or compare_id == food_id:
                    continue
                
                # 캐시된 유사도 계산 사용
                similarity = 0
                if food_id in self.taste_vectors and compare_id in self.taste_vectors:
                    similarity = self._calculate_taste_similarity_cached(food_id, compare_id)
                else:
                    # 캐시 미스 시 직접 계산
                    similarity = self._calculate_taste_similarity(target_taste, food.get('taste', {}))
                
                if minimal:
                    similar_foods.append({
                        'dishId': food['dishId'],
                        'similarity': similarity
                    })
                else:
                    similar_foods.append({
                        'dishId': food['dishId'],
                        'nameKo': food['nameKo'],
                        'nameEn': food['nameEn'],
                        'category': 'taste',
                        'similarity': similarity
                    })
            
            similar_foods.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_foods[:top_n]
            
        except Exception as e:
            logger.error(f"맛 기준 추천 중 오류: {e}")
            return []
    
    def _get_ingredient_recommendations(self, target_food, top_n=3, minimal=False):
        """재료 기준 추천 계산"""
        try:
            target_ingredients = target_food.get('ingredients', [])
            food_id = target_food['dishId']
            
            # 시스템 초기화 확인
            if not self.initialized:
                self.initialize()
            
            all_foods = list(self.db.foods.find())
            similar_foods = []
            
            for food in all_foods:
                compare_id = food.get('dishId')
                if not compare_id or compare_id == food_id:
                    continue
                
                # 유사도 계산 - 가능하면 캐시 사용
                similarity = 0
                if food_id in self.ingredient_sets and compare_id in self.ingredient_sets:
                    similarity = self._calculate_ingredient_similarity_cached(food_id, compare_id)
                else:
                    similarity = self._calculate_ingredient_similarity(
                        target_ingredients, food.get('ingredients', [])
                    )
                
                if minimal:
                    similar_foods.append({
                        'dishId': food['dishId'],
                        'similarity': similarity
                    })
                else:
                    similar_foods.append({
                        'dishId': food['dishId'],
                        'nameKo': food['nameKo'],
                        'nameEn': food['nameEn'],
                        'category': 'ingredient',
                        'similarity': similarity
                    })
            
            similar_foods.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_foods[:top_n]
            
        except Exception as e:
            logger.error(f"재료 기준 추천 중 오류: {e}")
            return []
    
    def _get_cooking_recommendations(self, target_food, top_n=3, minimal=False):
        """조리법 기준 추천 계산"""
        try:
            target_cooking = target_food.get('cooking', {})
            food_id = target_food['dishId']
            
            all_foods = list(self.db.foods.find())
            similar_foods = []
            
            for food in all_foods:
                if food['dishId'] == food_id:
                    continue  # 자기 자신 제외
                
                similarity = self._calculate_cooking_similarity(
                    target_cooking, food.get('cooking', {})
                )
                
                if minimal:
                    similar_foods.append({
                        'dishId': food['dishId'],
                        'similarity': similarity
                    })
                else:
                    similar_foods.append({
                        'dishId': food['dishId'],
                        'nameKo': food['nameKo'],
                        'nameEn': food['nameEn'],
                        'category': 'cooking',
                        'similarity': similarity
                    })
            
            similar_foods.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_foods[:top_n]
            
        except Exception as e:
            logger.error(f"조리법 기준 추천 중 오류: {e}")
            return []
    
    def update_similar_foods_in_db(self):
        """모든 음식의 similarFoods 필드를 업데이트합니다."""
        # 시스템 초기화 확인
        if not self.initialized:
            self.initialize()
            
        try:
            all_foods = list(self.db.foods.find())
            food_ids = [food.get('dishId') for food in all_foods if food.get('dishId')]
            total_updated = 0
            
            # 음식 ID 목록
            batch_size = 25  # 한 번에 처리할 음식 수
            
            for i in range(0, len(all_foods), batch_size):
                batch_foods = all_foods[i:i+batch_size]
                
                for target_food in batch_foods:
                    food_id = target_food.get('dishId')
                    if not food_id:
                        continue
                    
                    # 맛 기준 유사도 배치 계산
                    taste_similarities = self.calculate_batch_similarities(
                        food_id, food_ids, 'taste'
                    )
                    
                    # 재료 기준 유사도 배치 계산
                    ingredient_similarities = self.calculate_batch_similarities(
                        food_id, food_ids, 'ingredient'
                    )
                    
                    # 유사도 결과 정렬 및 형식화
                    taste_results = []
                    for fid, sim in taste_similarities.items():
                        if fid != food_id and sim > 0:
                            taste_results.append({'dishId': fid, 'similarity': sim})
                    taste_results.sort(key=lambda x: x['similarity'], reverse=True)
                    
                    ingredient_results = []
                    for fid, sim in ingredient_similarities.items():
                        if fid != food_id and sim > 0:
                            ingredient_results.append({'dishId': fid, 'similarity': sim})
                    ingredient_results.sort(key=lambda x: x['similarity'], reverse=True)
                    
                    # 조리법 유사도는 기존 방식 사용
                    cooking_results = self._get_cooking_recommendations(target_food, top_n=5, minimal=True)
                    
                    # similarFoods 필드 업데이트
                    similar_foods = {
                        'taste': taste_results[:5],
                        'ingredient': ingredient_results[:5],
                        'cooking': cooking_results
                    }
                    
                    # DB 업데이트
                    update_result = self.db.foods.update_one(
                        {"dishId": food_id},
                        {"$set": {"similarFoods": similar_foods}}
                    )
                    
                    if update_result.modified_count > 0:
                        total_updated += 1
            
            # 메모이제이션 캐시 정리
            self._calculate_taste_similarity_cached.cache_clear()
            self._calculate_ingredient_similarity_cached.cache_clear()
            
            logger.info(f"총 {total_updated}/{len(all_foods)}개 음식의 유사 음식 정보가 업데이트되었습니다.")
            return {"success": True, "updated_count": total_updated}
            
        except Exception as e:
            logger.error(f"유사 음식 정보 업데이트 중 오류 발생: {e}")
            return {"success": False, "error": str(e)}

def get_fresh_db_connection():
    """새로운 MongoDB 연결을 생성합니다."""
    global _mongo_client
    
    # 기존 연결이 있다면 먼저 닫기
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception as e:
            logger.warning(f"MongoDB 연결 닫기 중 오류 발생: {e}")
    
    # 새 연결 생성
    try:
        from flask import current_app
        from pymongo import MongoClient
        
        mongo_uri = current_app.config['MONGO_URI']
        db_name = current_app.config['MONGO_DB']
        
        _mongo_client = MongoClient(mongo_uri)
        db = _mongo_client[db_name]
        logger.info(f"추천 시스템용 MongoDB 연결 생성 성공: {mongo_uri}")
        return db
    except Exception as e:
        logger.error(f"MongoDB 연결 생성 중 오류 발생: {e}")
        return None

def get_recommender():
    """추천 시스템을 가져옵니다. 필요시 재초기화합니다."""
    global _recommender_instance
    
    # 기존 인스턴스가 있으면 반환
    if _recommender_instance is not None:
        return _recommender_instance
    
    # 없으면 새로 초기화
    logger.info("추천 시스템 지연 초기화 시작")
    db = get_fresh_db_connection()
    if db is not None:
        _recommender_instance = FoodRecommender(db)
        # 초기화 실행
        _recommender_instance.initialize()
        logger.info("추천 시스템 지연 초기화 완료")
        return _recommender_instance
    else:
        logger.error("추천 시스템 초기화 실패: 데이터베이스 연결 오류")
        return None

def init_recommender(app):
    """추천 시스템을 초기화합니다."""
    global _recommender_instance
    
    try:
        # 애플리케이션 컨텍스트에서 설정 가져오기
        with app.app_context():
            db = get_fresh_db_connection()
            if db is not None:
                _recommender_instance = FoodRecommender(db)
                # 초기화 실행
                _recommender_instance.initialize()
                logger.info("음식 추천 시스템 초기화 완료")
                return True
            else:
                logger.error("추천 시스템 초기화 실패: 데이터베이스 연결 오류")
                return False
    except Exception as e:
        logger.error(f"음식 추천 시스템 초기화 중 오류 발생: {e}")
        _recommender_instance = None
        return False