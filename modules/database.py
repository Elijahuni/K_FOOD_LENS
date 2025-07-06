# modules/database.py
import json
import logging
from pymongo import MongoClient, DESCENDING
from flask import current_app, g, session
from datetime import datetime
from bson.objectid import ObjectId
import os

logger = logging.getLogger(__name__)

def get_db():
    """애플리케이션 컨텍스트에서 데이터베이스 연결을 가져옵니다."""
    if 'db' not in g:
        try:
            mongo_uri = current_app.config['MONGO_URI']
            mongo_db = current_app.config['MONGO_DB']
            client = MongoClient(mongo_uri)
            g.client = client
            g.db = client[mongo_db]
            logger.info(f"MongoDB 연결 성공: {mongo_uri}/{mongo_db}")
        except Exception as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            raise e
    return g.db

def close_db(e=None):
    """애플리케이션 컨텍스트 종료 시 데이터베이스 연결을 닫습니다."""
    client = g.pop('client', None)
    if client is not None:
        client.close()
        logger.info("MongoDB 연결 종료")

def init_db(app):
    """데이터베이스를 초기화하고 필요한 컬렉션과 인덱스를 생성합니다."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        initialize_collections(db, app)
        initialize_food_metadata(db, app)

def initialize_collections(db, app):
    """필요한 컬렉션이 존재하는지 확인하고, 인덱스를 생성합니다."""
    # 컬렉션 목록 확인
    collections = db.list_collection_names()
    
    # 사용자 컬렉션 추가
    if 'users' not in collections:
        logger.info("'users' 컬렉션 생성")
        users = db.create_collection('users')
    else:
        users = db.users
    
    # 음식 정보 컬렉션
    if 'foods' not in collections:
        logger.info("'foods' 컬렉션 생성")
        foods = db.create_collection('foods')
    else:
        foods = db.foods
    
    # 인식 결과 컬렉션
    if 'recognitions' not in collections:
        logger.info("'recognitions' 컬렉션 생성")
        recognitions = db.create_collection('recognitions')
    else:
        recognitions = db.recognitions
    
    # 메뉴판 인식 결과 컬렉션
    if 'menu_recognitions' not in collections:
        logger.info("'menu_recognitions' 컬렉션 생성")
        menu_recognitions = db.create_collection('menu_recognitions')
    else:
        menu_recognitions = db.menu_recognitions
    
    # 인덱스 생성
    foods.create_index("nameEn")
    foods.create_index("nameKo")
    foods.create_index("dishId")
    users.create_index("email", unique=True)
    users.create_index("username")
    recognitions.create_index("timestamp")
    recognitions.create_index([("timestamp", DESCENDING)])
    recognitions.create_index("user_id")
    recognitions.create_index("is_favorite")
    menu_recognitions.create_index("timestamp")
    menu_recognitions.create_index([("timestamp", DESCENDING)])
    menu_recognitions.create_index("user_id")
    
    logger.info("컬렉션 및 인덱스 초기화 완료")

def initialize_food_metadata(db, app):
    """음식 메타데이터 파일에서 데이터베이스로 정보를 초기화합니다."""
    # 컬렉션이 비어있는 경우에만 데이터 로드
    if db.foods.count_documents({}) == 0:
        try:
            # JSON 파일에서 메타데이터 로드
            metadata_path = app.config['FOOD_METADATA_PATH']
            with open(metadata_path, 'r', encoding='utf-8') as f:
                food_metadata = json.load(f)
            
            # MongoDB에 데이터 삽입
            if isinstance(food_metadata, list):
                # 기존 데이터 삭제 (안전을 위한 추가 조치)
                db.foods.delete_many({})
                
                # 새 데이터 삽입
                db.foods.insert_many(food_metadata)
                logger.info(f"{len(food_metadata)}개 음식 메타데이터가 데이터베이스에 추가되었습니다.")
            else:
                logger.error("메타데이터 형식이 올바르지 않습니다. 리스트 형식이어야 합니다.")
        except Exception as e:
            logger.error(f"데이터베이스 초기화 중 오류 발생: {e}")
    else:
        logger.info("음식 메타데이터가 이미 데이터베이스에 존재합니다.")

def get_mongodb_connection():
    """MongoDB 연결을 가져옵니다."""
    from pymongo import MongoClient
    from flask import current_app
    
    mongo_uri = current_app.config['MONGO_URI']
    logger.info(f"MongoDB 연결 생성: {mongo_uri}")
    return MongoClient(mongo_uri)

def get_food_info(food_name, class_to_metadata_mapping=None):
    """MongoDB에서 음식 정보를 가져옵니다."""
    try:
        db = get_db()
        foods_collection = db.foods
        
        # YOLO 클래스 이름을 메타데이터 이름으로 변환
        metadata_name = food_name
        if class_to_metadata_mapping and food_name in class_to_metadata_mapping:
            metadata_name = class_to_metadata_mapping[food_name]
        
        logger.info(f"음식 정보 조회: {food_name} -> 매핑된 이름: {metadata_name}")
        
        # DB 검색 전략 - 다양한 방법으로 찾기
        food_info = None
        
        # 1. 정확한 영어 이름(nameEn)으로 검색
        food_info = foods_collection.find_one({
            'nameEn': metadata_name
        })
        
        # 2. 정확한 한국어 이름(nameKo)으로 검색
        if not food_info:
            food_info = foods_collection.find_one({
                'nameKo': metadata_name
            })
        
        # 3. 클래스 이름과 정확히 일치하는 nameEn으로 검색
        if not food_info:
            food_info = foods_collection.find_one({
                'nameEn': food_name
            })
            
        # 4. 부분 일치로 nameEn 검색 
        if not food_info:
            food_info = foods_collection.find_one({
                'nameEn': {'$regex': metadata_name, '$options': 'i'}
            })
        
        # 5. 부분 일치로 nameKo 검색
        if not food_info:
            food_info = foods_collection.find_one({
                'nameKo': {'$regex': metadata_name, '$options': 'i'}
            })
        
        # 6. 직접 클래스 이름과 부분 일치로 검색
        if not food_info:
            food_info = foods_collection.find_one({
                '$or': [
                    {'nameEn': {'$regex': food_name, '$options': 'i'}},
                    {'nameKo': {'$regex': food_name, '$options': 'i'}}
                ]
            })
            
        # 7. dishId로 검색 (문자열 또는 숫자일 수 있음)
        if not food_info:
            # 숫자로 변환 가능한지 확인
            try:
                class_id = int(food_name)
                food_info = foods_collection.find_one({
                    'dishId': str(class_id)  # 문자열로 변환하여 검색
                })
            except (ValueError, TypeError):
                # dishId가 문자열일 수도 있으니 직접 검색
                food_info = foods_collection.find_one({
                    'dishId': food_name
                })
                
        # 8. 하드코딩된 기본값 (김밥의 경우)
        if not food_info and food_name.lower() in ['gimbap', '김밥', 'kimbap']:
            food_info = {
                "dishId": "0",
                "nameKo": "김밥",
                "nameEn": "Gimbap",
                "classId": "C001",
                "className": "Rice Dishes",
                "koreanCategory": "밥 [Bap]",
                "allergens": ["글루텐"],
                "vegetarianStatus": "부분채식",
                "descriptionKo": "흰밥을 소금과 참기름으로 밑간한 뒤 살짝 구운 김 위에 얇게 펼쳐 놓고 시금치, 당근, 단무지, 고기볶음 등을 넣어 둘둘 말아 알맞은 크기로 썰어 먹는 음식이다.",
                "descriptionEn": "Rice seasoned with salt and sesame oil and rolled up in a sheet of roasted gim (dried laver) with spinach, carrots, and pickled white radish. The long roll is sliced and served in bite-sized pieces.",
                "ingredients": {
                    "main": ["쌀", "김", "시금치", "당근", "단무지"],
                    "sub": ["계란", "어묵", "우엉"],
                    "sauce": ["참기름", "소금", "설탕", "식초"]
                },
                "cookingMethod": {
                    "primary": "말기",
                    "secondary": ["삶기", "볶기", "썰기"]
                },
                "taste": {
                    "spiciness": 0,
                    "sweetness": 1,
                    "saltiness": 3, 
                    "sourness": 0,
                    "umami": 4,
                    "profile": ["고소한", "담백한", "깔끔한"]
                },
                "mealType": {
                    "primary": "점심",
                    "secondary": ["아침", "간식", "야식"],
                    "occasion": ["일상", "도시락", "피크닉"]
                },
                "region": {
                    "origin": "서울",
                    "popular": ["전국"],
                    "traditional": False
                },
                "similarFoods": {
                    "taste": [
                        {"dishId": "2", "name": "비빔밥", "similarity": 0.70},
                        {"dishId": "4", "name": "만두", "similarity": 0.65}
                    ],
                    "ingredient": [
                        {"dishId": "3", "name": "김치", "similarity": 0.75},
                        {"dishId": "1", "name": "라면", "similarity": 0.60}
                    ],
                    "cooking": [
                        {"dishId": "5", "name": "파전", "similarity": 0.50},
                        {"dishId": "6", "name": "잡채", "similarity": 0.45}
                    ]
                }
            }
        
        if food_info:
            # MongoDB ObjectId는 JSON으로 직렬화할 수 없으므로 제거
            if '_id' in food_info:
                food_info.pop('_id')
                
            logger.info(f"음식 정보 찾음: {food_info.get('nameKo', '')} / {food_info.get('nameEn', '')}")
        else:
            logger.warning(f"음식 정보를 찾을 수 없음: {food_name}")
            
        return food_info
    except Exception as e:
        logger.error(f"음식 정보 조회 중 오류 발생: {e}")
        return None

def save_recognition_result(image_path, detected_foods, overlay_image_path=None):
    """인식 결과를 데이터베이스에 저장합니다."""
    try:
        from flask import session
        from bson.objectid import ObjectId
        import os
        from datetime import datetime
        
        db = get_db()
        
        # 이미지 파일 이름 추출
        image_filename = os.path.basename(image_path)
        
        # 인식 기록 생성
        recognition_record = {
            'image_path': image_path,
            'image_filename': image_filename,
            'detected_foods': detected_foods,
            'timestamp': datetime.now(),
            'is_favorite': False
        }

        # 👉 overlay 이미지 경로도 추가 (있을 경우만)
        if overlay_image_path:
            recognition_record['overlay_image_path'] = overlay_image_path
        
        # 로그인한 사용자의 기록인 경우 사용자 ID 추가
        if 'user_id' in session:
            user_id = session['user_id']
            logger.info(f"인식 결과 저장 - 사용자 ID: {user_id}")
            recognition_record['user_id'] = user_id
        
        # DB에 기록 저장
        result = db.recognitions.insert_one(recognition_record)
        logger.info(f"인식 결과가 DB에 저장되었습니다. ID: {result.inserted_id}")
        
        # 사용자가 로그인 중이라면 통계 업데이트
        if 'user_id' in session:
            try:
                db.users.update_one(
                    {'_id': ObjectId(session['user_id'])},
                    {'$inc': {'stats.recognitions': 1}}
                )
                logger.info(f"사용자 {session['user_id']} 통계 업데이트: 인식 횟수 +1")
            except Exception as stat_error:
                logger.error(f"사용자 통계 업데이트 중 오류: {stat_error}")
        
        return result.inserted_id
    except Exception as e:
        logger.error(f"인식 결과 DB 저장 중 오류 발생: {e}", exc_info=True)
        return None


def save_menu_recognition_result(image_path, original_text, translated_text):
    """메뉴판 인식 결과를 데이터베이스에 저장합니다."""
    try:
        db = get_db()
        
        # 이미지 파일 이름 추출
        image_filename = os.path.basename(image_path)
        
        # 메뉴판 인식 기록 생성
        menu_record = {
            'image_path': image_path,
            'image_filename': image_filename,
            'original_text': original_text,
            'translated_text': translated_text,
            'timestamp': datetime.now(),
            'is_favorite': False
        }
        
        # 로그인한 사용자의 기록인 경우 사용자 ID 추가
        if 'user_id' in session:
            menu_record['user_id'] = session['user_id']
        
        # DB에 기록 저장
        result = db.menu_recognitions.insert_one(menu_record)
        logger.info(f"메뉴판 인식 결과가 DB에 저장되었습니다. ID: {result.inserted_id}")
        
        # 사용자가 로그인 중이라면 통계 업데이트
        if 'user_id' in session:
            db.users.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$inc': {'stats.menu_recognitions': 1}}
            )
            logger.info(f"사용자 {session['user_id']} 통계 업데이트: 메뉴 인식 횟수 +1")
        
        return result.inserted_id
    except Exception as e:
        logger.error(f"메뉴판 인식 결과 DB 저장 중 오류 발생: {e}")
        return None

def get_recent_recognitions(limit=20, page=1, filter=None):
    """최근 인식 기록을 가져옵니다."""
    try:
        import os
        from datetime import datetime
        
        db = get_db()
        
        # 페이지네이션 계산
        skip = (page - 1) * limit
        
        # 필터 설정
        query = filter if filter else {}
        
        # 필터 정보 로깅
        logger.info(f"get_recent_recognitions 필터: {query}, skip: {skip}, limit: {limit}")
        
        # 최신순으로 정렬하여 가져오기
        records = list(db.recognitions.find(query).sort('timestamp', -1).skip(skip).limit(limit))
        
        logger.info(f"인식 기록 조회 결과: {len(records)}개 레코드")
        
        # 필요한 경우 추가 데이터 처리
        for record in records:
            # 이미지 경로를 상대 경로로 변환 (필요한 경우)
            if 'image_path' in record:
                image_filename = record.get('image_filename') or os.path.basename(record['image_path'])
                record['image_url'] = f"/static/uploads/{image_filename}"
            
            # 타임스탬프 포맷팅 (필요한 경우)
            if 'timestamp' in record:
                record['formatted_timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M')
        
        return records
    except Exception as e:
        logger.error(f"인식 기록 조회 중 오류 발생: {e}", exc_info=True)
        return []

def get_recent_menu_recognitions(limit=20, page=1, filter=None):
    """최근 메뉴판 인식 기록을 가져옵니다."""
    try:
        db = get_db()
        
        # 페이지네이션 계산
        skip = (page - 1) * limit
        
        # 필터 설정
        query = filter if filter else {}
        
        # 최신순으로 정렬하여 가져오기
        records = list(db.menu_recognitions.find(query).sort('timestamp', -1).skip(skip).limit(limit))
        
        # 필요한 경우 추가 데이터 처리
        for record in records:
            # 이미지 경로를 상대 경로로 변환 (필요한 경우)
            if 'image_path' in record:
                image_filename = record.get('image_filename') or os.path.basename(record['image_path'])
                record['image_url'] = f"/static/uploads/{image_filename}"
            
            # 타임스탬프 포맷팅 (필요한 경우)
            if 'timestamp' in record:
                record['formatted_timestamp'] = record['timestamp'].strftime('%Y-%m-%d %H:%M')
        
        return records
    except Exception as e:
        logger.error(f"메뉴판 인식 기록 조회 중 오류 발생: {e}")
        return []

def get_user_favorites(user_id, limit=20, page=1):
    """사용자의 즐겨찾기 기록을 가져옵니다."""
    try:
        db = get_db()
        
        # 페이지네이션 계산
        skip = (page - 1) * limit
        
        # 사용자의 즐겨찾기 조회 (음식 인식과 메뉴판 인식 모두)
        food_favorites = list(db.recognitions.find({
            'user_id': user_id,
            'is_favorite': True
        }).sort('timestamp', -1).skip(skip).limit(limit))
        
        menu_favorites = list(db.menu_recognitions.find({
            'user_id': user_id,
            'is_favorite': True
        }).sort('timestamp', -1).skip(skip).limit(limit))
        
        # 두 결과 병합 및 타임스탬프로 정렬
        all_favorites = food_favorites + menu_favorites
        all_favorites.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 필요한 경우 페이지네이션 적용
        favorites = all_favorites[:limit]
        
        return favorites
    except Exception as e:
        logger.error(f"즐겨찾기 조회 중 오류 발생: {e}")
        return []

def search_food_by_name(search_query, limit=10):
    """음식 이름으로 검색합니다."""
    try:
        db = get_db()
        
        # 한글 및 영어 이름으로 검색
        foods = list(db.foods.find({
            '$or': [
                {'nameKo': {'$regex': search_query, '$options': 'i'}},
                {'nameEn': {'$regex': search_query, '$options': 'i'}}
            ]
        }).limit(limit))
        
        return foods
    except Exception as e:
        logger.error(f"음식 검색 중 오류 발생: {e}")
        return []

def search_recognition_history(search_query, user_id=None, limit=20, page=1):
    """인식 기록을 검색합니다."""
    try:
        db = get_db()
        
        # 페이지네이션 계산
        skip = (page - 1) * limit
        
        # 검색 필터 구성
        query = {
            '$or': [
                {'detected_foods.food_name': {'$regex': search_query, '$options': 'i'}},
                {'detected_foods.nameKo': {'$regex': search_query, '$options': 'i'}},
                {'detected_foods.nameEn': {'$regex': search_query, '$options': 'i'}}
            ]
        }
        
        # 특정 사용자의 기록만 검색하는 경우
        if user_id:
            query['user_id'] = user_id
        
        # 검색 실행
        records = list(db.recognitions.find(query).sort('timestamp', -1).skip(skip).limit(limit))
        
        return records
    except Exception as e:
        logger.error(f"인식 기록 검색 중 오류 발생: {e}")
        return []