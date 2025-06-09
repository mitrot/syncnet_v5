#!/usr/bin/env python3
"""Test LCR Election Fix"""

import sys
import time
import signal
sys.path.append('.')

from server.server import SyncNetServer

def test_election_fix():
    """Test that election now works properly"""
    print("🧪 Testing LCR Election Fix")
    print("="*50)
    
    servers = []
    
    try:
        # Start all three servers
        print("🚀 Starting servers...")
        for server_id in ['server1', 'server2', 'server3']:
            server = SyncNetServer(server_id)
            if server.start():
                servers.append(server)
                print(f"✅ {server_id} started")
            else:
                print(f"❌ Failed to start {server_id}")
                return False
        
        # Wait for election to complete
        print("\n⏱️  Waiting 15 seconds for election completion...")
        time.sleep(15)
        
        # Check election results
        print("\n📊 Election Results:")
        leaders = []
        
        for server in servers:
            election_status = server.election.get_election_status()
            print(f"\n🖥️  {server.server_id}:")
            print(f"   State: {election_status['state']}")
            print(f"   Is Leader: {election_status['is_leader']}")
            print(f"   Current Leader: {election_status['current_leader']}")
            print(f"   Ring Position: {election_status['ring_position']}")
            
            if election_status['is_leader']:
                leaders.append(server.server_id)
        
        # Validate results
        print(f"\n🎯 Analysis:")
        print(f"   Leaders found: {leaders}")
        print(f"   Leader count: {len(leaders)}")
        
        if len(leaders) == 1:
            print(f"✅ SUCCESS: {leaders[0]} is the leader!")
            print("🎉 LCR Election is working properly!")
            return True
        elif len(leaders) == 0:
            print("⚠️  No leader elected (may need more time)")
            
            # Try to get more details
            print("\n🔍 Detailed Status:")
            for server in servers:
                status = server.get_server_status()
                print(f"   {server.server_id}: Elections participated = {status['elections_participated']}")
            
            return False
        else:
            print(f"❌ FAILED: Multiple leaders: {leaders}")
            return False
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
        return False
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        for server in servers:
            try:
                server.stop()
                print(f"   Stopped {server.server_id}")
            except:
                pass

if __name__ == '__main__':
    # Setup signal handler
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run test
    success = test_election_fix()
    if success:
        print("\n🎉 ELECTION FIX TEST PASSED!")
        sys.exit(0)
    else:
        print("\n❌ ELECTION FIX TEST FAILED!")
        sys.exit(1) 