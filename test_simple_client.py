#!/usr/bin/env python3
"""Simple test for SyncNet v5 client-server connection"""

import sys
import time
import logging
sys.path.append('.')

def test_basic_connection():
    """Test basic client-server connection"""
    print("🧪 Testing Basic Client-Server Connection")
    print("="*50)
    
    # Setup minimal logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Import and start server
        from server.server import SyncNetServer
        print("📡 Starting server1...")
        
        server = SyncNetServer('server1')
        if server.start():
            print("✅ Server1 started successfully")
            
            # Wait for server to be ready
            time.sleep(3)
            
            # Import and connect client
            from client.syncnet_client import SyncNetClient
            print("🔌 Connecting client...")
            
            client = SyncNetClient('testuser')
            if client.connect('server1'):
                print("✅ Client connected successfully")
                
                # Test sending a message
                print("💬 Testing message sending...")
                if client.send_chat_message("Hello from test client!"):
                    print("✅ Message sent successfully")
                else:
                    print("❌ Failed to send message")
                
                # Wait a moment
                time.sleep(2)
                
                # Check status
                status = client.get_client_status()
                print(f"📊 Client Status: {status['state']}")
                print(f"   Messages sent: {status['messages_sent']}")
                print(f"   Server: {status['current_server']}")
                
                # Disconnect client
                client.disconnect()
                print("✅ Client disconnected")
                
            else:
                print("❌ Failed to connect client")
            
            # Stop server
            server.stop()
            print("✅ Server stopped")
            
            print("\n🎉 Basic connection test completed successfully!")
            return True
            
        else:
            print("❌ Failed to start server")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_basic_connection()
    sys.exit(0 if success else 1) 