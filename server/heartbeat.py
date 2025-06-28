import threading
import time
import socket
import json
import logging
from typing import Dict, Optional, List, Tuple
from enum import Enum

from common.config import DEFAULT_SERVER_CONFIGS, TIMEOUTS, NETWORK_CONSTANTS

class ServerStatus(Enum):
    ACTIVE = "active"
    FAILED = "failed"

class HeartbeatMonitor:
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.server_config = next(c for c in DEFAULT_SERVER_CONFIGS if c.server_id == server_id)
        
        self.statuses: Dict[str, Tuple[ServerStatus, float]] = {}
        self.last_heartbeat_data: Dict[str, Dict] = {}
        
        self._lock = threading.RLock()
        self._running = False
        self._thread_send = None
        self._thread_check = None
        
        self.logger = logging.getLogger(f'heartbeat.{server_id}')
        
        for config in DEFAULT_SERVER_CONFIGS:
            if config.server_id != self.server_id:
                self.statuses[config.server_id] = (ServerStatus.ACTIVE, time.time())

        self.logger.info("Heartbeat monitor initialized")

    def start(self):
        if self._running:
            return
        self._running = True
        
        # The server is now responsible for sending heartbeats.
        # This monitor only checks for failures.
        self._thread_check = threading.Thread(target=self._check_failures, daemon=True)
        self._thread_check.start()
        self.logger.info("Heartbeat failure detection started")

    def stop(self):
        if not self._running:
            return
        self._running = False
        
        if self._thread_check:
            self._thread_check.join(timeout=2.0)
        self.logger.info("Heartbeat monitoring stopped")

    def receive_heartbeat(self, data: Dict):
        sender_id = data.get("server_id")
        if not sender_id or sender_id == self.server_id:
            return

        with self._lock:
            status, _ = self.statuses.get(sender_id, (None, 0))
            if status != ServerStatus.ACTIVE:
                self.logger.info(f"Server {sender_id} has recovered to ACTIVE status.")
            
            self.statuses[sender_id] = (ServerStatus.ACTIVE, time.time())
            self.last_heartbeat_data[sender_id] = data

    def _check_failures(self):
        while self._running:
            time.sleep(TIMEOUTS['heartbeat_interval'])
            
            with self._lock:
                current_time = time.time()
                failed_servers = []
                for server_id, (status, last_seen) in self.statuses.items():
                    if status == ServerStatus.ACTIVE and (current_time - last_seen) > TIMEOUTS['leader_death_detection']:
                        failed_servers.append(server_id)
                
                for server_id in failed_servers:
                    self.logger.warning(f"Server {server_id} detected as FAILED (no heartbeat).")
                    self.statuses[server_id] = (ServerStatus.FAILED, self.statuses[server_id][1])

    def get_active_servers(self) -> List[str]:
        with self._lock:
            active_list = [
                server_id for server_id, (status, _) in self.statuses.items() 
                if status == ServerStatus.ACTIVE
            ]
            active_list.append(self.server_id)
            return sorted(list(set(active_list)))

    def get_failed_servers(self) -> List[str]:
        with self._lock:
            failed_servers = []
            
            for server_id, (status, _) in self.statuses.items():
                if status == ServerStatus.FAILED:
                    failed_servers.append(server_id)
            
            return failed_servers
    
    def get_heartbeat_statistics(self) -> Dict:
        with self._lock:
            return {
                'server_id': self.server_id,
                'active_servers': len(self.get_active_servers()),
                'failed_servers': len(self.get_failed_servers()),
                'monitoring_running': self._running
            }
    
    def get_detailed_status(self) -> Dict:
        with self._lock:
            current_time = time.time()
            detailed_status = {
                'monitor_server': self.server_id,
                'monitoring_active': self._running,
                'servers': {}
            }
            
            for server_id, (status, last_seen) in self.statuses.items():
                time_since_heartbeat = current_time - last_seen
                
                detailed_status['servers'][server_id] = {
                    'status': status.value,
                    'last_heartbeat_ago': round(time_since_heartbeat, 2)
                }
            
            return detailed_status
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop() 