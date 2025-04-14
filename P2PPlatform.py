import socket
import threading
import time

class Message:
    def __init__(self, contents):
        self.contents = contents

class Peer:
    def __init__(self, ip, port=None, connection=None):
        self.ip = ip
        self.port = port
        self.connection = connection
        self.name = None
    
    def __str__(self):
        if self.name:
            return f"{self.name} ({self.ip}:{self.port})"
        return f"{self.ip}:{self.port}"

class Network:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.peerList = []
        self.unconfirmedList = []
        self.alerters = []
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((ip, port))
        self.server_socket.listen(5)
        self.acceptor_thread = threading.Thread(target=self._accept_connections)
        self.acceptor_thread.daemon = True
        self.acceptor_thread.start()
        self.receiver_thread = threading.Thread(target=self._receive_messages)
        self.receiver_thread.daemon = True
        self.receiver_thread.start()
    
    def connect(self, ip, port):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, port))
            peer = Peer(ip, port, client_socket)
            self.peerList.append(peer)
            self._alert(Message(f"Connected to {peer}"))
            return True
        except Exception as e:
            self._alert(Message(f"Failed to connect to {ip}:{port}: {e}"))
            return False
    
    def sender(self, message):
        if not message:
            return
        message_obj = Message(message)
        for peer in self.peerList:
            try:
                if peer.connection:
                    peer.connection.sendall(message.encode())
            except Exception as e:
                self._alert(Message(f"Failed to send message to {peer}: {e}"))
    
    def approve(self, peer):
        if peer in self.unconfirmedList:
            self.unconfirmedList.remove(peer)
            self.peerList.append(peer)
            self._alert(Message(f"Peer {peer} approved"))
    
    def shutdown(self):
        self.running = False
        #closing all connections
        for peer in self.peerList:
            if peer.connection:
                try:
                    peer.connection.close()
                except:
                    pass
        #closing the server socket
        try:
            self.server_socket.close()
        except:
            pass
        self._alert(Message("Network shutdown"))
    
    def _alert(self, message, peer=None):
        for alerter in self.alerters:
            try:
                alerter(message, peer)
            except Exception as e:
                print(f"Error in alerter: {e}")
    
    def _accept_connections(self):
        while self.running:
            try:
                client_socket, (client_ip, client_port) = self.server_socket.accept()
                peer = Peer(client_ip, client_port, client_socket)
                self.unconfirmedList.append(peer)
                self._alert(Message(f"New connection from {peer}"))
            except Exception as e:
                if self.running:  #only print error if we're still supposed to be running
                    print(f"Error accepting connection: {e}")
            time.sleep(0.1)
    
    def _receive_messages(self):
        while self.running:
            all_peers = self.peerList + self.unconfirmedList
            for peer in all_peers:
                if peer.connection:
                    try:
                        peer.connection.setblocking(0)
                        try:
                            data = peer.connection.recv(4096)
                            if data:
                                message = Message(data.decode())
                                self._alert(message, str(peer))
                            else:
                                peer.connection.close()
                                peer.connection = None
                                if peer in self.peerList:
                                    self.peerList.remove(peer)
                                if peer in self.unconfirmedList:
                                    self.unconfirmedList.remove(peer)
                                self._alert(Message(f"Connection closed with {peer}"))
                        except BlockingIOError:
                            pass
                        finally:
                            if peer.connection:
                                peer.connection.setblocking(1)
                    except Exception as e:
                        print(f"Error receiving from {peer}: {e}")
                        try:
                            if peer.connection:
                                peer.connection.close()
                                peer.connection = None
                        except:
                            pass
                        if peer in self.peerList:
                            self.peerList.remove(peer)
                        if peer in self.unconfirmedList:
                            self.unconfirmedList.remove(peer)
                        self._alert(Message(f"Lost connection with {peer}: {e}"))
            time.sleep(0.1)