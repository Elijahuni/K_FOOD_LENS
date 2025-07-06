# modules/monitoring.py
import os
import time
import json
import logging
import requests
from threading import Thread, Event
from queue import Queue, Full
from flask import current_app

logger = logging.getLogger(__name__)

class AlertLevel:
    """알림 레벨 정의"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MonitoringSystem:
    """모니터링 및 알림 시스템"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self.alert_queue = Queue(maxsize=1000)
        self.metrics = {}
        self.stop_event = Event()
        self.worker_thread = None
        self.slack_webhook_url = None
        self.discord_webhook_url = None
        self.telegram_bot_token = None
        self.telegram_chat_id = None
        self.enabled = False
    
    def init_app(self, app):
        """Flask 앱으로 초기화"""
        self.slack_webhook_url = app.config.get('SLACK_WEBHOOK_URL')
        self.discord_webhook_url = app.config.get('DISCORD_WEBHOOK_URL')
        self.telegram_bot_token = app.config.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = app.config.get('TELEGRAM_CHAT_ID')
        
        # 환경변수 기반 기능 활성화 여부
        self.enabled = app.config.get('ENABLE_MONITORING', False)
        
        if self.enabled:
            # 워커 스레드 시작
            self.worker_thread = Thread(target=self._alert_worker, daemon=True)
            self.worker_thread.start()
            logger.info("모니터링 시스템이 활성화되었습니다.")
        else:
            logger.info("모니터링 시스템이 비활성화되었습니다.")
        
        # 앱 종료 시 워커 스레드 정리
        app.teardown_appcontext(self._teardown)
    
    def _teardown(self, exception=None):
        """앱 종료 시 정리 작업"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.worker_thread.join(timeout=5)
    
    def _alert_worker(self):
        """알림 큐를 처리하는 백그라운드 워커"""
        while not self.stop_event.is_set():
            try:
                # 큐에서 알림 메시지 가져오기
                try:
                    alert = self.alert_queue.get(timeout=1)
                except Exception:
                    continue
                
                # 알림 전송 시도
                success = False
                
                # 슬랙 알림 전송
                if self.slack_webhook_url:
                    slack_success = self._send_slack_alert(alert)
                    success = success or slack_success
                
                # 디스코드 알림 전송
                if self.discord_webhook_url:
                    discord_success = self._send_discord_alert(alert)
                    success = success or discord_success
                
                # 텔레그램 알림 전송
                if self.telegram_bot_token and self.telegram_chat_id:
                    telegram_success = self._send_telegram_alert(alert)
                    success = success or telegram_success
                
                if not success:
                    logger.warning(f"알림 전송에 실패했습니다: {alert.get('title')}")
                
                # 작업 완료 표시
                self.alert_queue.task_done()
                
            except Exception as e:
                logger.exception(f"알림 워커 스레드 오류: {e}")
    
    def _send_slack_alert(self, alert):
        """Slack으로 알림 전송"""
        try:
            level = alert.get('level', AlertLevel.INFO)
            title = alert.get('title', '알림')
            message = alert.get('message', '')
            details = alert.get('details', {})
            
            # 레벨에 따른 이모지 설정
            emoji = "🔵"
            if level == AlertLevel.WARNING:
                emoji = "⚠️"
            elif level == AlertLevel.ERROR:
                emoji = "🔴"
            elif level == AlertLevel.CRITICAL:
                emoji = "🚨"
            
            # Slack 메시지 포맷팅
            slack_message = {
                "text": f"{emoji} {title}",
                "attachments": [
                    {
                        "color": "#36a64f" if level == AlertLevel.INFO else 
                                "#ffcc00" if level == AlertLevel.WARNING else 
                                "#ff0000",
                        "fields": [
                            {
                                "title": "메시지",
                                "value": message,
                                "short": False
                            }
                        ]
                    }
                ]
            }
            
            # 세부 정보 추가
            if details:
                for key, value in details.items():
                    slack_message["attachments"][0]["fields"].append({
                        "title": key,
                        "value": str(value),
                        "short": True
                    })
            
            # Slack 웹훅 전송
            response = requests.post(
                self.slack_webhook_url,
                json=slack_message,
                timeout=5
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack 알림 전송 실패: {e}")
            return False
    
    def _send_discord_alert(self, alert):
        """Discord로 알림 전송"""
        try:
            level = alert.get('level', AlertLevel.INFO)
            title = alert.get('title', '알림')
            message = alert.get('message', '')
            details = alert.get('details', {})
            
            # 레벨에 따른 색상 설정
            color = 0x3498db  # INFO - 파란색
            if level == AlertLevel.WARNING:
                color = 0xf1c40f  # 노란색
            elif level == AlertLevel.ERROR:
                color = 0xe74c3c  # 빨간색
            elif level == AlertLevel.CRITICAL:
                color = 0x9b59b6  # 보라색
            
            # 세부 정보 포맷팅
            fields = []
            if details:
                for key, value in details.items():
                    fields.append({
                        "name": key,
                        "value": str(value),
                        "inline": True
                    })
            
            # Discord 메시지 포맷팅
            discord_message = {
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": color,
                        "fields": fields
                    }
                ]
            }
            
            # Discord 웹훅 전송
            response = requests.post(
                self.discord_webhook_url,
                json=discord_message,
                timeout=5
            )
            
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Discord 알림 전송 실패: {e}")
            return False
    
    def _send_telegram_alert(self, alert):
        """Telegram으로 알림 전송"""
        try:
            level = alert.get('level', AlertLevel.INFO)
            title = alert.get('title', '알림')
            message = alert.get('message', '')
            details = alert.get('details', {})
            
            # 레벨에 따른 이모지 설정
            emoji = "🔵"
            if level == AlertLevel.WARNING:
                emoji = "⚠️"
            elif level == AlertLevel.ERROR:
                emoji = "🔴"
            elif level == AlertLevel.CRITICAL:
                emoji = "🚨"
            
            # 텔레그램 메시지 포맷팅
            text = f"{emoji} *{title}*\n\n{message}\n"
            
            # 세부 정보 추가
            if details:
                text += "\n*세부 정보:*\n"
                for key, value in details.items():
                    text += f"- *{key}:* {value}\n"
            
            # Telegram API 호출
            response = requests.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                },
                timeout=5
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram 알림 전송 실패: {e}")
            return False
    
    def send_alert(self, title, message, level=AlertLevel.INFO, details=None):
        """알림 전송"""
        if not self.enabled:
            logger.info(f"알림 비활성화 상태: {title}")
            return False
        
        try:
            alert = {
                'title': title,
                'message': message,
                'level': level,
                'details': details or {},
                'timestamp': time.time()
            }
            
            # 큐에 알림 추가 (최대 대기 시간 1초)
            self.alert_queue.put(alert, timeout=1)
            
            # INFO 이상 레벨은 로그에도 기록
            if level != AlertLevel.INFO:
                log_level = logging.WARNING if level == AlertLevel.WARNING else logging.ERROR
                logger.log(log_level, f"알림 발생: {title} - {message}", extra=details)
            
            return True
        except Full:
            logger.warning("알림 큐가 가득 차서 알림을 보낼 수 없습니다.")
            return False
        except Exception as e:
            logger.error(f"알림 전송 중 오류 발생: {e}")
            return False
    
    def record_metric(self, name, value, tags=None):
        """메트릭 기록"""
        if not self.enabled:
            return
        
        try:
            if name not in self.metrics:
                self.metrics[name] = []
            
            self.metrics[name].append({
                'value': value,
                'tags': tags or {},
                'timestamp': time.time()
            })
            
            # 최대 1000개 항목만 유지
            if len(self.metrics[name]) > 1000:
                self.metrics[name] = self.metrics[name][-1000:]
        except Exception as e:
            logger.error(f"메트릭 기록 중 오류 발생: {e}")
    
    def get_metrics(self, name=None, limit=100):
        """메트릭 조회"""
        if name:
            return self.metrics.get(name, [])[-limit:]
        else:
            result = {}
            for metric_name, values in self.metrics.items():
                result[metric_name] = values[-limit:]
            return result

# 모니터링 시스템 인스턴스 생성
monitoring = MonitoringSystem.get_instance()

def init_monitoring(app):
    """모니터링 시스템 초기화"""
    monitoring.init_app(app)
    return monitoring

# 편의 함수
def send_alert(title, message, level=AlertLevel.INFO, details=None):
    """알림 전송 편의 함수"""
    return monitoring.send_alert(title, message, level, details)

def record_metric(name, value, tags=None):
    """메트릭 기록 편의 함수"""
    return monitoring.record_metric(name, value, tags)