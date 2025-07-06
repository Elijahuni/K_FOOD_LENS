
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

class FoodRecommender:
    def __init__(self, db):
        self.db = db
        self.foods_collection = db['foods']
        
    def calculate_taste_similarity(self, food1, food2):
        """맛 특성을 기반으로 유사도 계산"""
        taste1 = food1.get('taste', {})
        taste2 = food2.get('taste', {})
        
        # 맛 프로필 벡터 생성
        vector1 = [
            taste1.get('spiciness', 0),
            taste1.get('sweetness', 0),
            taste1.get('saltiness', 0),
            taste1.get('sourness', 0),
            taste1.get('umami', 0)
        ]
        vector2 = [
            taste2.get('spiciness', 0),
            taste2.get('sweetness', 0),
            taste2.get('saltiness', 0),
            taste2.get('sourness', 0),
            taste2.get('umami', 0)
        ]
        
        # 코사인 유사도 계산
        similarity = cosine_similarity([vector1], [vector2])[0][0]
        
        # 맛 프로필 태그 유사도 계산
        profile1 = set(taste1.get('profile', []))
        profile2 = set(taste2.get('profile', []))
        if profile1 and profile2:
            profile_similarity = len(profile1 & profile2) / len(profile1 | profile2)
            similarity = (similarity + profile_similarity) / 2
            
        return similarity
    
    def calculate_ingredient_similarity(self, food1, food2):
        """재료를 기반으로 유사도 계산"""
        ingredients1 = food1.get('ingredients', {})
        ingredients2 = food2.get('ingredients', {})
        
        # 모든 재료를 하나의 집합으로 결합
        all_ingredients1 = set()
        for category in ['main', 'sub', 'sauce']:
            all_ingredients1.update(ingredients1.get(category, []))
            
        all_ingredients2 = set()
        for category in ['main', 'sub', 'sauce']:
            all_ingredients2.update(ingredients2.get(category, []))
            
        if not all_ingredients1 or not all_ingredients2:
            return 0.0
            
        # 자카드 유사도 계산
        intersection = len(all_ingredients1 & all_ingredients2)
        union = len(all_ingredients1 | all_ingredients2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_cooking_similarity(self, food1, food2):
        """조리법을 기반으로 유사도 계산"""
        cooking1 = food1.get('cookingMethod', {})
        cooking2 = food2.get('cookingMethod', {})
        
        methods1 = set()
        methods1.add(cooking1.get('primary', ''))
        methods1.update(cooking1.get('secondary', []))
        
        methods2 = set()
        methods2.add(cooking2.get('primary', ''))
        methods2.update(cooking2.get('secondary', []))
        
        if not methods1 or not methods2:
            return 0.0
            
        # 자카드 유사도 계산
        intersection = len(methods1 & methods2)
        union = len(methods1 | methods2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_region_similarity(self, food1, food2):
        """지역을 기반으로 유사도 계산"""
        region1 = food1.get('region', {})
        region2 = food2.get('region', {})
        
        if not region1 or not region2:
            return 0.0
            
        similarity = 0.0
        
        # 발상지가 같은 경우
        if region1.get('origin') == region2.get('origin'):
            similarity += 0.5
            
        # 인기 지역 교집합
        popular1 = set(region1.get('popular', []))
        popular2 = set(region2.get('popular', []))
        if popular1 and popular2:
            intersection = len(popular1 & popular2)
            union = len(popular1 | popular2)
            similarity += 0.3 * (intersection / union if union > 0 else 0)
            
        # 전통음식 여부
        if region1.get('traditional') == region2.get('traditional'):
            similarity += 0.2
            
        return min(similarity, 1.0)
    
    def get_food_recommendations(self, food_id, top_n=5):
        """특정 음식과 유사한 음식 추천"""
        target_food = self.foods_collection.find_one({'dishId': food_id})
        if not target_food:
            return []
            
        recommendations = []
        all_foods = list(self.foods_collection.find({'dishId': {'$ne': food_id}}))
        
        for food in all_foods:
            similarity_scores = {
                'taste': self.calculate_taste_similarity(target_food, food),
                'ingredient': self.calculate_ingredient_similarity(target_food, food),
                'cooking': self.calculate_cooking_similarity(target_food, food),
                'region': self.calculate_region_similarity(target_food, food)
            }
            
            # 종합 유사도 계산 (가중 평균)
            total_similarity = (
                similarity_scores['taste'] * 0.4 +
                similarity_scores['ingredient'] * 0.3 +
                similarity_scores['cooking'] * 0.2 +
                similarity_scores['region'] * 0.1
            )
            
            recommendations.append({
                'dishId': food.get('dishId'),
                'name': food.get('nameKo'),
                'similarity': total_similarity,
                'details': similarity_scores
            })
        
        # 유사도 기준으로 정렬
        recommendations.sort(key=lambda x: x['similarity'], reverse=True)
        
        return recommendations[:top_n]
    
    def get_recommendations_by_criteria(self, food_id, criteria='taste', top_n=5):
        """특정 기준(맛, 재료, 조리법)에 따른 유사 음식 추천"""
        target_food = self.foods_collection.find_one({'dishId': food_id})
        if not target_food:
            return []
            
        recommendations = []
        all_foods = list(self.foods_collection.find({'dishId': {'$ne': food_id}}))
        
        for food in all_foods:
            if criteria == 'taste':
                similarity = self.calculate_taste_similarity(target_food, food)
            elif criteria == 'ingredient':
                similarity = self.calculate_ingredient_similarity(target_food, food)
            elif criteria == 'cooking':
                similarity = self.calculate_cooking_similarity(target_food, food)
            elif criteria == 'region':
                similarity = self.calculate_region_similarity(target_food, food)
            else:
                similarity = 0.0
                
            recommendations.append({
                'dishId': food.get('dishId'),
                'name': food.get('nameKo'),
                'similarity': similarity
            })
        
        # 유사도 기준으로 정렬
        recommendations.sort(key=lambda x: x['similarity'], reverse=True)
        
        return recommendations[:top_n]
    
    def update_similar_foods_in_db(self):
        """모든 음식에 대해 유사 음식 데이터 업데이트"""
        all_foods = list(self.foods_collection.find())
        total = len(all_foods)
        
        for i, food in enumerate(all_foods):
            food_id = food.get('dishId')
            if not food_id:
                continue
                
            similar_by_taste = self.get_recommendations_by_criteria(food_id, 'taste', 3)
            similar_by_ingredient = self.get_recommendations_by_criteria(food_id, 'ingredient', 3)
            similar_by_cooking = self.get_recommendations_by_criteria(food_id, 'cooking', 3)
            
            similar_foods = {
                'taste': similar_by_taste,
                'ingredient': similar_by_ingredient,
                'cooking': similar_by_cooking
            }
            
            self.foods_collection.update_one(
                {'dishId': food_id},
                {'$set': {'similarFoods': similar_foods}}
            )
            
            print(f"업데이트 완료: {i+1}/{total} - {food.get('nameKo')}")
        
        print("모든 음식의 유사 음식 데이터 업데이트 완료")
