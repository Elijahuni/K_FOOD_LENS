"""
MongoDB 데이터 확인 스크립트
"""
from modules.database import get_db
from bson.objectid import ObjectId
import json
from datetime import datetime

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def check_database():
    """MongoDB 데이터 확인"""
    db = get_db()
    
    # 컬렉션 목록 확인
    collections = db.list_collection_names()
    print(f"컬렉션 목록: {collections}")
    
    # 사용자 수 확인
    users_count = db.users.count_documents({})
    print(f"사용자 수: {users_count}")
    
    # 인식 결과 수 확인
    recognitions_count = db.recognitions.count_documents({})
    print(f"음식 인식 결과 수: {recognitions_count}")
    
    # 메뉴 인식 결과 수 확인
    menu_recognitions_count = db.menu_recognitions.count_documents({})
    print(f"메뉴 인식 결과 수: {menu_recognitions_count}")
    
    # 사용자별 인식 결과 확인
    print("\n사용자별 인식 결과:")
    users = list(db.users.find({}, {'_id': 1, 'username': 1, 'email': 1}))
    
    for user in users:
        user_id = user['_id']
        user_id_str = str(user_id)
        
        # ObjectId 형식과 문자열 형식 모두 확인
        food_count_obj = db.recognitions.count_documents({'user_id': user_id})
        food_count_str = db.recognitions.count_documents({'user_id': user_id_str})
        
        menu_count_obj = db.menu_recognitions.count_documents({'user_id': user_id})
        menu_count_str = db.menu_recognitions.count_documents({'user_id': user_id_str})
        
        print(f"  사용자: {user.get('username')} ({user.get('email')})")
        print(f"    ID(ObjectId): {user_id}")
        print(f"    ID(String): {user_id_str}")
        print(f"    음식 인식 결과 수(ObjectId): {food_count_obj}")
        print(f"    음식 인식 결과 수(String): {food_count_str}")
        print(f"    메뉴 인식 결과 수(ObjectId): {menu_count_obj}")
        print(f"    메뉴 인식 결과 수(String): {menu_count_str}")
    
    # 최근 인식 결과 몇 개 확인
    print("\n최근 음식 인식 결과:")
    recent_recognitions = list(db.recognitions.find().sort('timestamp', -1).limit(3))
    for idx, record in enumerate(recent_recognitions):
        print(f"  {idx+1}. 인식 ID: {record.get('_id')}")
        print(f"     사용자 ID: {record.get('user_id')}")
        print(f"     이미지: {record.get('image_path')}")
        print(f"     인식 음식 수: {len(record.get('detected_foods', []))}")
        print(f"     타임스탬프: {record.get('timestamp')}")
    
    # 최근 메뉴 인식 결과 몇 개 확인
    print("\n최근 메뉴 인식 결과:")
    recent_menu_recognitions = list(db.menu_recognitions.find().sort('timestamp', -1).limit(3))
    for idx, record in enumerate(recent_menu_recognitions):
        print(f"  {idx+1}. 인식 ID: {record.get('_id')}")
        print(f"     사용자 ID: {record.get('user_id')}")
        print(f"     이미지: {record.get('image_path')}")
        print(f"     타임스탬프: {record.get('timestamp')}")

if __name__ == "__main__":
    # 이 스크립트는 Flask 앱 컨텍스트 내에서 실행해야 합니다.
    print("이 스크립트는 Flask 앱 컨텍스트 내에서 실행해야 합니다.")