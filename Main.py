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