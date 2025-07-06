# performance_test.py
import time
import logging
from flask import Flask
from modules.recommender import FoodRecommender
from modules.database import get_db
from modules.cache_manager import get_cache_stats, invalidate_cache

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 테스트 앱 생성
app = Flask(__name__)
app.config.from_object('config.Config')

# 테스트 함수
def test_recommendation_performance():
    with app.app_context():
        # 데이터베이스 연결
        db = get_db()
        
        # 추천 시스템 인스턴스 생성
        recommender = FoodRecommender(db)
        
        # 초기화
        recommender.initialize()
        
        # 테스트할 음식 ID 선택
        food_ids = [1, 5, 10, 15, 20]  # 예제 ID
        
        # 캐시 비우기
        invalidate_cache('recommendation_*')
        
        # 캐시 없이 처음 실행 (콜드 스타트)
        logger.info("캐시 없이 첫 번째 실행 (콜드 스타트)...")
        cold_start_times = []
        
        for food_id in food_ids:
            start_time = time.time()
            results = recommender.get_food_recommendations(food_id, top_n=5)
            elapsed = time.time() - start_time
            cold_start_times.append(elapsed)
            logger.info(f"음식 ID {food_id} 추천 계산: {elapsed:.4f}초, {len(results)}개 결과")
        
        avg_cold = sum(cold_start_times) / len(cold_start_times)
        logger.info(f"콜드 스타트 평균 시간: {avg_cold:.4f}초")
        
        # 캐시된 상태에서 다시 실행 (웜 스타트)
        logger.info("\n캐시된 상태에서 다시 실행 (웜 스타트)...")
        warm_start_times = []
        
        for food_id in food_ids:
            start_time = time.time()
            results = recommender.get_food_recommendations(food_id, top_n=5)
            elapsed = time.time() - start_time
            warm_start_times.append(elapsed)
            logger.info(f"음식 ID {food_id} 추천 검색: {elapsed:.4f}초, {len(results)}개 결과")
        
        avg_warm = sum(warm_start_times) / len(warm_start_times)
        logger.info(f"웜 스타트 평균 시간: {avg_warm:.4f}초")
        
        # 성능 향상 계산
        improvement = ((avg_cold - avg_warm) / avg_cold) * 100
        logger.info(f"캐싱 성능 향상: {improvement:.2f}%")
        
        # 캐시 통계 확인
        cache_stats = get_cache_stats()
        logger.info(f"캐시 통계: {cache_stats}")
        
        # 배치 유사도 계산 테스트
        logger.info("\n배치 유사도 계산 테스트...")
        all_foods = list(db.foods.find({}))
        all_food_ids = [food.get('dishId') for food in all_foods[:50] if food.get('dishId')]
        
        # 개별 계산 시간 측정
        start_time = time.time()
        individual_results = {}
        for target_id in food_ids:
            for compare_id in all_food_ids:
                if target_id != compare_id:
                    sim = recommender._calculate_taste_similarity_cached(target_id, compare_id)
                    if sim > 0:
                        if target_id not in individual_results:
                            individual_results[target_id] = {}
                        individual_results[target_id][compare_id] = sim
        
        individual_time = time.time() - start_time
        logger.info(f"개별 유사도 계산 시간: {individual_time:.4f}초")
        
        # 배치 계산 시간 측정
        start_time = time.time()
        batch_results = {}
        for target_id in food_ids:
            batch_results[target_id] = recommender.calculate_batch_similarities(target_id, all_food_ids, 'taste')
        
        batch_time = time.time() - start_time
        logger.info(f"배치 유사도 계산 시간: {batch_time:.4f}초")
        
        # 배치 처리 성능 향상 계산
        batch_improvement = ((individual_time - batch_time) / individual_time) * 100
        logger.info(f"배치 처리 성능 향상: {batch_improvement:.2f}%")

if __name__ == "__main__":
    test_recommendation_performance()