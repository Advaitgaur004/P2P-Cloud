from P2PPlatform import Network
from P2PPlatform import Peer
import socket
import subprocess

class Interface(object):
	def __init__(self, tagDict, network = None):
		self.network = network
		self.tagDict = tagDict
		self.receivingCode = False
		
	def run(self):
		self.network.alerters.append(self.netMessage)
		adamNode = self.printThis("Would you like to start a new network? y/n ", type = "input")
		if adamNode == "" or adamNode[0].lower()!= "y":
			self.connector()
		command = None
		while command != "/exit":
			command = input("Please type your message, or enter a command, '/connect', '/approve', '/name', '/addPort', '/exit', '/sendCode' , '/receiveCode' then hit enter:  \n")
			if command == "/connect":
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
		self.network.shutdown()
		self.network = None

	def parseAndSend(self):
		fileName = input("Please enter the filename to send: ")
		toSendFile = self.programParser(fileName)
		self.network.sender("<code> " + toSendFile)
		
	def programParser(self, filename):
		with open(filename, 'r') as openFile:
			string = openFile.read()
		return string
	#first function upon netmessage receiving a <code> tag...	
	def receiveCode(self, peer, code):
		self.receivingCode = False
		if peer != None:
			print("Code received from " + peer)
		fileName = input("Please enter name of the file to be created for the code: ")
		self.programCreater(fileName,code)
		run = input("Run the file? y/n")
		if run == "y" or run == "Y" or run == "Yes":
			try:
				result = self.runProgram(fileName)
				print(result)
				sendYN = input("Send the result? y/n")
				if sendYN == "y" or sendYN == "Y" or sendYN == "Yes":
					self.network.sender(result)
			except subprocess.CalledProcessError as e:
				error_message = f"Error executing code: {e}"
				print(error_message)
				sendYN = input("Send the error message? y/n")
				if sendYN == "y" or sendYN == "Y" or sendYN == "Yes":
					self.network.sender(error_message)
	def programCreater(self, filename, code):
		with open(filename, 'w') as openFile:
			openFile.write(code)		
		
	#runs a python program
	def runProgram(self, fileName):
		process = subprocess.check_output(["python3", fileName], stderr=subprocess.STDOUT, universal_newlines=True)
		return process		
	
	def getOwnIP(self):
		"""see http://stackoverflow.com/questions/166506 for details. """
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('google.com', 53))
		IP = s.getsockname()[0]
	
		while not self.validateIP(IP):
			IP = input("Please enter a valid IP address: ")
	
		return IP
	
	
	def validateIP(self, IP):
		sections = IP.split(".") 
	
		if len(sections) != 4:
			return False
	
		for section in sections:
			if not section.isdigit(): #Making sure all contents are ints
				return False
			section = int(section)
			if section < 0 or section > 255: #validate range of the number
				return False
	
		if sections[0] == "127": #not loop-back address
			return False
	
		return True
	
	
	
	def getPort(self):	
		DEFAULT = 12345
		port = input("Default port: {}. Enter to continue or type an alternate. ".format(DEFAULT))
		if port == "":
			return DEFAULT
		return int(port)
	
	def connector(self):
		peerIP = input("Enter it your peer's IP address: ")
		peerPort = self.getPort()
		self.network.connect(peerIP, peerPort)
		
	def netMessage(self, message, peer = None):
		message = message.contents
		if type(message) is str and message[:6] == "<code>" and self.receivingCode:
			self.receiveCode(peer,message[6:])
		if peer is not None:
			print("From {0!s}: {1!s}".format(peer,message))
		else:
			print(str(message))
	def approver(self):
		
		i = 0
		while i < len(self.network.unconfirmedList):
			peer = self.network.unconfirmedList[i]
			add = input("y/n to add: " + str(peer) + " ").lower()
			if add == "y":
				self.network.approve(peer)
			i += 1
	
	
	def printThis(self, toPrint, type = None):
		if type is not None:
			return input(toPrint)
		else:
			print(toPrint)
			
		
	def name(self): 
		"""
		Gives a peer a unique name identifier (determined by the input of the user)
		The name will be accessible through peer.name
		"""
		for peers in list(self.network.peerList):
			print(str(peers) + " " + str(self.network.peerList.index(peers)))
		index = int(self.printThis("Please enter the index of the peer you would like to name: \n", type = "input"))
		name = self.printThis("Please enter the name of the peer you would like to name: \n", type = "input")
		self.network.peerList[index].name = name
		
		
	def addPort(self):
		"""
		Adds a server port to a peer, the peer which has the port added, and the port number
		to be added is determined with user input
		"""
		for peers in list(self.network.peerList):
			print(str(peers) + " " + str(self.network.peerList.index(peers)))
		index = int(self.printThis("Please enter the index of the peer you would like to add a port to: \n", type = "input"))
		port = int(self.printThis("Please enter the port for the peer: \n", type = "input"))
		self.network.peerList[index].port = port
