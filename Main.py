import socket
import time
from Interface import Interface
from P2PPlatform import Network


################################## MAIN PROGRAM BELOW ##################################



tagDict = {}
myInterface = Interface(tagDict)

############### THIS COULD BE MOVED TO INTERFACE###########
myIP = myInterface.getOwnIP()
print("Detected IP: " + myIP) 
print("I'll need your port.")
myPort = myInterface.getPort()
myNetwork = Network(myIP, myPort)
myInterface.network = myNetwork

myInterface.run()
"""interfaceThread = WorkerThread("interface", myInterface)
receiverThread = WorkerThread("receiver",myNetwork)
acceptorThread = WorkerThread("acceptor",myNetwork)



interfaceThread.start()
receiverThread.start()
acceptorThread.start()


myInterface.network = myNetwork

# Add the first peer if the user wants one

############################################################
	
while myInterface.network is not None: #with this implementation, when the interface closes, this program closes
	
	######TODO code program logic here #############
	
	time.sleep(3)"""
