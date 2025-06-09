"""LCR Election Algorithm for SyncNet v5"""
import threading
import time
import logging
import uuid
import random
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from common.config import DEFAULT_SERVER_CONFIGS, TIMEOUTS
from common.messages import Message, MessageType, LamportClock

class ElectionState(Enum):
    """Election states"""
    IDLE = "idle"
    PARTICIPATING = "participating"
    LEADER = "leader"
    FOLLOWER = "follower"

@dataclass
class ElectionMessage:
    """Election message structure"""
    election_id: str
    candidate_id: str
    candidate_position: int
    message_type: str  # "election", "leader", "ok"
    sender_id: str
    lamport_timestamp: int

class LCRElection:
    """LCR (Le Lann, Chang, and Roberts) Leader Election Algorithm"""
    
    def __init__(self, server_id: str, ring_position: int):
        self.server_id = server_id
        self.ring_position = ring_position
        self.state = ElectionState.IDLE
        self.current_leader = None
        self.election_id = None
        self.election_timeout = TIMEOUTS['election_timeout']
        
        # Ring topology
        self.servers = {config.server_id: config.ring_position for config in DEFAULT_SERVER_CONFIGS}
        self.total_servers = len(self.servers)
        self.failed_servers = set()  # Track failed servers
        
        # Election tracking
        self.received_candidates = set()
        self.election_start_time = None
        self.lamport_clock = LamportClock()
        
        # Threading
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f'election.{server_id}')
        
        self.logger.info(f"Election initialized for {server_id} at position {ring_position}")
    
    def get_next_neighbor(self) -> str:
        """Get the next active server in the ring topology (skipping failed servers)"""
        self.logger.debug(f"get_next_neighbor: failed_servers={self.failed_servers}, servers={self.servers}")
        
        # Get list of active servers (not failed)
        active_servers = {sid: pos for sid, pos in self.servers.items() 
                         if sid not in self.failed_servers and sid != self.server_id}
        
        self.logger.debug(f"get_next_neighbor: active_servers={active_servers}")
        
        if not active_servers:
            self.logger.debug(f"get_next_neighbor: no active servers, returning self")
            return self.server_id  # Only server in ring or all others failed
        
        # Find next active server by position
        current_pos = self.ring_position
        
        # Try positions in order: current+1, current+2, ..., wrapping around
        for offset in range(1, self.total_servers):
            next_pos = (current_pos + offset) % self.total_servers
            
            # Find server at this position that's active
            for server_id, position in active_servers.items():
                if position == next_pos:
                    self.logger.debug(f"get_next_neighbor: found {server_id} at position {next_pos}")
                    return server_id
        
        # Fallback: return any active server
        fallback = next(iter(active_servers.keys()))
        self.logger.debug(f"get_next_neighbor: fallback to {fallback}")
        return fallback
    
    def get_previous_neighbor(self) -> str:
        """Get the previous server in the ring topology"""
        prev_position = (self.ring_position - 1) % self.total_servers
        
        # Find server with previous position
        for server_id, position in self.servers.items():
            if position == prev_position:
                return server_id
        
        # Fallback: return last server that's not us
        for server_id in self.servers:
            if server_id != self.server_id:
                return server_id
        
        return self.server_id  # Only server in ring
    
    def sync_failed_servers_with_heartbeat(self, heartbeat_monitor):
        """Sync failed servers list with current heartbeat status"""
        with self._lock:
            # Get current server statuses from heartbeat monitor
            server_statuses = heartbeat_monitor.get_server_statuses()
            
            self.logger.info(f"Syncing failed servers - current statuses: {server_statuses}")
            self.logger.info(f"Failed servers before sync: {self.failed_servers}")
            
            # Update failed servers based on heartbeat status
            for server_id, status in server_statuses.items():
                if server_id != self.server_id:  # Don't include ourselves
                    if status == 'failed' and server_id not in self.failed_servers:
                        self.failed_servers.add(server_id)
                        self.logger.info(f"Synced {server_id} as failed from heartbeat status")
                    elif status in ['active', 'suspected'] and server_id in self.failed_servers:
                        self.failed_servers.remove(server_id)
                        self.logger.info(f"Synced {server_id} as recovered from heartbeat status")
            
            self.logger.info(f"Failed servers after sync: {self.failed_servers}")
    
    def start_election(self, heartbeat_monitor=None) -> str:
        """Start a new election process"""
        with self._lock:
            # Sync with heartbeat status if monitor provided
            if heartbeat_monitor:
                self.sync_failed_servers_with_heartbeat(heartbeat_monitor)
            
            # Check if election is already in progress
            if self.state == ElectionState.PARTICIPATING:
                # Check for timeout
                if self.is_election_timeout():
                    self.logger.warning(f"Previous election {self.election_id} timed out, restarting")
                    self.reset_election()
                else:
                    self.logger.info("Election already in progress")
                    return self.election_id
            
            # Generate new election ID
            self.election_id = f"election_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            self.state = ElectionState.PARTICIPATING
            self.election_start_time = time.time()
            self.received_candidates.clear()
            
            # Add ourselves as candidate
            self.received_candidates.add((self.server_id, self.ring_position))
            
            self.logger.info(f"Starting election {self.election_id}")
            
            # Start election timeout monitor
            self._start_election_timeout_monitor(heartbeat_monitor)
            
            return self.election_id
    
    def _start_election_timeout_monitor(self, heartbeat_monitor=None):
        """Start monitoring for election timeout"""
        def timeout_monitor():
            time.sleep(self.election_timeout)
            with self._lock:
                if (self.election_id and 
                    self.state == ElectionState.PARTICIPATING and 
                    self.is_election_timeout()):
                    
                    self.logger.warning(f"Election {self.election_id} timed out after {self.election_timeout}s")
                    
                    # Reset and restart election with backoff
                    self.reset_election()
                    
                    # Exponential backoff for retry
                    retry_delay = 2.0 + random.uniform(0, 2.0)
                    self.logger.info(f"Retrying election in {retry_delay:.2f}s")
                    
                    def retry_election():
                        time.sleep(retry_delay)
                        with self._lock:
                            if self.current_leader is None and self.state == ElectionState.IDLE:
                                self.logger.info("Retrying election after timeout")
                                # Pass heartbeat monitor to sync before retry
                                self.start_election(heartbeat_monitor)
                    
                    retry_thread = threading.Thread(target=retry_election, daemon=True)
                    retry_thread.start()
        
        timeout_thread = threading.Thread(target=timeout_monitor, daemon=True)
        timeout_thread.start()
    
    def create_election_message(self, message_type: str = "election") -> ElectionMessage:
        """Create an election message"""
        timestamp = self.lamport_clock.tick()
        
        return ElectionMessage(
            election_id=self.election_id,
            candidate_id=self.server_id,
            candidate_position=self.ring_position,
            message_type=message_type,
            sender_id=self.server_id,
            lamport_timestamp=timestamp
        )
    
    def process_election_message(self, msg: ElectionMessage) -> Tuple[bool, Optional[ElectionMessage]]:
        """
        Process incoming election message according to LCR algorithm
        Returns: (should_forward, response_message)
        """
        with self._lock:
            # Update Lamport clock
            self.lamport_clock.update(msg.lamport_timestamp)
            
            if msg.message_type == "election":
                return self._process_election_msg(msg)
            elif msg.message_type == "leader":
                return self._process_leader_msg(msg)
            elif msg.message_type == "ok":
                return self._process_ok_msg(msg)
            
            return False, None
    
    def _process_election_msg(self, msg: ElectionMessage) -> Tuple[bool, Optional[ElectionMessage]]:
        """Process election message according to LCR rules"""
        
        # If we receive our own election message, we're the leader
        if msg.candidate_id == self.server_id and msg.election_id == self.election_id:
            self._become_leader()
            leader_msg = self.create_election_message("leader")
            return True, leader_msg
        
        # Handle competing elections from other servers
        if msg.election_id != self.election_id and self.state == ElectionState.PARTICIPATING:
            # Multiple elections in progress - use election ID to determine precedence
            if msg.election_id > self.election_id:
                # Newer election takes precedence, abort ours
                self.logger.info(f"Aborting election {self.election_id} in favor of newer election {msg.election_id}")
                self.reset_election()
                self.election_id = msg.election_id
                self.state = ElectionState.PARTICIPATING
                self.election_start_time = time.time()
                self.received_candidates.clear()
                self.received_candidates.add((msg.candidate_id, msg.candidate_position))
            elif msg.election_id < self.election_id:
                # Our election is newer, ignore this older one
                self.logger.debug(f"Ignoring older election {msg.election_id} (ours: {self.election_id})")
                return False, None
        
        # Compare candidate positions (higher position wins in LCR)
        if msg.candidate_position > self.ring_position:
            # Higher position candidate, forward the message
            self.received_candidates.add((msg.candidate_id, msg.candidate_position))
            return True, msg
        elif msg.candidate_position < self.ring_position:
            # Lower position candidate, start our own election if not already participating
            if self.state == ElectionState.IDLE:
                self.start_election()
                our_msg = self.create_election_message("election")
                return True, our_msg
            else:
                # We're already participating with higher priority, don't forward lower candidate
                return False, None
        else:
            # Same position (shouldn't happen in correct ring), break tie by server ID
            if msg.candidate_id > self.server_id:
                self.received_candidates.add((msg.candidate_id, msg.candidate_position))
                return True, msg
            else:
                return False, None
    
    def _process_leader_msg(self, msg: ElectionMessage) -> Tuple[bool, Optional[ElectionMessage]]:
        """Process leader announcement message"""
        
        # If we receive our own leader message, election is complete
        if msg.candidate_id == self.server_id and msg.election_id == self.election_id:
            self.logger.info(f"Leader announcement completed for {self.server_id}")
            return False, None
        
        # Accept the new leader
        self._accept_leader(msg.candidate_id)
        
        # Forward leader message
        return True, msg
    
    def _process_ok_msg(self, msg: ElectionMessage) -> Tuple[bool, Optional[ElectionMessage]]:
        """Process OK message (acknowledgment)"""
        self.logger.debug(f"Received OK from {msg.sender_id}")
        return False, None
    
    def _become_leader(self):
        """Become the leader"""
        with self._lock:
            self.state = ElectionState.LEADER
            self.current_leader = self.server_id
            
            if self.election_start_time:
                duration = time.time() - self.election_start_time
                self.logger.info(f"Became leader! Election {self.election_id} completed in {duration:.2f}s")
            else:
                self.logger.info(f"Became leader! Election {self.election_id}")
    
    def _accept_leader(self, leader_id: str):
        """Accept another server as leader"""
        with self._lock:
            self.state = ElectionState.FOLLOWER
            self.current_leader = leader_id
            
            if self.election_start_time:
                duration = time.time() - self.election_start_time
                self.logger.info(f"Accepted {leader_id} as leader. Election completed in {duration:.2f}s")
            else:
                self.logger.info(f"Accepted {leader_id} as leader")
    
    def is_leader(self) -> bool:
        """Check if this server is the current leader"""
        return self.state == ElectionState.LEADER
    
    def get_current_leader(self) -> Optional[str]:
        """Get the current leader server ID"""
        return self.current_leader
    
    def is_election_in_progress(self) -> bool:
        """Check if election is currently in progress"""
        return self.state == ElectionState.PARTICIPATING
    
    def is_election_timeout(self) -> bool:
        """Check if current election has timed out"""
        if not self.election_start_time:
            return False
        
        return (time.time() - self.election_start_time) > self.election_timeout
    
    def reset_election(self):
        """Reset election state (for timeout or restart)"""
        with self._lock:
            self.state = ElectionState.IDLE
            self.election_id = None
            self.election_start_time = None
            self.received_candidates.clear()
            self.logger.info("Election state reset")
    
    def handle_server_failure(self, failed_server_id: str):
        """Handle failure of a server in the ring"""
        with self._lock:
            # Add to failed servers set
            self.failed_servers.add(failed_server_id)
            self.logger.info(f"Marked {failed_server_id} as failed in ring topology")
            
            # If the failed server was the leader, start new election
            if self.current_leader == failed_server_id:
                self.logger.warning(f"Leader {failed_server_id} failed, starting new election")
                self.current_leader = None
                self.reset_election()
                
                # Add random delay to prevent simultaneous elections from multiple servers
                # Lower position servers get shorter delays (election priority)
                base_delay = 1.0 + (self.ring_position * 0.5)  # 1.0s, 1.5s, 2.0s for positions 0,1,2
                random_delay = base_delay + random.uniform(0, 1.0)  # Add 0-1s random component
                
                self.logger.info(f"Starting election in {random_delay:.2f}s to prevent coordination conflicts")
                
                # Schedule delayed election start
                def delayed_election():
                    time.sleep(random_delay)
                    with self._lock:
                        # Double-check we still need an election
                        if self.current_leader is None and self.state == ElectionState.IDLE:
                            self.start_election()
                        else:
                            self.logger.info("Election no longer needed - leader already established")
                
                election_thread = threading.Thread(target=delayed_election, daemon=True)
                election_thread.start()
            
            # Remove failed server from ring topology (temporary)
            if failed_server_id in self.servers:
                self.logger.info(f"Temporarily removing {failed_server_id} from ring")
                # Note: In production, we'd need proper ring reconfiguration
    
    def handle_server_recovery(self, recovered_server_id: str):
        """Handle recovery of a previously failed server"""
        with self._lock:
            if recovered_server_id in self.failed_servers:
                self.failed_servers.remove(recovered_server_id)
                self.logger.info(f"Marked {recovered_server_id} as recovered in ring topology")
    
    def get_election_status(self) -> Dict[str, Any]:
        """Get current election status for monitoring"""
        with self._lock:
            status = {
                'server_id': self.server_id,
                'ring_position': self.ring_position,
                'state': self.state.value,
                'current_leader': self.current_leader,
                'is_leader': self.is_leader(),
                'election_id': self.election_id,
                'election_in_progress': self.is_election_in_progress(),
                'election_timeout': self.is_election_timeout() if self.election_start_time else False,
                'lamport_timestamp': self.lamport_clock.timestamp,
                'ring_size': self.total_servers,
                'next_neighbor': self.get_next_neighbor(),
                'previous_neighbor': self.get_previous_neighbor()
            }
            
            if self.election_start_time:
                status['election_duration'] = time.time() - self.election_start_time
            
            return status
    
    def force_election(self):
        """Force start a new election (for testing/manual trigger)"""
        self.logger.info("Forcing new election")
        self.reset_election()
        return self.start_election()
    
    def get_ring_topology(self) -> List[Dict[str, Any]]:
        """Get the current ring topology"""
        topology = []
        for server_id, position in sorted(self.servers.items(), key=lambda x: x[1]):
            topology.append({
                'server_id': server_id,
                'position': position,
                'is_current': server_id == self.server_id,
                'is_leader': server_id == self.current_leader
            })
        return topology 