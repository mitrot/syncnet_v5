#!/usr/bin/env python3
"""Test 2-server election scenario"""
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
    print('🧪 Testing 2-Server Election (server3 down)')
    print('='*50)
    
    servers = []
    
    try:
        # Start only server1 and server2  
        print('🚀 Starting server1 and server2...')
        server1 = subprocess.Popen(['python', 'server/server.py', 'server1'], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        servers.append(server1)
        time.sleep(2)
        
        server2 = subprocess.Popen(['python', 'server/server.py', 'server2'], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        servers.append(server2)
        
        # Wait for servers to start and attempt elections
        print('⏱️  Waiting 15 seconds for election attempts...')
        time.sleep(15)
        
        print('📊 Election Results:')
        print()
        
        # Check server1 status
        status1 = get_server_status(8010)
        print(f'🖥️  server1:')
        if 'error' not in status1:
            election_status = status1.get('election_status', {})
            print(f'   State: {election_status.get("state", "unknown")}')
            print(f'   Is Leader: {election_status.get("is_leader", False)}')
            print(f'   Current Leader: {election_status.get("current_leader", "None")}')
            print(f'   Ring Position: {election_status.get("ring_position", "unknown")}')
            print(f'   Next Neighbor: {election_status.get("next_neighbor", "unknown")}')
        else:
            print(f'   Error: {status1["error"]}')
        
        print()
        
        # Check server2 status
        status2 = get_server_status(8011) 
        print(f'🖥️  server2:')
        if 'error' not in status2:
            election_status = status2.get('election_status', {})
            print(f'   State: {election_status.get("state", "unknown")}')
            print(f'   Is Leader: {election_status.get("is_leader", False)}')
            print(f'   Current Leader: {election_status.get("current_leader", "None")}')
            print(f'   Ring Position: {election_status.get("ring_position", "unknown")}')
            print(f'   Next Neighbor: {election_status.get("next_neighbor", "unknown")}')
        else:
            print(f'   Error: {status2["error"]}')
        
        print()
        
        # Analysis
        if 'error' not in status1 and 'error' not in status2:
            leader1 = status1.get('election_status', {}).get('current_leader')
            leader2 = status2.get('election_status', {}).get('current_leader')
            
            print('🎯 Analysis:')
            if leader1 and leader2 and leader1 == leader2:
                print(f'✅ SUCCESS: Both servers agree on leader: {leader1}')
            elif leader1 or leader2:
                print(f'⚠️  PARTIAL: server1 thinks leader is {leader1}, server2 thinks leader is {leader2}')
            else:
                print('❌ FAILURE: No leader elected in 2-server scenario')
                print('   This demonstrates the ring topology issue with failed servers')
        
    except KeyboardInterrupt:
        print('\n⏹️  Test interrupted by user')
    except Exception as e:
        print(f'❌ Error during test: {e}')
    finally:
        print()
        print('🧹 Cleaning up...')
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