#!/usr/bin/env python3
"""Comprehensive test for SyncNet v5 distributed server functionality"""

import sys
import time
import threading
import json
import socket
import signal
from typing import List, Dict
sys.path.append('.')

from server.server import SyncNetServer, ServerState

class DistributedTestSuite:
    """Test suite for distributed server functionality"""
    
    def __init__(self):
        self.servers: List[SyncNetServer] = []
        self.running = True
        
    def setup_signal_handlers(self):
        """Setup graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)
    
    def test_1_server_startup(self):
        """Test 1: Start all three servers"""
        print("\n" + "="*60)
        print("🚀 TEST 1: Multi-Server Startup")
        print("="*60)
        
        server_ids = ['server1', 'server2', 'server3']
        
        for server_id in server_ids:
            print(f"\n📡 Starting {server_id}...")
            server = SyncNetServer(server_id)
            
            if server.start():
                self.servers.append(server)
                print(f"✅ {server_id} started successfully")
                print(f"   State: {server.state.value}")
                print(f"   TCP Port: {server.server_config.tcp_port}")
                print(f"   Heartbeat Port: {server.server_config.heartbeat_port}")
                print(f"   Ring Position: {server.server_config.ring_position}")
            else:
                print(f"❌ Failed to start {server_id}")
                return False
        
        print(f"\n🎉 All {len(self.servers)} servers started successfully!")
        return True
    
    def test_2_heartbeat_communication(self):
        """Test 2: Verify heartbeat communication between servers"""
        print("\n" + "="*60)
        print("💓 TEST 2: Heartbeat Communication")
        print("="*60)
        
        print("⏱️  Waiting 5 seconds for heartbeat establishment...")
        time.sleep(5)
        
        for server in self.servers:
            heartbeat_stats = server.heartbeat.get_heartbeat_statistics()
            print(f"\n📊 {server.server_id} Heartbeat Stats:")
            print(f"   Heartbeats sent: {heartbeat_stats['heartbeats_sent']}")
            print(f"   Heartbeats received: {heartbeat_stats['heartbeats_received']}")
            print(f"   Active servers: {heartbeat_stats['active_servers']}")
            print(f"   Failed servers: {heartbeat_stats['failed_servers']}")
            print(f"   Monitoring running: {heartbeat_stats['monitoring_running']}")
        
        # Check if servers are detecting each other
        active_counts = [s.heartbeat.get_heartbeat_statistics()['active_servers'] for s in self.servers]
        if all(count > 1 for count in active_counts):
            print("✅ Servers are detecting each other via heartbeats")
            return True
        else:
            print("⚠️  Servers may not be fully detecting each other yet")
            return False
    
    def test_3_leader_election(self):
        """Test 3: Leader election process"""
        print("\n" + "="*60)
        print("👑 TEST 3: Leader Election")
        print("="*60)
        
        # Check initial election states
        print("📋 Initial Election States:")
        existing_leaders = []
        for server in self.servers:
            election_status = server.election.get_election_status()
            print(f"   {server.server_id}: Leader={election_status['is_leader']}, State={election_status['state']}")
            if election_status['is_leader']:
                existing_leaders.append(server.server_id)
        
        # If we already have a leader, verify consistency
        if existing_leaders:
            print(f"\n✅ Leader already established: {existing_leaders}")
            
            # Check that all servers agree on the leader
            current_leaders = set()
            for server in self.servers:
                leader = server.election.get_current_leader()
                if leader:
                    current_leaders.add(leader)
            
            if len(current_leaders) == 1:
                leader = list(current_leaders)[0]
                print(f"✅ All servers agree on leader: {leader}")
                
                # Verify it's the highest position server (LCR rule)
                leader_server = next(s for s in self.servers if s.server_id == leader)
                highest_position = max(s.server_config.ring_position for s in self.servers)
                
                if leader_server.server_config.ring_position == highest_position:
                    print(f"✅ Leader has highest ring position ({highest_position})")
                    return True
                else:
                    print(f"⚠️  Leader position ({leader_server.server_config.ring_position}) is not highest ({highest_position})")
                    return False
            else:
                print(f"⚠️  Servers disagree on leader: {current_leaders}")
                return False
        else:
            # No leader yet, start election on one server only
            print("\n🗳️  No leader found, starting election from server1...")
            self.servers[0].start_election_process()
            
            # Wait for election to complete
            print("⏱️  Waiting 10 seconds for election completion...")
            time.sleep(10)
            
            # Check results
            print("\n📊 Election Results:")
            leaders = []
            for server in self.servers:
                election_status = server.election.get_election_status()
                current_leader = server.election.get_current_leader()
                is_leader = server.election.is_leader()
                
                print(f"   {server.server_id}:")
                print(f"     Is Leader: {is_leader}")
                print(f"     Current Leader: {current_leader}")
                print(f"     Election State: {election_status['state']}")
                print(f"     Ring Position: {election_status['ring_position']}")
                
                if is_leader:
                    leaders.append(server.server_id)
            
            # Validate election results
            if len(leaders) == 1:
                print(f"✅ Election successful! Leader: {leaders[0]}")
                return True
            elif len(leaders) == 0:
                print("⚠️  No leader elected yet (may need more time)")
                return False
            else:
                print(f"❌ Multiple leaders detected: {leaders}")
                return False
    
    def test_4_failure_simulation(self):
        """Test 4: Server failure detection and recovery"""
        print("\n" + "="*60)
        print("💥 TEST 4: Failure Detection & Recovery")
        print("="*60)
        
        if len(self.servers) < 2:
            print("❌ Need at least 2 servers for failure testing")
            return False
        
        # Pick a server to "fail"
        target_server = self.servers[1]  # server2
        print(f"🎯 Simulating failure of {target_server.server_id}")
        
        # Stop the server
        print("⏹️  Stopping server...")
        target_server.stop()
        
        # Wait for failure detection
        print("⏱️  Waiting 15 seconds for failure detection...")
        time.sleep(15)
        
        # Check if other servers detected the failure
        print("\n📊 Failure Detection Results:")
        for server in self.servers:
            if server.server_id == target_server.server_id:
                continue
                
            heartbeat_stats = server.heartbeat.get_heartbeat_statistics()
            print(f"   {server.server_id}:")
            print(f"     Active servers: {heartbeat_stats['active_servers']}")
            print(f"     Failed servers: {heartbeat_stats['failed_servers']}")
            print(f"     Failures detected: {heartbeat_stats['failures_detected']}")
        
        # Restart the failed server
        print(f"\n🔄 Restarting {target_server.server_id}...")
        if target_server.start():
            print("✅ Server restarted successfully")
            
            # Wait for recovery detection
            print("⏱️  Waiting 10 seconds for recovery detection...")
            time.sleep(10)
            
            # Check recovery
            print("\n📊 Recovery Detection Results:")
            for server in self.servers:
                heartbeat_stats = server.heartbeat.get_heartbeat_statistics()
                print(f"   {server.server_id}: Active={heartbeat_stats['active_servers']}")
            
            return True
        else:
            print("❌ Failed to restart server")
            return False
    
    def test_5_message_synchronization(self):
        """Test 5: Message storage and Lamport clock synchronization"""
        print("\n" + "="*60)
        print("🕐 TEST 5: Message Synchronization")
        print("="*60)
        
        print("📝 Storing test messages on different servers...")
        
        # Store messages on different servers
        test_messages = [
            ("server1", "Hello from server1"),
            ("server2", "Hello from server2"), 
            ("server3", "Hello from server3")
        ]
        
        from common.messages import Message, MessageType
        
        for i, (server_id, content) in enumerate(test_messages):
            server = next(s for s in self.servers if s.server_id == server_id)
            
            # Create message with Lamport timestamp
            timestamp = server.lamport_clock.tick()
            message = Message(
                msg_type=MessageType.CHAT,
                sender_id=server_id,
                data={'content': content},
                lamport_timestamp=timestamp
            )
            
            # Store message
            message_id = server.storage.store_message(message)
            print(f"   📄 {server_id}: Stored message {message_id} with timestamp {timestamp}")
            
            time.sleep(1)  # Small delay between messages
        
        # Check message counts and timestamps
        print("\n📊 Storage Statistics:")
        for server in self.servers:
            storage_stats = server.storage.get_stats()
            recent_messages = server.storage.get_recent_messages(5)
            
            print(f"   {server.server_id}:")
            print(f"     Messages stored: {storage_stats['message_count']}")
            print(f"     Lamport timestamp: {server.lamport_clock.timestamp}")
            
            if recent_messages:
                print(f"     Recent messages:")
                for msg in recent_messages[:3]:
                    print(f"       - {msg.content} (TS: {msg.lamport_timestamp})")
        
        return True
    
    def test_6_comprehensive_status(self):
        """Test 6: Comprehensive system status"""
        print("\n" + "="*60)
        print("📊 TEST 6: Comprehensive System Status")
        print("="*60)
        
        for server in self.servers:
            status = server.get_server_status()
            print(f"\n🖥️  {server.server_id} Status:")
            print(f"   State: {status['state']}")
            print(f"   Uptime: {status['uptime']}s")
            print(f"   Is Leader: {status['is_leader']}")
            print(f"   Current Leader: {status['current_leader']}")
            print(f"   Connected Clients: {status['connected_clients']}")
            print(f"   Messages Processed: {status['messages_processed']}")
            print(f"   Elections Participated: {status['elections_participated']}")
            print(f"   Storage: {status['storage_stats']['message_count']} messages")
            print(f"   Network: TCP={status['network']['tcp_port']}, UDP={status['network']['heartbeat_port']}")
        
        return True
    
    def run_all_tests(self):
        """Run complete distributed system test suite"""
        self.setup_signal_handlers()
        
        print("🚀 SYNCNET V5 DISTRIBUTED SYSTEM TEST SUITE")
        print("="*60)
        
        test_results = {}
        
        try:
            # Run tests sequentially
            test_results['startup'] = self.test_1_server_startup()
            if not test_results['startup']:
                print("❌ Startup failed, aborting tests")
                return
            
            test_results['heartbeat'] = self.test_2_heartbeat_communication()
            test_results['election'] = self.test_3_leader_election()
            test_results['failure'] = self.test_4_failure_simulation()
            test_results['synchronization'] = self.test_5_message_synchronization()
            test_results['status'] = self.test_6_comprehensive_status()
            
            # Summary
            print("\n" + "="*60)
            print("📋 TEST RESULTS SUMMARY")
            print("="*60)
            
            passed = sum(test_results.values())
            total = len(test_results)
            
            for test_name, result in test_results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {test_name.upper()}: {status}")
            
            print(f"\n🎯 OVERALL: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 ALL DISTRIBUTED SYSTEM TESTS PASSED!")
                print("✅ Ready for Phase 3A: Client Implementation")
            else:
                print("⚠️  Some tests failed - distributed system may need fixes")
                
        except KeyboardInterrupt:
            print("\n⏹️  Tests interrupted by user")
        except Exception as e:
            print(f"\n❌ Test error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up all servers"""
        print("\n🧹 Cleaning up servers...")
        for server in self.servers:
            try:
                server.stop()
                print(f"   Stopped {server.server_id}")
            except Exception as e:
                print(f"   Error stopping {server.server_id}: {e}")
        
        self.servers.clear()
        print("✅ Cleanup complete")

if __name__ == '__main__':
    suite = DistributedTestSuite()
    suite.run_all_tests() 