# CloudMainWithConfig.py
import socket
import time
import argparse
import sys
import logging
from CloudInterface import CloudInterface
from CloudP2PPlatform import CloudNetwork
import config

# Configure logging
log_level = getattr(logging, config.LOGGING["level"])
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cloud_main')

def parse_arguments():
    """Parse command line arguments (will override config file settings)"""
    parser = argparse.ArgumentParser(description='Cloud P2P Platform')
    parser.add_argument('--relay', type=str, help='Relay server IP address (overrides config)')
    parser.add_argument('--relay-port', type=int, help='Relay server port (overrides config)')
    parser.add_argument('--ip', type=str, help='Local IP address (overrides config)')
    parser.add_argument('--port', type=int, help='Local port (overrides config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    return parser.parse_args()

def validate_ip(ip):
    """Validate IP address format"""
    sections = ip.split(".")
    
    if len(sections) != 4:
        return False
    
    for section in sections:
        if not section.isdigit():
            return False
        section = int(section)
        if section < 0 or section > 255:
            return False
    
    if sections[0] == "127":  # not loop-back address
        return False
    
    return True

def get_own_ip():
    """Auto-detect local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))  # Connect to Google DNS
        ip = s.getsockname()[0]
        s.close()
        
        if validate_ip(ip):
            return ip
    except:
        pass
    
    # Manual entry fallback
    while True:
        ip = input("Could not auto-detect IP. Please enter a valid IP address: ")
        if validate_ip(ip):
            return ip

def get_port():
    """Prompt for port number"""
    DEFAULT = config.LOCAL_NETWORK["port"]
    
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
    """Main entry point"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine relay server settings (command line args override config file)
    relay_host = args.relay if args.relay else config.RELAY_SERVER["host"]
    relay_port = args.relay_port if args.relay_port else config.RELAY_SERVER["port"]
    
    # Get local IP (auto-detect or from config)
    if args.ip:
        myIP = args.ip
    elif not config.LOCAL_NETWORK["auto_detect_ip"] and config.LOCAL_NETWORK["ip"]:
        myIP = config.LOCAL_NETWORK["ip"]
    else:
        myIP = get_own_ip()
    
    print(f"Using IP address: {myIP}")
    
    # Get local port
    myPort = args.port if args.port else config.LOCAL_NETWORK["port"]
    print(f"Using port: {myPort}")
    
    # Initialize tag dictionary
    tagDict = {}
    
    try:
        # Initialize cloud network
        logger.info(f"Connecting to relay server at {relay_host}:{relay_port}")
        myNetwork = CloudNetwork(myIP, myPort, relay_host, relay_port)
        
        # Configure network parameters from config
        myNetwork.peer_timeout = config.NETWORK["peer_timeout"]
        
        # Initialize cloud interface
        myInterface = CloudInterface(tagDict, myNetwork, relay_host)
        
        # Run the interface
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