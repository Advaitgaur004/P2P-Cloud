import socket
import threading
import time
import json
import logging
import random
import uuid
import base64
from P2PPlatform import Network, Peer, Message

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cloud_p2p')

class CloudPeer(Peer):
    """Extended Peer class with cloud identity information"""
    def __init__(self, ip, port=None, connection=None, peer_id=None):
        super().__init__(ip, port, connection)
        self.peer_id = peer_id or str(uuid.uuid4())
        self.relay_only = False  # Flag if we can only communicate via relay
        self.last_heartbeat = time.time()
    
    def __str__(self):
        if self.name:
            return f"{self.name} ({self.ip}:{self.port})"
        return f"{self.ip}:{self.port} [{self.peer_id[:8]}]"

class CloudNetwork(Network):
    """Extended Network class with cloud functionality"""
    def __init__(self, ip, port, relay_server_ip, relay_server_port=12345):
        super().__init__(ip, port)
        
        # Cloud specific attributes
        self.relay_server_ip = relay_server_ip
        self.relay_server_port = relay_server_port
        self.relay_connection = None
        self.peer_id = None
        self.cloud_connected = False
        self.relay_peers = {}  # Peers known through relay {peer_id: CloudPeer}
        
        # Start cloud connection
        self._connect_to_relay()
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        # Start relay receiver thread
        self.relay_receiver_thread = threading.Thread(target=self._relay_receiver)
        self.relay_receiver_thread.daemon = True
        self.relay_receiver_thread.start()
    
    def _connect_to_relay(self):
        """Connect to relay server and register this peer"""
        try:
            # Create a socket connection to the relay server
            self.relay_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.relay_connection.connect((self.relay_server_ip, self.relay_server_port))
            
            # Register with relay server
            registration = {
                'command': 'register',
                'ip': self.ip,
                'port': self.port
            }
            self.relay_connection.sendall(json.dumps(registration).encode('utf-8'))
            
            # Get response
            response = json.loads(self.relay_connection.recv(4096).decode('utf-8'))
            if response.get('status') == 'success':
                self.peer_id = response.get('peer_id')
                self.cloud_connected = True
                logger.info(f"Connected to relay server. Assigned ID: {self.peer_id}")
                self._alert(Message(f"Connected to cloud relay at {self.relay_server_ip}:{self.relay_server_port}"))
                return True
            else:
                logger.error(f"Failed to register with relay server: {response.get('message')}")
                self._alert(Message(f"Failed to connect to cloud relay: {response.get('message')}"))
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to relay server: {e}")
            self._alert(Message(f"Failed to connect to cloud relay: {e}"))
            self.relay_connection = None
            return False
    
    def _heartbeat_loop(self):
        """Send regular heartbeats to the relay server"""
        while self.running and self.cloud_connected:
            try:
                if self.relay_connection and self.peer_id:
                    heartbeat = {
                        'command': 'heartbeat',
                        'peer_id': self.peer_id
                    }
                    self.relay_connection.sendall(json.dumps(heartbeat).encode('utf-8'))
                    
                    # Update peer list every 5 heartbeats
                    if random.random() < 0.2:  # 20% chance per heartbeat
                        self._get_relay_peers()
                
                time.sleep(30)  # Heartbeat every 30 seconds
                
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                # Try to reconnect
                self.cloud_connected = False
                time.sleep(5)
                self._connect_to_relay()
    
    def _relay_receiver(self):
        """Handle messages from the relay server"""
        while self.running:
            if not self.cloud_connected or not self.relay_connection:
                time.sleep(1)
                continue
                
            try:
                self.relay_connection.settimeout(1.0)
                data = self.relay_connection.recv(4096)
                if not data:
                    logger.warning("Lost connection to relay server")
                    self.cloud_connected = False
                    time.sleep(5)
                    self._connect_to_relay()
                    continue
                
                message = json.loads(data.decode('utf-8'))
                
                # Handle relayed message
                if message.get('type') == 'relayed':
                    sender_id = message.get('sender_id')
                    content = message.get('content')
                    sender_ip = message.get('sender_ip')
                    sender_port = message.get('sender_port')
                    
                    # Create/update peer info
                    if sender_id not in self.relay_peers:
                        # Create new peer
                        peer = CloudPeer(sender_ip, sender_port, None, sender_id)
                        peer.relay_only = True
                        self.relay_peers[sender_id] = peer
                    
                    # Alert about the message
                    relay_peer = self.relay_peers[sender_id]
                    relay_peer.last_heartbeat = time.time()
                    
                    # Handle special messages
                    if isinstance(content, dict) and content.get('type') == 'file_transfer':
                        # Handle file transfer
                        file_content = base64.b64decode(content.get('data'))
                        file_name = content.get('filename')
                        self._alert(Message(f"Received file {file_name} via relay"))
                        # Assuming the Interface will handle this
                        self._alert(Message(file_content), str(relay_peer))
                    else:
                        # Regular message
                        self._alert(Message(content), str(relay_peer))
                
            except socket.timeout:
                # This is expected, just continue
                pass
            except Exception as e:
                logger.error(f"Error receiving from relay: {e}")
                time.sleep(1)
    
    def _get_relay_peers(self):
        """Get list of peers from relay server"""
        if not self.cloud_connected:
            return
            
        try:
            # Request peer list
            peer_request = {
                'command': 'get_peers',
                'peer_id': self.peer_id
            }
            self.relay_connection.sendall(json.dumps(peer_request).encode('utf-8'))
            
            # Get response (with short timeout)
            self.relay_connection.settimeout(5.0)
            response = json.loads(self.relay_connection.recv(4096).decode('utf-8'))
            self.relay_connection.settimeout(None)
            
            if response.get('status') == 'success':
                peers = response.get('peers', [])
                for peer_info in peers:
                    peer_id = peer_info.get('peer_id')
                    ip = peer_info.get('ip')
                    port = peer_info.get('port')
                    
                    # Add to relay peers if new
                    if peer_id not in self.relay_peers:
                        peer = CloudPeer(ip, port, None, peer_id)
                        peer.relay_only = True  # Start with relay only until direct connection verified
                        self.relay_peers[peer_id] = peer
                        logger.info(f"Discovered new peer via relay: {peer}")
                
        except Exception as e:
            logger.error(f"Error getting peers from relay: {e}")
    
    def connect_to_cloud_peer(self, peer_id):
        """Connect to a peer known through the relay"""
        if peer_id not in self.relay_peers:
            self._alert(Message(f"Unknown peer ID: {peer_id}"))
            return False
            
        peer = self.relay_peers[peer_id]
        
        # Try direct connection first
        try:
            # Create a socket and connect to the peer
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)  # Short timeout for connection attempt
            client_socket.connect((peer.ip, peer.port))
            client_socket.settimeout(None)
            
            # Update peer connection
            peer.connection = client_socket
            peer.relay_only = False
            
            # Move from relay_peers to peerList if not already there
            if peer not in self.peerList:
                self.peerList.append(peer)
                
            self._alert(Message(f"Connected directly to {peer}"))
            return True
            
        except Exception as e:
            logger.warning(f"Direct connection to {peer} failed: {e}")
            self._alert(Message(f"Direct connection to {peer} failed, will use relay"))
            
            # Add to peer list anyway, we'll use relay
            if peer not in self.peerList:
                self.peerList.append(peer)
                
            return False
    
    def send_via_relay(self, peer_id, content):
        """Send a message through the relay server"""
        if not self.cloud_connected:
            logger.warning("Cannot send via relay: not connected")
            return False
            
        try:
            relay_message = {
                'command': 'relay_message',
                'peer_id': self.peer_id,
                'target_id': peer_id,
                'content': content
            }
            self.relay_connection.sendall(json.dumps(relay_message).encode('utf-8'))
            return True
            
        except Exception as e:
            logger.error(f"Error sending via relay: {e}")
            return False
    
    def send_file_via_relay(self, peer_id, file_content, filename):
        """Send a file through the relay server"""
        # Encode the file content to base64
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        # Create a file transfer message
        file_message = {
            'type': 'file_transfer',
            'filename': filename,
            'data': encoded_content
        }
        
        return self.send_via_relay(peer_id, file_message)
    
    def sender(self, message):
        """Override sender to handle relay-only peers"""
        if not message:
            return
            
        # Handle standard peers with direct connection
        super().sender(message)
        
        # Additionally, send to relay-only peers
        for peer_id, peer in self.relay_peers.items():
            if peer.relay_only and peer in self.peerList:
                self.send_via_relay(peer_id, message)
    
    def list_cloud_peers(self):
        """Return a list of discovered cloud peers"""
        return list(self.relay_peers.values())
    
    def shutdown(self):
        """Override shutdown to handle cloud resources"""
        if self.cloud_connected:
            try:
                # Notify relay we're disconnecting
                disconnect_msg = {
                    'command': 'disconnect',
                    'peer_id': self.peer_id
                }
                self.relay_connection.sendall(json.dumps(disconnect_msg).encode('utf-8'))
                self.relay_connection.close()
            except:
                pass
            
        self.cloud_connected = False
        super().shutdown()# CloudP2PPlatform.py
