# modules/db_manager.py
import logging
import threading
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from flask import current_app, g

logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """데이터베이스 관련 예외 클래스"""
    pass

class ConnectionPool:
    """MongoDB 연결 풀 클래스"""
    
    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
        self.connection_count = 0
    
    def get_connection(self, uri, timeout=5000):
        """사용 가능한 연결을 반환하거나 새 연결 생성"""
        with self.lock:
            # 사용 가능한 연결이 있는지 확인
            if self.connections:
                return self.connections.pop()
            
            # 최대 연결 수를 초과하지 않았는지 확인
            if self.connection_count >= self.max_connections:
                # 연결 풀이 가득 찼지만 연결이 없음 - 대기 후 재시도 로직을 구현할 수 있음
                logger.warning(f"연결 풀이 가득 찼습니다. (max={self.max_connections})")
                # 여기서는 단순히 새 연결 생성 (실제로는 대기 또는 예외 처리가 필요)
            
            # 새 연결 생성
            try:
                client = MongoClient(uri, serverSelectionTimeoutMS=timeout)
                # 연결 테스트 - 간단한 명령 실행
                client.admin.command('ping')
                self.connection_count += 1
                logger.debug(f"새 MongoDB 연결 생성 (현재 연결 수: {self.connection_count})")
                return client
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"MongoDB 연결 생성 실패: {e}")
                raise DatabaseError(f"MongoDB 연결 실패: {e}")
    
    def release_connection(self, client):
        """연결을 풀로 반환"""
        with self.lock:
            # 연결이 여전히 살아있는지 확인
            try:
                client.admin.command('ping')
                self.connections.append(client)
                logger.debug(f"연결이 풀로 반환됨 (사용 가능 연결: {len(self.connections)})")
            except Exception as e:
                # 연결이 끊어졌으면 카운트만 감소
                logger.warning(f"손상된 연결 폐기: {e}")
                self.connection_count -= 1
                try:
                    client.close()
                except:
                    pass
    
    def close_all(self):
        """모든 연결 닫기"""
        with self.lock:
            for client in self.connections:
                try:
                    client.close()
                except Exception as e:
                    logger.warning(f"연결 닫기 중 오류: {e}")
            
            self.connections = []
            self.connection_count = 0
            logger.info("모든 데이터베이스 연결이 닫혔습니다.")

class DBManager:
    """데이터베이스 관리자 싱글톤 클래스"""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """초기화 - 직접 호출하지 말고 get_instance() 사용"""
        self.app = None
        self.connection_pools = {}
        self.db_instances = {}
    
    def init_app(self, app):
        """Flask 앱으로 초기화"""
        self.app = app
        
        # 앱 종료 시 모든 연결 닫기
        app.teardown_appcontext(self.close_connections)
        
        logger.info("DBManager가 Flask 앱에 초기화되었습니다.")
        return self
    
    def get_db(self, db_name=None, uri=None, pool_name='default'):
        """데이터베이스 인스턴스 반환"""
        # 앱 컨텍스트에서 설정 가져오기
        if not db_name and self.app:
            db_name = self.app.config.get('MONGO_DB')
        
        if not uri and self.app:
            uri = self.app.config.get('MONGO_URI')
        
        if not db_name or not uri:
            raise ValueError("데이터베이스 이름과 URI는 필수입니다.")
        
        # g 객체에서 연결 확인 (Request 컨텍스트 내에서 재사용)
        if hasattr(g, 'dbs') and pool_name in g.dbs and db_name in g.dbs[pool_name]:
            return g.dbs[pool_name][db_name]
        
        # 연결 풀 가져오기
        if pool_name not in self.connection_pools:
            self.connection_pools[pool_name] = ConnectionPool()
        
        # 연결 가져오기
        client = self.connection_pools[pool_name].get_connection(uri)
        
        # DB 인스턴스 생성
        db = client[db_name]
        
        # g 객체에 저장
        if not hasattr(g, 'dbs'):
            g.dbs = {}
        if pool_name not in g.dbs:
            g.dbs[pool_name] = {}
        g.dbs[pool_name][db_name] = db
        
        # 클라이언트 참조 저장 (연결 해제용)
        if not hasattr(g, 'clients'):
            g.clients = {}
        if pool_name not in g.clients:
            g.clients[pool_name] = []
        g.clients[pool_name].append(client)
        
        logger.info(f"데이터베이스 연결 성공: {uri}/{db_name} (풀: {pool_name})")
        return db
    
    def close_connections(self, exception=None):
        """요청 종료 시 연결 반환"""
        if hasattr(g, 'clients'):
            for pool_name, clients in g.clients.items():
                for client in clients:
                    if pool_name in self.connection_pools:
                        self.connection_pools[pool_name].release_connection(client)
                    else:
                        try:
                            client.close()
                        except Exception as e:
                            logger.warning(f"연결 닫기 중 오류: {e}")
        
        # g 객체 정리
        if hasattr(g, 'dbs'):
            g.dbs = {}
        if hasattr(g, 'clients'):
            g.clients = {}
    
    def shutdown(self):
        """모든 연결 풀 종료"""
        for pool_name, pool in self.connection_pools.items():
            try:
                pool.close_all()
            except Exception as e:
                logger.error(f"연결 풀 '{pool_name}' 종료 중 오류: {e}")
        
        self.connection_pools = {}
        logger.info("모든 데이터베이스 연결 풀이 종료되었습니다.")

# 싱글톤 인스턴스 생성
db_manager = DBManager.get_instance()

# 편의 함수들 (기존 코드와의 호환성 유지)
def init_db(app):
    """데이터베이스 초기화"""
    global db_manager
    db_manager.init_app(app)
    
    # 기존 초기화 작업 수행
    with app.app_context():
        db = get_db()
        initialize_collections(db, app)
        initialize_food_metadata(db, app)

def get_db():
    """애플리케이션 컨텍스트에서 데이터베이스 연결을 가져옵니다."""
    global db_manager
    try:
        return db_manager.get_db()
    except Exception as e:
        logger.error(f"데이터베이스 연결 가져오기 실패: {e}")
        raise DatabaseError(f"데이터베이스 연결 실패: {e}")

def get_mongodb_connection():
    """MongoDB 연결을 직접 가져옵니다."""
    from flask import current_app
    global db_manager
    
    mongo_uri = current_app.config['MONGO_URI']
    logger.info(f"MongoDB 연결 요청: {mongo_uri}")
    
    # 연결 풀에서 연결 가져오기
    pool_name = 'direct'  # 직접 접근용 풀 이름
    if pool_name not in db_manager.connection_pools:
        db_manager.connection_pools[pool_name] = ConnectionPool(max_connections=5)
    
    return db_manager.connection_pools[pool_name].get_connection(mongo_uri)

# 추천 시스템용 함수 대체
def get_fresh_db_connection():
    """추천 시스템을 위한 새로운 MongoDB 연결을 생성합니다."""
    from flask import current_app
    global db_manager
    
    try:
        mongo_uri = current_app.config['MONGO_URI']
        db_name = current_app.config['MONGO_DB']
        
        # 추천 시스템용 특별 풀 사용
        pool_name = 'recommender'
        db = db_manager.get_db(db_name, mongo_uri, pool_name)
        
        logger.info(f"추천 시스템용 MongoDB 연결 생성 성공: {mongo_uri}")
        return db
    except Exception as e:
        logger.error(f"추천 시스템용 MongoDB 연결 생성 중 오류 발생: {e}")
        return None