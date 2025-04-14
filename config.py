# config.py
"""
Configuration settings for the Cloud P2P Platform
"""

# Relay server configuration
RELAY_SERVER = {
    "host": "your-ec2-instance-ip",  # Replace with your EC2 instance's public IP or domain name
    "port": 12345                    # Default relay server port
}

# Local configuration
LOCAL_NETWORK = {
    "auto_detect_ip": True,          # Automatically detect local IP address
    "ip": None,                      # Manual IP (only used if auto_detect_ip is False)
    "port": 12345                    # Default local port
}

# Security settings
SECURITY = {
    "enable_encryption": False,      # Not implemented yet - for future use
    "authentication": False          # Not implemented yet - for future use
}

# Logging configuration
LOGGING = {
    "level": "INFO",                 # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "output": "console"              # console, file, both
}

# File transfer settings
FILE_TRANSFER = {
    "use_relay_for_large_files": False,  # Whether to use relay for files over max_direct_size
    "max_direct_size": 1024 * 1024 * 10  # Maximum file size for direct transfer (10MB)
}

# Network behavior
NETWORK = {
    "peer_timeout": 120,             # Seconds before considering a peer disconnected
    "heartbeat_interval": 30,        # Seconds between heartbeats
    "auto_reconnect": True           # Attempt to reconnect if connection is lost
}