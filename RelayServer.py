import socket
import threading
import json
import time
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('relay_server')

class RelayServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.peers = {}  # Dictionary to store registered peers {peer_id: {ip, port, last_active}}
        self.connections = {}  # Active connections {peer_id: connection}
        self.running = True
        
        # Setup server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        # Start maintenance thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_inactive_peers)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        logger.info(f"Relay server started on {self.host}:{self.port}")
    
    def start(self):
        """Start accepting connections"""
        try:
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_handler = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address)
                    )
                    client_handler.daemon = True
                    client_handler.start()
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Server shutdown initiated")
        finally:
            self.shutdown()
    
    def _handle_client(self, client_socket, address):
        """Handle client connection and messages"""
        peer_id = None
        try:
            logger.info(f"New connection from {address}")
            client_socket.settimeout(60)  # 60 second timeout
            
            while self.running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    
                    message = json.loads(data.decode('utf-8'))
                    command = message.get('command')
                    
                    if command == 'register':
                        # Register a new peer
                        peer_id = str(uuid.uuid4())
                        self.peers[peer_id] = {
                            'ip': message.get('ip'),
                            'port': message.get('port'),
                            'last_active': time.time()
                        }
                        self.connections[peer_id] = client_socket
                        
                        response = {
                            'status': 'success',
                            'peer_id': peer_id
                        }
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                        logger.info(f"Registered peer {peer_id} at {message.get('ip')}:{message.get('port')}")
                    
                    elif command == 'heartbeat':
                        # Update last active time for peer
                        peer_id = message.get('peer_id')
                        if peer_id in self.peers:
                            self.peers[peer_id]['last_active'] = time.time()
                            response = {'status': 'success'}
                        else:
                            response = {'status': 'error', 'message': 'Peer not registered'}
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
                    elif command == 'get_peers':
                        # Return list of active peers
                        peer_id = message.get('peer_id')
                        if peer_id in self.peers:
                            self.peers[peer_id]['last_active'] = time.time()
                            
                            # Filter out requesting peer and format for response
                            peer_list = []
                            for pid, info in self.peers.items():
                                if pid != peer_id:
                                    peer_list.append({
                                        'peer_id': pid,
                                        'ip': info['ip'],
                                        'port': info['port']
                                    })
                            
                            response = {
                                'status': 'success',
                                'peers': peer_list
                            }
                        else:
                            response = {'status': 'error', 'message': 'Peer not registered'}
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
                    elif command == 'relay_message':
                        # Relay a message to another peer
                        sender_id = message.get('peer_id')
                        target_id = message.get('target_id')
                        content = message.get('content')
                        
                        if sender_id in self.peers and target_id in self.connections:
                            relay_message = {
                                'type': 'relayed',
                                'sender_id': sender_id,
                                'sender_ip': self.peers[sender_id]['ip'],
                                'sender_port': self.peers[sender_id]['port'],
                                'content': content
                            }
                            try:
                                self.connections[target_id].sendall(json.dumps(relay_message).encode('utf-8'))
                                response = {'status': 'success'}
                            except Exception as e:
                                response = {'status': 'error', 'message': f'Failed to relay: {str(e)}'}
                        else:
                            response = {'status': 'error', 'message': 'Invalid peer IDs'}
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                    
                    elif command == 'disconnect':
                        # Peer is disconnecting
                        peer_id = message.get('peer_id')
                        if peer_id in self.peers:
                            logger.info(f"Peer {peer_id} disconnecting")
                            self._remove_peer(peer_id)
                        break
                    
                    else:
                        # Unknown command
                        response = {'status': 'error', 'message': 'Unknown command'}
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                
                except socket.timeout:
                    # Check if peer is still registered
                    if peer_id and peer_id in self.peers:
                        if time.time() - self.peers[peer_id]['last_active'] > 60:
                            break
                    else:
                        break
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {address}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error handling client {address}: {e}")
                    break
        
        finally:
            if peer_id and peer_id in self.peers:
                self._remove_peer(peer_id)
            try:
                client_socket.close()
            except:
                pass
    
    def _remove_peer(self, peer_id):
        """Remove a peer from the registry"""
        if peer_id in self.peers:
            del self.peers[peer_id]
        if peer_id in self.connections:
            try:
                self.connections[peer_id].close()
            except:
                pass
            del self.connections[peer_id]
    
    def _cleanup_inactive_peers(self):
        """Remove peers that haven't sent a heartbeat recently"""
        while self.running:
            current_time = time.time()
            to_remove = []
            
            for peer_id, info in self.peers.items():
                if current_time - info['last_active'] > 120:  # 2 minutes timeout
                    to_remove.append(peer_id)
            
            for peer_id in to_remove:
                logger.info(f"Removing inactive peer {peer_id}")
                self._remove_peer(peer_id)
                
            time.sleep(30)  # Check every 30 seconds
    
    def shutdown(self):
        """Shutdown the relay server"""
        self.running = False
        
        # Close all client connections
        for peer_id in list(self.connections.keys()):
            self._remove_peer(peer_id)
        
        # Close server socket
        try:
            self.server_socket.close()
        except:
            pass
        
        logger.info("Relay server shut down")

if __name__ == "__main__":
    # Change port if needed
    server = RelayServer(port=12345)
    server.start()