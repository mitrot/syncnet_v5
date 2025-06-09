#!/usr/bin/env python3
"""Diagnostic test for SyncNet v5 hanging issues"""

import sys
import time
import logging
import threading
sys.path.append('.')

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TimeoutManager:
    """Timeout manager for Windows compatibility"""
    def __init__(self, timeout_seconds):
        self.timeout_seconds = timeout_seconds
        self.timed_out = False
        self.timer = None
    
    def start(self):
        """Start the timeout timer"""
        self.timer = threading.Timer(self.timeout_seconds, self._timeout_callback)
        self.timer.daemon = True
        self.timer.start()
    
    def cancel(self):
        """Cancel the timeout timer"""
        if self.timer:
            self.timer.cancel()
    
    def _timeout_callback(self):
        """Called when timeout occurs"""
        self.timed_out = True
        print(f"\n⏰ Test timed out after {self.timeout_seconds} seconds!")
        print("🛑 Force exiting due to hanging...")
        import os
        os._exit(1)

def test_step_by_step():
    """Test each component step by step"""
    print("🔍 DIAGNOSTIC TEST - Step by Step")
    print("="*50)
    
    # Setup timeout manager (30 seconds total)
    timeout_mgr = TimeoutManager(30)
    timeout_mgr.start()
    
    server = None
    client = None
    
    try:
        # Step 1: Import server
        print("📦 Step 1: Importing server...")
        from server.server import SyncNetServer
        print("✅ Server imported successfully")
        
        # Step 2: Create server instance
        print("🏗️  Step 2: Creating server instance...")
        server = SyncNetServer('server1')
        print("✅ Server instance created")
        
        # Step 3: Start server (with timeout)
        print("🚀 Step 3: Starting server...")
        start_time = time.time()
        
        # Start server in separate thread to detect hangs
        result_container = [None]
        def start_server():
            try:
                result_container[0] = server.start()
            except Exception as e:
                print(f"❌ Server start error: {e}")
                result_container[0] = False
        
        start_thread = threading.Thread(target=start_server)
        start_thread.daemon = True
        start_thread.start()
        start_thread.join(timeout=10)
        
        if start_thread.is_alive():
            print("❌ Server start is hanging!")
            print("   The server.start() method is taking too long")
            print("   This might be due to:")
            print("   - Election process hanging")
            print("   - Socket binding issues")
            print("   - Thread synchronization problems")
            return False
        
        if result_container[0] is None:
            print("❌ Server start returned None")
            return False
        
        if not result_container[0]:
            print("❌ Server failed to start")
            return False
        
        elapsed = time.time() - start_time
        print(f"✅ Server started in {elapsed:.1f}s")
        
        # Step 4: Wait for server to be ready
        print("⏱️  Step 4: Waiting for server readiness...")
        time.sleep(3)
        
        # Step 5: Import client
        print("📦 Step 5: Importing client...")
        from client.syncnet_client import SyncNetClient
        print("✅ Client imported successfully")
        
        # Step 6: Create client
        print("👤 Step 6: Creating client...")
        client = SyncNetClient('testuser')
        print("✅ Client created successfully")
        
        # Step 7: Connect client (with timeout)
        print("🔌 Step 7: Connecting client...")
        
        result_container = [None]
        def connect_client():
            try:
                result_container[0] = client.connect('server1')
            except Exception as e:
                print(f"❌ Client connect error: {e}")
                result_container[0] = False
        
        connect_thread = threading.Thread(target=connect_client)
        connect_thread.daemon = True
        connect_thread.start()
        connect_thread.join(timeout=10)
        
        if connect_thread.is_alive():
            print("❌ Client connection is hanging!")
            print("   The client.connect() method is taking too long")
            print("   This might be due to:")
            print("   - Socket connection timeout")
            print("   - Server not accepting connections")
            print("   - Thread synchronization issues")
            return False
        
        if result_container[0] is None:
            print("❌ Client connect returned None")
            return False
        
        if not result_container[0]:
            print("❌ Client failed to connect")
            return False
        
        if client.is_connected():
            print("✅ Client connected successfully")
        else:
            print("❌ Client reports not connected despite successful connect()")
            return False
        
        # Step 8: Test message sending
        print("💬 Step 8: Testing message...")
        if client.send_chat_message("Test message"):
            print("✅ Message sent successfully")
        else:
            print("❌ Failed to send message")
        
        # Step 9: Check status
        print("📊 Step 9: Checking status...")
        status = client.get_client_status()
        print(f"   Client state: {status['state']}")
        print(f"   Messages sent: {status['messages_sent']}")
        print(f"   Current server: {status['current_server']}")
        
        print("\n🎉 Diagnostic test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        timeout_mgr.cancel()  # Cancel timeout
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        if client:
            try:
                client.disconnect()
                print("   Client disconnected")
            except Exception as e:
                print(f"   Error disconnecting client: {e}")
        
        if server:
            try:
                server.stop()
                print("   Server stopped")
            except Exception as e:
                print(f"   Error stopping server: {e}")

if __name__ == '__main__':
    success = test_step_by_step()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    sys.exit(0 if success else 1) 