import os
import socket
import subprocess
from Interface import Interface
from CloudP2PPlatform import CloudNetwork, CloudPeer

class CloudInterface(Interface):
    def __init__(self, tagDict, network=None, relay_server=None):
        super().__init__(tagDict, network)
        self.relay_server = relay_server
        self.cloud_commands = {
            "/cloud": self.cloud_status,
            "/discover": self.discover_peers,
            "/connect_cloud": self.connect_cloud_peer,
            "/relay": self.relay_message
        }
    
    def run(self):
        """Override run to add cloud commands"""
        if not isinstance(self.network, CloudNetwork):
            print("Warning: Not using cloud network. Cloud features disabled.")
            super().run()
            return
            
        self.network.alerters.append(self.netMessage)
        adamNode = self.printThis("Would you like to start a new network? y/n ", type="input")
        if adamNode == "" or adamNode[0].lower() != "y":
            self.connector()
            
        # Display cloud status on startup
        self.cloud_status()
        
        print("\nCloud P2P Commands:")
        print("  /cloud - Display cloud connection status")
        print("  /discover - Find peers through cloud relay")
        print("  /connect_cloud <peer_id> - Connect to a peer by ID")
        print("  /relay <peer_id> <message> - Send message through relay\n")
            
        command = None
        while command != "/exit":
            command = input("Please type your message, or enter a command, '/connect', '/approve', '/name', '/addPort', '/exit', '/cloud', '/discover', '/connect_cloud', '/relay', '/sendCode', '/receiveCode' then hit enter:  \n")
            
            # Check for cloud commands first
            if command.split(' ')[0] in self.cloud_commands:
                cmd_parts = command.split(' ', 1)
                cmd = cmd_parts[0]
                args = cmd_parts[1] if len(cmd_parts) > 1 else ""
                self.cloud_commands[cmd](args)
            elif command == "/connect":
                self.connector()
            elif command == "/approve":
                self.approver()
            elif command == "/name":
                self.name()
            elif command == "/addPort":
                self.addPort()
            elif command == "/sendCode":
                self.parseAndSend()
            elif command == "/receiveCode":
                self.receivingCode = True
            else:
                self.network.sender(command)

        # Close down the network
        self.network.shutdown()
        self.network = None
    
    def cloud_status(self, args=""):
        """Display cloud connection status"""
        if not isinstance(self.network, CloudNetwork):
            print("Not connected to cloud relay")
            return
            
        if self.network.cloud_connected:
            print(f"Connected to cloud relay at {self.network.relay_server_ip}:{self.network.relay_server_port}")
            print(f"Your peer ID: {self.network.peer_id}")
            print(f"Direct connections: {len(self.network.peerList)}")
            print(f"Known cloud peers: {len(self.network.relay_peers)}")
        else:
            print("Not connected to cloud relay")
    
    def discover_peers(self, args=""):
        """Force peer discovery from relay server"""
        if not isinstance(self.network, CloudNetwork):
            print("Cloud network not available")
            return
            
        if not self.network.cloud_connected:
            print("Not connected to cloud relay")
            return
            
        # Force peer refresh
        self.network._get_relay_peers()
        
        # Show discovered peers
        print("Discovered cloud peers:")
        for peer_id, peer in self.network.relay_peers.items():
            connection_type = "relay only" if peer.relay_only else "direct connection"
            print(f"  - {peer} ({connection_type})")
    
    def connect_cloud_peer(self, args):
        """Connect to a peer by ID"""
        if not args:
            print("Usage: /connect_cloud <peer_id>")
            return
            
        if not isinstance(self.network, CloudNetwork):
            print("Cloud network not available")
            return
            
        peer_id = args.strip()
        if peer_id not in self.network.relay_peers:
            print(f"Unknown peer ID: {peer_id}")
            return
            
        print(f"Connecting to peer {peer_id}...")
        result = self.network.connect_to_cloud_peer(peer_id)
        
        if result:
            print(f"Direct connection established with {self.network.relay_peers[peer_id]}")
        else:
            print(f"Using relay for communication with {self.network.relay_peers[peer_id]}")
    
    def relay_message(self, args):
        """Send a message through relay"""
        if not args or ' ' not in args:
            print("Usage: /relay <peer_id> <message>")
            return
            
        if not isinstance(self.network, CloudNetwork):
            print("Cloud network not available")
            return
            
        parts = args.split(' ', 1)
        peer_id = parts[0]
        message = parts[1]
        
        if peer_id not in self.network.relay_peers:
            print(f"Unknown peer ID: {peer_id}")
            return
            
        success = self.network.send_via_relay(peer_id, message)
        if success:
            print(f"Message sent via relay to {self.network.relay_peers[peer_id]}")
        else:
            print("Failed to send message via relay")
    
    def parseAndSend(self):
        """Override parseAndSend to handle cloud file transfers"""
        fileName = input("Please enter the filename to send: ")
        
        try:
            with open(fileName, 'r') as openFile:
                file_content = openFile.read()
                
            # For standard network connections
            self.network.sender("<code> " + file_content)
            
            # For relay-only peers in cloud network
            if isinstance(self.network, CloudNetwork):
                for peer_id, peer in self.network.relay_peers.items():
                    if peer.relay_only and peer in self.network.peerList:
                        self.network.send_file_via_relay(peer_id, file_content.encode('utf-8'), os.path.basename(fileName))
                        
        except Exception as e:
            print(f"Error reading or sending file: {e}")