import socket
import threading
import time
import json
import logging
import random
import uuid
import base64
from P2PPlatform import Network, Peer, Message

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cloud_p2p')

class CloudPeer(Peer):
    """Extended Peer class with cloud identity information"""
    def __init__(self, ip, port=None, connection=None, peer_id=None):
        super().__init__(ip, port, connection)
        self.peer_id = peer_id or str(uuid.uuid4())
        self.relay_only = False  # Flag if we can only communicate via relay
        self.last_heartbeat = time.time()
    
    def __str__(self):
        if self.name:
            return f"{self.name} ({self.ip}:{self.port})"
        return f"{self.ip}:{self.port} [{self.peer_id[:8]}]"

class CloudNetwork(Network):
    """Extended Network class with cloud functionality"""
    def __init__(self, ip, port, relay_server_ip, relay_server_port=12345):
        super().__init__(ip, port)
        
        # Cloud specific attributes
        self.relay_server_ip = relay_server_ip
        self.relay_server_port = relay_server_port
        self.relay_connection = None
        self.peer_id = None
        self.cloud_connected = False
        self.relay_peers = {}  # Peers known through relay {peer_id: CloudPeer}
        
        # Start cloud connection
        self._connect_to_relay()
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        # Start relay receiver thread
        self.relay_receiver_thread = threading.Thread(target=self._relay_receiver)
        self.relay_receiver_thread.daemon = True
        self.relay_receiver_thread.start()
    
    def _connect_to_relay(self):
        """Connect to relay server and register this peer"""
        try:
            # Create a socket connection to the relay server
            self.relay_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.relay_connection.connect((self.relay_server_ip, self.relay_server_port))
            
            # Register with relay server
            registration = {
                'command': 'register',
                'ip': self.ip,
                'port': self.port
            }
            self.relay_connection.sendall(json.dumps(registration).encode('utf-8'))
            
            # Get response
            response = json.loads(self.relay_connection.recv(4096).decode('utf-8'))
            if response.get('status') == 'success':
                self.peer_id = response.get('peer_id')
                self.cloud_connected = True
                logger.info(f"Connected to relay server. Assigned ID: {self.peer_id}")
                self._alert(Message(f"Connected to cloud relay at {self.relay_server_ip}:{self.relay_server_port}"))
                return True
            else:
                logger.error(f"Failed to register with relay server: {response.get('message')}")
                self._alert(Message(f"Failed to connect to cloud relay: {response.get('message')}"))
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to relay server: {e}")
            self._alert(Message(f"Failed to connect to cloud relay: {e}"))
            self.relay_connection = None
            return False
    
    def _heartbeat_loop(self):
        """Send regular heartbeats to the relay server"""
        while self.running and self.cloud_connected:
            try:
                if self.relay_connection and self.peer_id:
                    heartbeat = {
                        'command': 'heartbeat',
                        'peer_id': self.peer_id
                    }
                    self.relay_connection.sendall(json.dumps(heartbeat).encode('utf-8'))
                    
                    # Update peer list every 5 heartbeats
                    if random.random() < 0.2:  # 20% chance per heartbeat
                        self._get_relay_peers()
                
                time.sleep(30)  # Heartbeat every 30 seconds
                
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                # Try to reconnect
                self.cloud_connected = False
                time.sleep(5)
                self._connect_to_relay()
    
    def _relay_receiver(self):
        """Handle messages from the relay server"""
        while self.running:
            if not self.cloud_connected or not self.relay_connection:
                time.sleep(1)
                continue
                
            try:
                self.relay_connection.settimeout(1.0)
                data = self.relay_connection.recv(4096)
                if not data:
                    logger.warning("Lost connection to relay server")
                    self.cloud_connected = False
                    time.sleep(5)
                    self._connect_to_relay()
                    continue
                
                message = json.loads(data.decode('utf-8'))
                
                # Handle relayed message
                if message.get('type') == 'relayed':
                    sender_id = message.get('sender_id')
                    content = message.get('content')
                    sender_ip = message.get('sender_ip')
                    sender_port = message.get('sender_port')
                    
                    # Create/update peer info
                    if sender_id not in self.relay_peers:
                        # Create new peer
                        peer = CloudPeer(sender_ip, sender_port, None, sender_id)
                        peer.relay_only = True
                        self.relay_peers[sender_id] = peer
                    
                    # Alert about the message
                    relay_peer = self.relay_peers[sender_id]
                    relay_peer.last_heartbeat = time.time()
                    
                    # Handle special messages
                    if isinstance(content, dict) and content.get('type') == 'file_transfer':
                        # Handle file transfer
                        file_content = base64.b64decode(content.get('data'))
                        file_name = content.get('filename')
                        self._alert(Message(f"Received file {file_name} via relay"))
                        # Assuming the Interface will handle this
                        self._alert(Message(file_content), str(relay_peer))
                    else:
                        # Regular message
                        self._alert(Message(content), str(relay_peer))
                
            except socket.timeout:
                # This is expected, just continue
                pass
            except Exception as e:
                logger.error(f"Error receiving from relay: {e}")
                time.sleep(1)
    
    def _get_relay_peers(self):
        """Get list of peers from relay server"""
        if not self.cloud_connected:
            return
            
        try:
            # Request peer list
            peer_request = {
                'command': 'get_peers',
                'peer_id': self.peer_id
            }
            self.relay_connection.sendall(json.dumps(peer_request).encode('utf-8'))
            
            # Get response (with short timeout)
            self.relay_connection.settimeout(5.0)
            response = json.loads(self.relay_connection.recv(4096).decode('utf-8'))
            self.relay_connection.settimeout(None)
            
            if response.get('status') == 'success':
                peers = response.get('peers', [])
                for peer_info in peers:
                    peer_id = peer_info.get('peer_id')
                    ip = peer_info.get('ip')
                    port = peer_info.get('port')
                    
                    # Add to relay peers if new
                    if peer_id not in self.relay_peers:
                        peer = CloudPeer(ip, port, None, peer_id)
                        peer.relay_only = True  # Start with relay only until direct connection verified
                        self.relay_peers[peer_id] = peer
                        logger.info(f"Discovered new peer via relay: {peer}")
                
        except Exception as e:
            logger.error(f"Error getting peers from relay: {e}")
    
    def connect_to_cloud_peer(self, peer_id):
        """Connect to a peer known through the relay"""
        if peer_id not in self.relay_peers:
            self._alert(Message(f"Unknown peer ID: {peer_id}"))
            return False
            
        peer = self.relay_peers[peer_id]
        
        # Try direct connection first
        try:
            # Create a socket and connect to the peer
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)  # Short timeout for connection attempt
            client_socket.connect((peer.ip, peer.port))
            client_socket.settimeout(None)
            
            # Update peer connection
            peer.connection = client_socket
            peer.relay_only = False
            
            # Move from relay_peers to peerList if not already there
            if peer not in self.peerList:
                self.peerList.append(peer)
                
            self._alert(Message(f"Connected directly to {peer}"))
            return True
            
        except Exception as e:
            logger.warning(f"Direct connection to {peer} failed: {e}")
            self._alert(Message(f"Direct connection to {peer} failed, will use relay"))
            
            # Add to peer list anyway, we'll use relay
            if peer not in self.peerList:
                self.peerList.append(peer)
                
            return False
    
    def send_via_relay(self, peer_id, content):
        """Send a message through the relay server"""
        if not self.cloud_connected:
            logger.warning("Cannot send via relay: not connected")
            return False
            
        try:
            relay_message = {
                'command': 'relay_message',
                'peer_id': self.peer_id,
                'target_id': peer_id,
                'content': content
            }
            self.relay_connection.sendall(json.dumps(relay_message).encode('utf-8'))
            return True
            
        except Exception as e:
            logger.error(f"Error sending via relay: {e}")
            return False
    
    def send_file_via_relay(self, peer_id, file_content, filename):
        """Send a file through the relay server"""
        # Encode the file content to base64
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        # Create a file transfer message
        file_message = {
            'type': 'file_transfer',
            'filename': filename,
            'data': encoded_content
        }
        
        return self.send_via_relay(peer_id, file_message)
    
    def sender(self, message):
        """Override sender to handle relay-only peers"""
        if not message:
            return
            
        # Handle standard peers with direct connection
        super().sender(message)
        
        # Additionally, send to relay-only peers
        for peer_id, peer in self.relay_peers.items():
            if peer.relay_only and peer in self.peerList:
                self.send_via_relay(peer_id, message)
    
    def list_cloud_peers(self):
        """Return a list of discovered cloud peers"""
        return list(self.relay_peers.values())
    
    def shutdown(self):
        """Override shutdown to handle cloud resources"""
        if self.cloud_connected:
            try:
                # Notify relay we're disconnecting
                disconnect_msg = {
                    'command': 'disconnect',
                    'peer_id': self.peer_id
                }
                self.relay_connection.sendall(json.dumps(disconnect_msg).encode('utf-8'))
                self.relay_connection.close()
            except:
                pass
            
        self.cloud_connected = False
        super().shutdown()