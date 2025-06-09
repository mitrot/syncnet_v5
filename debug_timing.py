#!/usr/bin/env python3
"""Debug timing issue between election and heartbeat failure detection"""
import subprocess
import time
import socket
import json

def get_election_status(port):
    """Get election status from server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(('localhost', port))
        sock.send(json.dumps({'type': 'status'}).encode())
        response = sock.recv(4096)
        sock.close()
        status = json.loads(response.decode())
        return status.get('election_status', {})
    except Exception as e:
        return {'error': str(e)}

def main():
    print('🕐 Timing Analysis: Election vs Heartbeat Detection')
    print('='*60)
    print('Config: Elections start at 8s, Heartbeat failure detection at 20s')
    print('Issue: server2 sends election to server3 before server3 is marked as failed')
    print()
    
    # Start only server2 (server3 will be "down")
    print('🚀 Starting server2 only (server3 remains down)...')
    server2 = subprocess.Popen(['python', 'server/server.py', 'server2'], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Monitor server2's election behavior over time
        for t in range(0, 35, 5):
            time.sleep(5)
            print(f'\n⏰ t={t+5}s:')
            
            status = get_election_status(8011)  # server2's discovery port
            if 'error' not in status:
                next_neighbor = status.get('next_neighbor', 'unknown')
                current_leader = status.get('current_leader', 'None')
                election_state = status.get('state', 'unknown')
                
                print(f'   Election State: {election_state}')
                print(f'   Current Leader: {current_leader}')
                print(f'   Next Neighbor: {next_neighbor}')
                
                if t+5 == 10:
                    print('   📩 Election should have started at t=8s')
                    if next_neighbor == 'server3':
                        print('   ❌ server2 is still trying to send to server3 (not yet failed)')
                    else:
                        print('   ✅ server2 correctly identified server3 as failed')
                
                elif t+5 == 25:
                    print('   💀 server3 should be marked as failed by now (t=20s)')
                    if next_neighbor == 'server3':
                        print('   ❌ server2 STILL trying to send to server3 (BUG!)')
                    else:
                        print('   ✅ server2 correctly skipping server3')
            else:
                print(f'   Error: {status["error"]}')
    
    except KeyboardInterrupt:
        print('\n⏹️  Analysis interrupted')
    finally:
        print('\n🧹 Cleaning up...')
        server2.terminate()
        time.sleep(1)
        print('   Server stopped')

if __name__ == '__main__':
    main() 