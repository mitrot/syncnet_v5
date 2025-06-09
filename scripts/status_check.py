#!/usr/bin/env python3
"""SyncNet v5 Cluster Status Monitor"""
import socket
import json
import time
import sys
import threading
import os
from typing import Dict, List, Any

# Add parent directory for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

from common.config import DEFAULT_SERVER_CONFIGS

class ClusterMonitor:
    """Real-time cluster monitoring and health checking"""
    
    def __init__(self):
        self.server_configs = {
            config.server_id: config for config in DEFAULT_SERVER_CONFIGS
        }
        
    def check_server_status(self, server_id: str) -> Dict[str, Any]:
        """Check individual server status with detailed health metrics"""
        config = self.server_configs.get(server_id)
        if not config:
            return {'server_id': server_id, 'status': 'unknown', 'error': 'Invalid server ID'}
        
        try:
            # Connect to server TCP port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((config.host, config.tcp_port))
            
            if result == 0:
                # Server is reachable, try to get detailed status
                try:
                    # Send status request (simple protocol)
                    status_request = json.dumps({
                        'type': 'status',
                        'timestamp': time.time()
                    })
                    sock.send(status_request.encode())
                    
                    # Try to receive response (with timeout)
                    sock.settimeout(1.0)
                    response_data = sock.recv(4096)
                    
                    if response_data:
                        try:
                            response = json.loads(response_data.decode())
                            # Server responded with detailed status
                            return {
                                'server_id': server_id,
                                'status': 'online',
                                'detailed': True,
                                'is_leader': response.get('is_leader', False),
                                'uptime': response.get('uptime', 0),
                                'connected_clients': response.get('connected_clients', 0),
                                'messages_processed': response.get('messages_processed', 0),
                                'tcp_port': config.tcp_port,
                                'heartbeat_port': config.heartbeat_port
                            }
                        except json.JSONDecodeError:
                            pass
                    
                except:
                    pass
                finally:
                    sock.close()
                
                # Server is reachable but no detailed status
                return {
                    'server_id': server_id,
                    'status': 'online',
                    'detailed': False,
                    'is_leader': False,
                    'tcp_port': config.tcp_port,
                    'heartbeat_port': config.heartbeat_port
                }
            else:
                return {
                    'server_id': server_id,
                    'status': 'offline',
                    'detailed': False,
                    'is_leader': False,
                    'tcp_port': config.tcp_port,
                    'error': f'Connection failed (code: {result})'
                }
                
        except Exception as e:
            return {
                'server_id': server_id,
                'status': 'error',
                'detailed': False,
                'is_leader': False,
                'error': str(e)
            }
    
    def get_cluster_status(self) -> List[Dict[str, Any]]:
        """Get status of all servers in parallel"""
        statuses = []
        threads = []
        results = {}
        
        def check_server(server_id):
            results[server_id] = self.check_server_status(server_id)
        
        # Start parallel status checks
        for server_id in self.server_configs.keys():
            thread = threading.Thread(target=check_server, args=(server_id,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        # Wait for all checks to complete (max 5 seconds)
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Collect results in order
        for server_id in sorted(self.server_configs.keys()):
            statuses.append(results.get(server_id, {
                'server_id': server_id,
                'status': 'timeout',
                'detailed': False,
                'is_leader': False,
                'error': 'Status check timed out'
            }))
        
        return statuses
    
    def print_cluster_status(self, show_details: bool = False):
        """Print formatted cluster status table"""
        statuses = self.get_cluster_status()
        
        print("=" * 70)
        print("🌐 SyncNet v5 Cluster Status Monitor")
        print("=" * 70)
        print(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Header
        if show_details:
            print(f"{'Server':<10} {'Status':<12} {'Leader':<8} {'Uptime':<8} {'Clients':<8} {'Messages':<10} {'Ports':<12}")
            print("-" * 70)
        else:
            print(f"{'Server':<10} {'Status':<15} {'Leader':<8} {'TCP Port':<10} {'Notes':<20}")
            print("-" * 70)
        
        # Server status rows
        online_count = 0
        leader_count = 0
        
        for status in statuses:
            server_id = status['server_id']
            is_online = status['status'] == 'online'
            is_leader = status.get('is_leader', False)
            
            if is_online:
                online_count += 1
            if is_leader:
                leader_count += 1
            
            # Status indicators
            if status['status'] == 'online':
                status_str = "✅ ONLINE"
            elif status['status'] == 'offline':
                status_str = "❌ OFFLINE"
            elif status['status'] == 'error':
                status_str = "🚨 ERROR"
            else:
                status_str = "⏱️  TIMEOUT"
            
            leader_str = "🏆 YES" if is_leader else "   NO"
            
            if show_details and status.get('detailed'):
                uptime = f"{status.get('uptime', 0):.1f}s"
                clients = str(status.get('connected_clients', 0))
                messages = str(status.get('messages_processed', 0))
                ports = f"{status.get('tcp_port', 'N/A')}/{status.get('heartbeat_port', 'N/A')}"
                
                print(f"{server_id:<10} {status_str:<12} {leader_str:<8} {uptime:<8} {clients:<8} {messages:<10} {ports:<12}")
            else:
                tcp_port = status.get('tcp_port', 'N/A')
                error_msg = status.get('error', '')[:18] if status.get('error') else ''
                
                print(f"{server_id:<10} {status_str:<15} {leader_str:<8} {tcp_port:<10} {error_msg:<20}")
        
        print("-" * 70)
        
        # Summary and health assessment
        total_servers = len(statuses)
        print(f"📊 Summary: {online_count}/{total_servers} servers online, {leader_count} leader(s)")
        
        # Health assessment
        if online_count == total_servers and leader_count == 1:
            print("💚 Cluster Status: HEALTHY - All servers online with single leader")
        elif online_count == 0:
            print("💀 Cluster Status: DOWN - No servers responding")
        elif leader_count == 0:
            print("⚠️  Cluster Status: NO LEADER - Election may be in progress")
        elif leader_count > 1:
            print("🚨 Cluster Status: SPLIT BRAIN - Multiple leaders detected!")
        elif online_count < total_servers:
            print(f"⚠️  Cluster Status: DEGRADED - {total_servers - online_count} server(s) offline")
        
        print("=" * 70)
        
        return {
            'online_count': online_count,
            'total_count': total_servers,
            'leader_count': leader_count,
            'healthy': online_count == total_servers and leader_count == 1
        }
    
    def monitor_continuously(self, interval: int = 5):
        """Continuously monitor cluster status"""
        print("🔄 Starting continuous monitoring (Ctrl+C to stop)")
        print(f"🕐 Update interval: {interval} seconds")
        print()
        
        try:
            while True:
                self.print_cluster_status(show_details=True)
                print()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")

def main():
    """Main CLI interface"""
    monitor = ClusterMonitor()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'status':
            # One-time status check
            result = monitor.print_cluster_status(show_details=True)
            sys.exit(0 if result['healthy'] else 1)
            
        elif command == 'watch':
            # Continuous monitoring
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            monitor.monitor_continuously(interval)
            
        elif command == 'simple':
            # Simple status check
            monitor.print_cluster_status(show_details=False)
            
        else:
            print("❌ Unknown command:", command)
            print("Usage: python status_check.py [status|watch|simple] [interval]")
            sys.exit(1)
    else:
        # Default: one-time detailed status
        result = monitor.print_cluster_status(show_details=True)
        sys.exit(0 if result['healthy'] else 1)

if __name__ == '__main__':
    main() 