#!/usr/bin/env python3
"""Clean test to demonstrate election behavior differences"""

import sys
import time
import signal
sys.path.append('.')

from server.server import SyncNetServer

def test_3_servers():
    """Test 3-server election (working case)"""
    print("🧪 Test 1: 3-Server Election (All servers running)")
    print("="*60)
    
    servers = []
    
    try:
        # Start all three servers
        print("🚀 Starting all servers...")
        for server_id in ['server1', 'server2', 'server3']:
            server = SyncNetServer(server_id)
            if server.start():
                servers.append(server)
                print(f"✅ {server_id} started")
            else:
                print(f"❌ Failed to start {server_id}")
                return False
        
        # Wait for election
        print("\n⏱️  Waiting 12 seconds for election...")
        time.sleep(12)
        
        # Check results
        print("\n📊 Results:")
        leaders = []
        
        for server in servers:
            election_status = server.election.get_election_status()
            print(f"   {server.server_id}: state={election_status['state']}, leader={election_status['current_leader']}")
            
            if election_status['is_leader']:
                leaders.append(server.server_id)
        
        if len(leaders) == 1:
            print(f"✅ SUCCESS: {leaders[0]} is the leader!")
            return True
        else:
            print(f"❌ Issue: {len(leaders)} leaders found")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Cleanup
        print("🧹 Stopping servers...")
        for server in servers:
            try:
                server.stop()
            except:
                pass


def test_2_servers():
    """Test 2-server election (problematic case)"""
    print("\n🧪 Test 2: 2-Server Election (server3 down)")
    print("="*60)
    
    servers = []
    
    try:
        # Start only server1 and server2
        print("🚀 Starting server1 and server2...")
        for server_id in ['server1', 'server2']:
            server = SyncNetServer(server_id)
            if server.start():
                servers.append(server)
                print(f"✅ {server_id} started")
            else:
                print(f"❌ Failed to start {server_id}")
                return False
        
        print("📝 server3 remains DOWN (simulating failure)")
        
        # Monitor election behavior over time
        print("\n⏱️  Monitoring election behavior...")
        
        for t in [5, 10, 15, 20]:
            time.sleep(5)
            print(f"\n📊 Status at t={t}s:")
            
            for server in servers:
                election_status = server.election.get_election_status()
                next_neighbor = election_status['next_neighbor']
                state = election_status['state']
                leader = election_status['current_leader']
                
                print(f"   {server.server_id}: state={state}, leader={leader}, next_neighbor={next_neighbor}")
                
                # Key analysis points
                if t == 10 and server.server_id == 'server2':
                    if next_neighbor == 'server3':
                        print("   ❌ TIMING ISSUE: server2 still trying to send to server3!")
                    elif next_neighbor == 'server1':
                        print("   ✅ FIX WORKING: server2 correctly sending to server1")
                
                if t == 20:
                    print(f"   📝 t=20s: Heartbeat should have detected server3 as failed")
        
        # Final analysis
        print(f"\n🎯 Final Analysis:")
        leaders = []
        for server in servers:
            election_status = server.election.get_election_status()
            if election_status['is_leader']:
                leaders.append(server.server_id)
        
        if len(leaders) == 1:
            print(f"✅ SUCCESS: {leaders[0]} became leader in 2-server scenario!")
            print("   The timing fix is working correctly.")
            return True
        elif len(leaders) == 0:
            print("❌ FAILURE: No leader elected in 2-server scenario")
            print("   This demonstrates the timing issue between election and heartbeat detection")
            
            # Show the issue
            for server in servers:
                election_status = server.election.get_election_status()
                next_neighbor = election_status['next_neighbor']
                if server.server_id == 'server2' and next_neighbor == 'server3':
                    print(f"   🔍 ROOT CAUSE: {server.server_id} is still trying to send to server3 (failed server)")
            
            return False
        else:
            print(f"❌ Multiple leaders: {leaders}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Cleanup
        print("🧹 Stopping servers...")
        for server in servers:
            try:
                server.stop()
            except:
                pass


def main():
    """Run both tests to demonstrate the difference"""
    print("🔬 SyncNet v5 Election Behavior Analysis")
    print("="*70)
    print("Demonstrating the difference between working and failing elections")
    print()
    
    # Test 3-server election (should work)
    success1 = test_3_servers()
    
    # Brief pause between tests
    time.sleep(2)
    
    # Test 2-server election (problematic)
    success2 = test_2_servers()
    
    # Summary
    print("\n" + "="*70)
    print("📋 SUMMARY:")
    print(f"   3-Server Election: {'✅ WORKING' if success1 else '❌ FAILED'}")
    print(f"   2-Server Election: {'✅ WORKING' if success2 else '❌ FAILED'}")
    
    if success1 and not success2:
        print("\n🎯 KEY INSIGHT:")
        print("   The timing mismatch between election start (8s) and")
        print("   heartbeat failure detection (20s) causes 2-server elections to fail.")
        print("   The fix should synchronize failed server status before elections start.")
    elif success1 and success2:
        print("\n🎉 EXCELLENT: Both scenarios working - the timing fix is successful!")
    

if __name__ == '__main__':
    # Setup signal handler
    def signal_handler(signum, frame):
        print(f"\n🛑 Interrupted")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    main() 