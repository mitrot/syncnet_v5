#!/usr/bin/env python3
"""Test SyncNet v5 Client Implementation - Phase 3A"""

import sys
import time
import threading
import signal
import logging
sys.path.append('.')

from server.server import SyncNetServer
from client.syncnet_client import SyncNetClient

class ClientTestSuite:
    """Test suite for SyncNet v5 client functionality"""
    
    def __init__(self):
        self.servers = []
        self.clients = []
        self.running = True
        
        # Setup logging to reduce noise
        logging.basicConfig(level=logging.WARNING)
        
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
        """Test 1: Start distributed servers"""
        print("\n" + "="*60)
        print("🚀 TEST 1: Starting Distributed Servers")
        print("="*60)
        
        server_ids = ['server1', 'server2', 'server3']
        
        for server_id in server_ids:
            print(f"📡 Starting {server_id}...")
            server = SyncNetServer(server_id)
            
            if server.start():
                self.servers.append(server)
                print(f"✅ {server_id} started successfully")
            else:
                print(f"❌ Failed to start {server_id}")
                return False
        
        # Wait for servers to establish heartbeats and elect leader
        print("⏱️  Waiting 8 seconds for server initialization...")
        time.sleep(8)
        
        print(f"🎉 All {len(self.servers)} servers started and initialized!")
        return True
    
    def test_2_client_connection(self):
        """Test 2: Client connection to servers"""
        print("\n" + "="*60)
        print("🔌 TEST 2: Client Connection")
        print("="*60)
        
        # Test connecting to different servers
        test_users = [
            ('alice', 'server1'),
            ('bob', 'server2'),
            ('charlie', 'server3')
        ]
        
        for username, server_id in test_users:
            print(f"\n👤 Connecting {username} to {server_id}...")
            
            client = SyncNetClient(username, preferred_server=server_id)
            
            if client.connect(server_id):
                self.clients.append(client)
                print(f"✅ {username} connected to {server_id}")
                
                # Wait a moment for join message to process
                time.sleep(1)
                
                # Check client status
                status = client.get_client_status()
                print(f"   Status: {status['state']}")
                print(f"   Server: {status['current_server']}")
                print(f"   Client ID: {status['client_id']}")
            else:
                print(f"❌ Failed to connect {username} to {server_id}")
                return False
        
        print(f"\n🎉 All {len(self.clients)} clients connected successfully!")
        return True
    
    def test_3_message_exchange(self):
        """Test 3: Message exchange between clients"""
        print("\n" + "="*60)
        print("💬 TEST 3: Message Exchange")
        print("="*60)
        
        if len(self.clients) < 2:
            print("❌ Need at least 2 clients for message testing")
            return False
        
        # Test messages from different clients
        test_messages = [
            (0, "Hello everyone! This is Alice."),
            (1, "Hi Alice! Bob here from server2."),
            (2, "Charlie checking in from server3!"),
            (0, "Great to see the distributed chat working!"),
            (1, "The leader election seems to be working well."),
            (2, "Messages are being synchronized across servers!")
        ]
        
        print("📝 Sending test messages...")
        
        for client_idx, message in test_messages:
            if client_idx < len(self.clients):
                client = self.clients[client_idx]
                username = client.username
                
                print(f"   📤 {username}: {message}")
                
                if client.send_chat_message(message):
                    print(f"      ✅ Message sent successfully")
                else:
                    print(f"      ❌ Failed to send message")
                    return False
                
                time.sleep(1)  # Small delay between messages
        
        # Wait for message propagation
        print("\n⏱️  Waiting 3 seconds for message propagation...")
        time.sleep(3)
        
        # Check message statistics
        print("\n📊 Message Statistics:")
        for client in self.clients:
            status = client.get_client_status()
            print(f"   {client.username}:")
            print(f"     Messages sent: {status['messages_sent']}")
            print(f"     Messages received: {status['messages_received']}")
        
        return True
    
    def test_4_server_status_requests(self):
        """Test 4: Server status requests from clients"""
        print("\n" + "="*60)
        print("📊 TEST 4: Server Status Requests")
        print("="*60)
        
        if not self.clients:
            print("❌ No clients available for status testing")
            return False
        
        # Request status from each client
        for i, client in enumerate(self.clients):
            print(f"\n🔍 Requesting status from {client.username}...")
            
            if client.request_status():
                print(f"✅ Status request sent successfully")
                time.sleep(2)  # Wait for response
            else:
                print(f"❌ Failed to send status request")
                return False
        
        return True
    
    def test_5_client_failover(self):
        """Test 5: Client failover when server goes down"""
        print("\n" + "="*60)
        print("🔄 TEST 5: Client Failover")
        print("="*60)
        
        if len(self.servers) < 2 or len(self.clients) < 1:
            print("❌ Need at least 2 servers and 1 client for failover testing")
            return False
        
        # Pick a client and its current server
        test_client = self.clients[0]
        current_server_id = test_client.current_server.server_id if test_client.current_server else None
        
        if not current_server_id:
            print("❌ Test client not connected to any server")
            return False
        
        print(f"🎯 Testing failover for {test_client.username} on {current_server_id}")
        
        # Find and stop the server
        target_server = None
        for server in self.servers:
            if server.server_id == current_server_id:
                target_server = server
                break
        
        if not target_server:
            print(f"❌ Could not find server {current_server_id}")
            return False
        
        print(f"⏹️  Stopping {current_server_id}...")
        target_server.stop()
        
        # Wait for client to detect failure and reconnect
        print("⏱️  Waiting 10 seconds for failover detection...")
        time.sleep(10)
        
        # Check if client reconnected
        if test_client.is_connected():
            new_server_id = test_client.current_server.server_id if test_client.current_server else None
            print(f"✅ Client successfully failed over to {new_server_id}")
            
            # Test sending a message after failover
            if test_client.send_chat_message("Testing message after server failover"):
                print("✅ Message sent successfully after failover")
            else:
                print("⚠️  Failed to send message after failover")
        else:
            print("⚠️  Client did not reconnect after server failure")
            return False
        
        # Restart the failed server
        print(f"\n🔄 Restarting {current_server_id}...")
        if target_server.start():
            print(f"✅ {current_server_id} restarted successfully")
            time.sleep(5)  # Wait for server to rejoin cluster
        else:
            print(f"⚠️  Failed to restart {current_server_id}")
        
        return True
    
    def test_6_multiple_client_simulation(self):
        """Test 6: Multiple clients chatting simultaneously"""
        print("\n" + "="*60)
        print("🎭 TEST 6: Multiple Client Simulation")
        print("="*60)
        
        # Create additional temporary clients
        temp_clients = []
        temp_usernames = ['david', 'emma', 'frank']
        
        print("🔌 Connecting additional clients...")
        for username in temp_usernames:
            client = SyncNetClient(username)
            if client.connect():
                temp_clients.append(client)
                print(f"✅ {username} connected")
                time.sleep(1)
            else:
                print(f"❌ Failed to connect {username}")
        
        all_clients = self.clients + temp_clients
        
        # Simulate concurrent messaging
        print(f"\n💬 Simulating {len(all_clients)} clients chatting...")
        
        def send_messages(client, message_count=3):
            """Send multiple messages from a client"""
            for i in range(message_count):
                message = f"Message {i+1} from {client.username}"
                client.send_chat_message(message)
                time.sleep(0.5)
        
        # Start messaging threads
        threads = []
        for client in all_clients:
            thread = threading.Thread(target=send_messages, args=(client, 2))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Wait for message propagation
        print("⏱️  Waiting 5 seconds for message propagation...")
        time.sleep(5)
        
        # Display final statistics
        print("\n📊 Final Client Statistics:")
        for client in all_clients:
            status = client.get_client_status()
            print(f"   {client.username}: Sent={status['messages_sent']}, Received={status['messages_received']}")
        
        # Cleanup temporary clients
        print("\n🧹 Disconnecting temporary clients...")
        for client in temp_clients:
            client.disconnect()
            print(f"   Disconnected {client.username}")
        
        return True
    
    def run_all_tests(self):
        """Run complete client test suite"""
        self.setup_signal_handlers()
        
        print("🚀 SYNCNET V5 CLIENT TEST SUITE - PHASE 3A")
        print("="*60)
        
        test_results = {}
        
        try:
            # Run tests sequentially
            test_results['server_startup'] = self.test_1_server_startup()
            if not test_results['server_startup']:
                print("❌ Server startup failed, aborting tests")
                return
            
            test_results['client_connection'] = self.test_2_client_connection()
            test_results['message_exchange'] = self.test_3_message_exchange()
            test_results['status_requests'] = self.test_4_server_status_requests()
            test_results['client_failover'] = self.test_5_client_failover()
            test_results['multiple_clients'] = self.test_6_multiple_client_simulation()
            
            # Summary
            print("\n" + "="*60)
            print("📋 CLIENT TEST RESULTS SUMMARY")
            print("="*60)
            
            passed = sum(test_results.values())
            total = len(test_results)
            
            for test_name, result in test_results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {test_name.upper().replace('_', ' ')}: {status}")
            
            print(f"\n🎯 OVERALL: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 ALL CLIENT TESTS PASSED!")
                print("✅ Phase 3A: Client Implementation is working perfectly!")
                print("🌟 SyncNet v5 distributed chat system is fully operational!")
            else:
                print("⚠️  Some client tests failed - implementation may need fixes")
                
        except KeyboardInterrupt:
            print("\n⏹️  Tests interrupted by user")
        except Exception as e:
            print(f"\n❌ Test error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up all clients and servers"""
        print("\n🧹 Cleaning up clients and servers...")
        
        # Disconnect clients
        for client in self.clients:
            try:
                client.disconnect()
                print(f"   Disconnected client {client.username}")
            except Exception as e:
                print(f"   Error disconnecting {client.username}: {e}")
        
        # Stop servers
        for server in self.servers:
            try:
                server.stop()
                print(f"   Stopped {server.server_id}")
            except Exception as e:
                print(f"   Error stopping {server.server_id}: {e}")
        
        self.clients.clear()
        self.servers.clear()
        print("✅ Cleanup complete")

if __name__ == '__main__':
    suite = ClientTestSuite()
    suite.run_all_tests() 