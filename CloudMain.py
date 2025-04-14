# CloudMain.py
import socket
import time
import argparse
import sys
import logging
from CloudInterface import CloudInterface
from CloudP2PPlatform import CloudNetwork

#Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cloud_main')

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Cloud P2P Platform')
    parser.add_argument('--relay', type=str, help='Relay server IP address', required=True)
    parser.add_argument('--relay-port', type=int, default=12345, help='Relay server port (default: 12345)')
    parser.add_argument('--ip', type=str, help='Local IP address (auto-detect if not specified)')
    parser.add_argument('--port', type=int, help='Local port (prompt if not specified)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    return parser.parse_args()

def validate_ip(ip):
    sections = ip.split(".")
    
    if len(sections) != 4:
        return False
    
    for section in sections:
        if not section.isdigit():
            return False
        section = int(section)
        if section < 0 or section > 255:
            return False
    
    if sections[0] == "127":  #not loop-back address
        return False
    
    return True

def get_own_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))  #connect to Google DNS
        ip = s.getsockname()[0]
        s.close()
        if validate_ip(ip):
            return ip
    except:
        pass
    while True:
        ip = input("Could not auto-detect IP. Please enter a valid IP address: ")
        if validate_ip(ip):
            return ip

def get_port():
    DEFAULT = 12345
    port = input(f"Default port: {DEFAULT}. Enter to continue or type an alternate: ")
    if port == "":
        return DEFAULT
    try:
        port = int(port)
        return port
    except:
        print("Invalid port. Using default.")
        return DEFAULT

def main():
    args = parse_arguments()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    myIP = args.ip if args.ip else get_own_ip()
    print(f"Using IP address: {myIP}")    
    myPort = args.port if args.port else get_port()
    print(f"Using port: {myPort}")
    tagDict = {}
    try:
        logger.info(f"Connecting to relay server at {args.relay}:{args.relay_port}")
        myNetwork = CloudNetwork(myIP, myPort, args.relay, args.relay_port)
        myInterface = CloudInterface(tagDict, myNetwork, args.relay)
        myInterface.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if 'myNetwork' in locals():
            myNetwork.shutdown()
    except Exception as e:
        logger.error(f"Error: {e}")
        if 'myNetwork' in locals():
            myNetwork.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()