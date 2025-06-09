#!/usr/bin/env python3
"""Debug script to test sync functionality"""

import sys
import time
sys.path.append('.')

from server.server import SyncNetServer

def test_sync_behavior():
    """Test the sync behavior directly"""
    print("🔍 Debug: Testing Sync Behavior")
    print("="*50)
    
    servers = []
    
    try:
        # Start only server1 and server2
        print("Starting server1 and server2...")
        for server_id in ['server1', 'server2']:
            server = SyncNetServer(server_id)
            if server.start():
                servers.append(server)
                print(f"✅ {server_id} started")
            else:
                print(f"❌ Failed to start {server_id}")
                return
        
        print("📝 server3 is down (not started)")
        
        # Wait for heartbeat detection
        print("\n⏱️  Waiting 25 seconds for heartbeat failure detection...")
        time.sleep(25)
        
        # Check server statuses
        for server in servers:
            print(f"\n🔍 Debug {server.server_id}:")
            
            # Check heartbeat status
            heartbeat_stats = server.heartbeat.get_heartbeat_statistics()
            print(f"   Heartbeat stats: {heartbeat_stats}")
            
            # Check server statuses
            server_statuses = server.heartbeat.get_server_statuses()
            print(f"   Server statuses: {server_statuses}")
            
            # Check election failed servers
            print(f"   Election failed servers: {server.election.failed_servers}")
            
            # Test sync manually
            print(f"   Calling sync_failed_servers_with_heartbeat...")
            server.election.sync_failed_servers_with_heartbeat(server.heartbeat)
            print(f"   Election failed servers after sync: {server.election.failed_servers}")
            
            # Check next neighbor
            next_neighbor = server.election.get_next_neighbor()
            print(f"   Next neighbor: {next_neighbor}")
            
            print()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🧹 Cleanup...")
        for server in servers:
            try:
                server.stop()
            except:
                pass

if __name__ == '__main__':
    test_sync_behavior() 