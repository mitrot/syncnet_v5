#!/usr/bin/env python3
"""Test the timing fix for 2-server elections"""
import subprocess
import time
import socket
import json
import sys

def get_server_status(port):
    """Get server status via TCP"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(('localhost', port))
        sock.send(json.dumps({'type': 'status'}).encode())
        response = sock.recv(4096)
        sock.close()
        return json.loads(response.decode())
    except Exception as e:
        return {'error': str(e)}

def main():
    print('🧪 Testing Timing Fix: 2-Server Election')
    print('='*50)
    print('Scenario: Start server1 and server2, server3 remains down')
    print('Expected: server2 should become leader (higher position)')
    print()
    
    servers = []
    
    try:
        # Start server1 first
        print('🚀 Starting server1...')
        server1 = subprocess.Popen(['python', 'server/server.py', 'server1'])
        servers.append(server1)
        time.sleep(3)
        
        # Start server2 
        print('🚀 Starting server2...')
        server2 = subprocess.Popen(['python', 'server/server.py', 'server2'])
        servers.append(server2)
        time.sleep(3)
        
        print('⏱️  Waiting for servers to initialize and start elections...')
        
        # Monitor for 25 seconds to see election behavior
        for i in range(5):
            time.sleep(5)
            elapsed = (i + 1) * 5
            print(f'\n📊 Status at t={elapsed}s:')
            
            # Check server1
            status1 = get_server_status(8010)
            if 'error' not in status1:
                election1 = status1.get('election_status', {})
                print(f'   server1: {election1.get("state", "unknown")} | Leader: {election1.get("current_leader", "None")} | Next: {election1.get("next_neighbor", "unknown")}')
            else:
                print(f'   server1: Connection failed')
            
            # Check server2
            status2 = get_server_status(8011)
            if 'error' not in status2:
                election2 = status2.get('election_status', {})
                print(f'   server2: {election2.get("state", "unknown")} | Leader: {election2.get("current_leader", "None")} | Next: {election2.get("next_neighbor", "unknown")}')
            else:
                print(f'   server2: Connection failed')
            
            # Analysis at key timing points
            if elapsed == 10:
                print('   📝 Elections should have started (t=8s)')
                if 'error' not in status2:
                    next_neighbor = election2.get('next_neighbor', 'unknown')
                    if next_neighbor == 'server3':
                        print('   ❌ server2 still trying to send to server3 (timing issue)')
                    elif next_neighbor == 'server1':
                        print('   ✅ server2 correctly sending to server1 (fix working)')
            
            elif elapsed == 25:
                print('   📝 Heartbeat should have detected server3 as failed (t=20s)')
                if 'error' not in status1 and 'error' not in status2:
                    leader1 = election1.get('current_leader')
                    leader2 = election2.get('current_leader')
                    if leader1 and leader2 and leader1 == leader2:
                        print(f'   ✅ SUCCESS: Both servers agree on leader: {leader1}')
                    else:
                        print(f'   ❌ FAILURE: No consensus (server1: {leader1}, server2: {leader2})')
        
        print('\n🎯 Final Analysis:')
        status1 = get_server_status(8010)
        status2 = get_server_status(8011)
        
        if 'error' not in status1 and 'error' not in status2:
            leader1 = status1.get('election_status', {}).get('current_leader')
            leader2 = status2.get('election_status', {}).get('current_leader')
            
            if leader1 and leader2 and leader1 == leader2:
                print(f'✅ SUCCESS: 2-server election completed, leader is {leader1}')
                print('   The timing fix is working correctly!')
            else:
                print('❌ FAILURE: 2-server election did not complete successfully')
                print('   The timing issue persists')
        else:
            print('❌ Could not determine final status')
    
    except KeyboardInterrupt:
        print('\n⏹️  Test interrupted by user')
    except Exception as e:
        print(f'❌ Error during test: {e}')
    finally:
        print('\n🧹 Cleaning up...')
        for server in servers:
            try:
                server.terminate()
                server.wait(timeout=3)
            except:
                server.kill()
        time.sleep(1)
        print('   Servers stopped')

if __name__ == '__main__':
    main() 