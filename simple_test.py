#!/usr/bin/env python3
"""Simple test to demonstrate 2-server election issue"""
import sys
import os
import subprocess
import time
import socket
import json

# Fix import path
sys.path.insert(0, os.getcwd())

def get_status(port):
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect(('localhost', port))
        s.send(json.dumps({'type': 'status'}).encode())
        data = s.recv(4096)
        s.close()
        return json.loads(data.decode())
    except Exception as e:
        return {'error': str(e)}

def main():
    print('🧪 Clean Test: 2-Server Election (server3 down)')
    print('='*50)
    
    # Set environment for subprocesses
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    
    try:
        print('🚀 Starting server1...')
        server1 = subprocess.Popen([sys.executable, 'server/server.py', 'server1'], 
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(2)
        
        print('🚀 Starting server2...')
        server2 = subprocess.Popen([sys.executable, 'server/server.py', 'server2'], 
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print('⏱️  Waiting 12 seconds for election attempts...')
        time.sleep(12)
        
        print('\n📊 Election Results:')
        
        # Check server1
        status1 = get_status(8010)
        print(f'🖥️  server1:')
        if 'error' not in status1:
            e1 = status1.get('election_status', {})
            print(f'   State: {e1.get("state", "unknown")}')
            print(f'   Leader: {e1.get("current_leader", "None")}')
            print(f'   Next Neighbor: {e1.get("next_neighbor", "unknown")}')
        else:
            print(f'   Error: {status1["error"]}')
        
        # Check server2
        status2 = get_status(8011)
        print(f'🖥️  server2:')
        if 'error' not in status2:
            e2 = status2.get('election_status', {})
            print(f'   State: {e2.get("state", "unknown")}')
            print(f'   Leader: {e2.get("current_leader", "None")}')
            print(f'   Next Neighbor: {e2.get("next_neighbor", "unknown")}')
        else:
            print(f'   Error: {status2["error"]}')
        
        print('\n🎯 Analysis:')
        if 'error' not in status1 and 'error' not in status2:
            leader1 = e1.get('current_leader')
            leader2 = e2.get('current_leader')
            next1 = e1.get('next_neighbor')
            next2 = e2.get('next_neighbor')
            
            if leader1 and leader2 and leader1 == leader2:
                print(f'✅ SUCCESS: Both servers agree on leader: {leader1}')
                print('   The timing fix is working!')
            else:
                print(f'❌ ISSUE: server1 leader={leader1}, server2 leader={leader2}')
                if next2 == 'server3':
                    print('   🔍 server2 is still trying to send to server3 (timing issue)')
                elif next2 == 'server1':
                    print('   🔍 server2 correctly identified to send to server1')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        print('\n🧹 Cleanup...')
        try:
            server1.terminate()
            server2.terminate()
            time.sleep(1)
        except:
            pass
        print('   Done')

if __name__ == '__main__':
    main() 