"""Heartbeat monitoring system for SyncNet v5"""
import threading
import time
import logging
import socket
import json
from typing import Dict, List, Set, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from common.config import DEFAULT_SERVER_CONFIGS, TIMEOUTS, NETWORK_CONSTANTS
from common.messages import Message, MessageType, LamportClock

class ServerStatus(Enum):
    """Server health status"""
    ACTIVE = "active"
    SUSPECTED = "suspected"
    FAILED = "failed"
    UNKNOWN = "unknown"

@dataclass
class HeartbeatInfo:
    """Heartbeat information for a server"""
    server_id: str
    last_heartbeat: float
    status: ServerStatus
    consecutive_failures: int
    last_response_time: float

class HeartbeatMonitor:
    """Thread-safe heartbeat monitoring and failure detection"""
    
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.heartbeat_interval = TIMEOUTS['heartbeat_interval']
        self.death_detection_timeout = TIMEOUTS['leader_death_detection'] 
        self.socket_timeout = TIMEOUTS['socket_timeout']
        
        # Server tracking
        self.servers = {config.server_id: config for config in DEFAULT_SERVER_CONFIGS}
        self.heartbeat_info: Dict[str, HeartbeatInfo] = {}
        self.lamport_clock = LamportClock()
        
        # Threading and control
        self._lock = threading.RLock()
        self._running = False
        self._heartbeat_thread = None
        self._monitor_thread = None
        
        # Callbacks for failure events
        self.failure_callbacks: List[Callable[[str], None]] = []
        self.recovery_callbacks: List[Callable[[str], None]] = []
        
        # Statistics
        self.heartbeats_sent = 0
        self.heartbeats_received = 0
        self.failures_detected = 0
        
        self.logger = logging.getLogger(f'heartbeat.{server_id}')
        
        # Initialize heartbeat info for all servers
        self._initialize_server_tracking()
        
        self.logger.info(f"Heartbeat monitor initialized for {server_id}")
    
    def _initialize_server_tracking(self):
        """Initialize heartbeat tracking for all servers"""
        current_time = time.time()
        
        for server_id in self.servers:
            if server_id != self.server_id:
                self.heartbeat_info[server_id] = HeartbeatInfo(
                    server_id=server_id,
                    last_heartbeat=current_time,
                    status=ServerStatus.UNKNOWN,
                    consecutive_failures=0,
                    last_response_time=0.0
                )
    
    def start_monitoring(self):
        """Start heartbeat monitoring threads"""
        with self._lock:
            if self._running:
                self.logger.warning("Heartbeat monitoring already running")
                return
            
            self._running = True
            
            # Start heartbeat sending thread
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"heartbeat-sender-{self.server_id}",
                daemon=True
            )
            self._heartbeat_thread.start()
            
            # Start failure monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name=f"heartbeat-monitor-{self.server_id}",
                daemon=True
            )
            self._monitor_thread.start()
            
            self.logger.info("Heartbeat monitoring started")
    
    def stop_monitoring(self):
        """Stop heartbeat monitoring threads"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Wait for threads to finish
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                self._heartbeat_thread.join(timeout=2.0)
            
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=2.0)
            
            self.logger.info("Heartbeat monitoring stopped")
    
    def _heartbeat_loop(self):
        """Main heartbeat sending loop"""
        self.logger.info("Heartbeat sending thread started")
        
        while self._running:
            try:
                # Send heartbeats to all other servers
                for server_id in self.servers:
                    if server_id != self.server_id and self._running:
                        self._send_heartbeat_to_server(server_id)
                
                # Wait for next heartbeat interval
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                time.sleep(1.0)  # Brief pause before retry
        
        self.logger.info("Heartbeat sending thread stopped")
    
    def _monitor_loop(self):
        """Main failure monitoring loop"""
        self.logger.info("Failure monitoring thread started")
        
        while self._running:
            try:
                current_time = time.time()
                
                # Check each server for failures
                with self._lock:
                    for server_id, info in self.heartbeat_info.items():
                        if not self._running:
                            break
                        
                        time_since_heartbeat = current_time - info.last_heartbeat
                        
                        # Update server status based on time since last heartbeat
                        new_status = self._determine_server_status(time_since_heartbeat, info)
                        
                        if new_status != info.status:
                            self._handle_status_change(server_id, info.status, new_status)
                            info.status = new_status
                
                # Monitor every 2 seconds
                time.sleep(2.0)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(1.0)
        
        self.logger.info("Failure monitoring thread stopped")
    
    def _send_heartbeat_to_server(self, target_server_id: str):
        """Send heartbeat to specific server"""
        if target_server_id not in self.servers:
            return
        
        try:
            target_config = self.servers[target_server_id]
            
            # Create heartbeat message
            timestamp = self.lamport_clock.tick()
            heartbeat_data = {
                'type': 'heartbeat',
                'sender_id': self.server_id,
                'timestamp': timestamp,
                'send_time': time.time()
            }
            
            # Send via UDP to heartbeat port
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.socket_timeout)
            
            message = json.dumps(heartbeat_data).encode()
            target_port = target_config.heartbeat_port
            
            sock.sendto(message, (target_config.host, target_port))
            sock.close()
            
            self.heartbeats_sent += 1
            self.logger.debug(f"Sent heartbeat to {target_server_id}:{target_port}")
            
        except Exception as e:
            self.logger.debug(f"Failed to send heartbeat to {target_server_id}: {e}")
            # Don't treat send failures as server failures immediately
    
    def receive_heartbeat(self, sender_id: str, heartbeat_data: Dict):
        """Process received heartbeat from another server"""
        if sender_id == self.server_id:
            return  # Ignore our own heartbeats
        
        with self._lock:
            current_time = time.time()
            
            # Update Lamport clock
            if 'timestamp' in heartbeat_data:
                self.lamport_clock.update(heartbeat_data['timestamp'])
            
            # Update or create heartbeat info
            if sender_id not in self.heartbeat_info:
                self.heartbeat_info[sender_id] = HeartbeatInfo(
                    server_id=sender_id,
                    last_heartbeat=current_time,
                    status=ServerStatus.ACTIVE,
                    consecutive_failures=0,
                    last_response_time=current_time
                )
            else:
                info = self.heartbeat_info[sender_id]
                old_status = info.status
                info.last_heartbeat = current_time
                info.last_response_time = current_time
                info.consecutive_failures = 0
                
                # Update status to ACTIVE if receiving heartbeat
                new_status = ServerStatus.ACTIVE
                if old_status != new_status:
                    info.status = new_status
                    self._handle_status_change(sender_id, old_status, new_status)
            
            self.heartbeats_received += 1
            self.logger.debug(f"Received heartbeat from {sender_id}")
    
    def _determine_server_status(self, time_since_heartbeat: float, info: HeartbeatInfo) -> ServerStatus:
        """Determine server status based on time since last heartbeat"""
        
        # If we haven't heard from server in death detection timeout, it's failed
        if time_since_heartbeat > self.death_detection_timeout:
            return ServerStatus.FAILED
        
        # If we haven't heard for half the timeout, it's suspected
        elif time_since_heartbeat > (self.death_detection_timeout / 2):
            return ServerStatus.SUSPECTED
        
        # If we've heard recently, it's active
        elif time_since_heartbeat < self.heartbeat_interval * 3:
            return ServerStatus.ACTIVE
        
        # Default to unknown for edge cases
        else:
            return ServerStatus.UNKNOWN
    
    def _handle_status_change(self, server_id: str, old_status: ServerStatus, new_status: ServerStatus):
        """Handle server status changes and trigger callbacks"""
        
        self.logger.info(f"Server {server_id} status changed: {old_status.value} → {new_status.value}")
        
        # Server failure detected
        if new_status == ServerStatus.FAILED and old_status != ServerStatus.FAILED:
            self.failures_detected += 1
            self.logger.warning(f"Server {server_id} detected as FAILED")
            
            # Trigger failure callbacks
            for callback in self.failure_callbacks:
                try:
                    callback(server_id)
                except Exception as e:
                    self.logger.error(f"Error in failure callback: {e}")
        
        # Server recovery detected
        elif new_status == ServerStatus.ACTIVE and old_status in [ServerStatus.FAILED, ServerStatus.SUSPECTED]:
            self.logger.info(f"Server {server_id} recovered to ACTIVE")
            
            # Trigger recovery callbacks
            for callback in self.recovery_callbacks:
                try:
                    callback(server_id)
                except Exception as e:
                    self.logger.error(f"Error in recovery callback: {e}")
    
    def add_failure_callback(self, callback: Callable[[str], None]):
        """Add callback for server failure events"""
        self.failure_callbacks.append(callback)
    
    def add_recovery_callback(self, callback: Callable[[str], None]):
        """Add callback for server recovery events"""
        self.recovery_callbacks.append(callback)
    
    def get_server_status(self, server_id: str) -> ServerStatus:
        """Get current status of a server"""
        with self._lock:
            if server_id in self.heartbeat_info:
                return self.heartbeat_info[server_id].status
            return ServerStatus.UNKNOWN
    
    def get_active_servers(self) -> List[str]:
        """Get list of currently active servers"""
        with self._lock:
            active_servers = [self.server_id]  # Include ourselves
            
            for server_id, info in self.heartbeat_info.items():
                if info.status == ServerStatus.ACTIVE:
                    active_servers.append(server_id)
            
            return active_servers
    
    def get_failed_servers(self) -> List[str]:
        """Get list of currently failed servers"""
        with self._lock:
            failed_servers = []
            
            for server_id, info in self.heartbeat_info.items():
                if info.status == ServerStatus.FAILED:
                    failed_servers.append(server_id)
            
            return failed_servers
    
    def get_server_statuses(self) -> Dict[str, str]:
        """Get status of all servers as a dictionary"""
        with self._lock:
            statuses = {}
            
            for server_id, info in self.heartbeat_info.items():
                statuses[server_id] = info.status.value
            
            return statuses
    
    def force_check_server(self, server_id: str) -> ServerStatus:
        """Force immediate health check of a specific server"""
        if server_id not in self.servers or server_id == self.server_id:
            return ServerStatus.UNKNOWN
        
        # Send immediate heartbeat and wait briefly for response
        old_received_count = self.heartbeats_received
        self._send_heartbeat_to_server(server_id)
        
        # Wait up to 1 second for response
        start_time = time.time()
        while time.time() - start_time < 1.0:
            if self.heartbeats_received > old_received_count:
                break
            time.sleep(0.1)
        
        return self.get_server_status(server_id)
    
    def get_heartbeat_statistics(self) -> Dict:
        """Get heartbeat monitoring statistics"""
        with self._lock:
            return {
                'server_id': self.server_id,
                'heartbeats_sent': self.heartbeats_sent,
                'heartbeats_received': self.heartbeats_received,
                'failures_detected': self.failures_detected,
                'active_servers': len(self.get_active_servers()),
                'failed_servers': len(self.get_failed_servers()),
                'monitoring_running': self._running,
                'lamport_timestamp': self.lamport_clock.timestamp
            }
    
    def get_detailed_status(self) -> Dict:
        """Get detailed status of all monitored servers"""
        with self._lock:
            current_time = time.time()
            detailed_status = {
                'monitor_server': self.server_id,
                'monitoring_active': self._running,
                'servers': {}
            }
            
            for server_id, info in self.heartbeat_info.items():
                time_since_heartbeat = current_time - info.last_heartbeat
                
                detailed_status['servers'][server_id] = {
                    'status': info.status.value,
                    'last_heartbeat_ago': round(time_since_heartbeat, 2),
                    'consecutive_failures': info.consecutive_failures,
                    'last_response_time': info.last_response_time
                }
            
            return detailed_status
    
    def __enter__(self):
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_monitoring() 