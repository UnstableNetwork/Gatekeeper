import paramiko
import select
import socket
import threading
import logging

# --- CONFIGURATION ---
SSH_HOST = "your.remote.server.ip"
SSH_USER = "root"
SSH_PASSWORD = "your_password"  # Or use SSH_KEY_FILE
LOCAL_PORT = 8080               # Traffic enters here
REMOTE_TARGET = "127.0.0.1"     # Target relative to the server
REMOTE_PORT = 80                # Target port (e.g., a web server or database)

# Logging Setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger("Gatekeeper")

def tunnel_handler(local_socket, remote_host, remote_port, transport):
    """Handles the bidirectional flow of data between local and remote sockets."""
    remote_socket = transport.open_channel(
        "direct-tcpip", (remote_host, remote_port), local_socket.getpeername()
    )
    
    if remote_socket is None:
        logger.error(f"Could not open tunnel to {remote_host}:{remote_port}")
        return

    logger.info("Tunnel established.")
    try:
        while True:
            r, w, x = select.select([local_socket, remote_socket], [], [])
            if local_socket in r:
                data = local_socket.recv(4096)
                if len(data) == 0: break
                remote_socket.send(data)
            if remote_socket in r:
                data = remote_socket.recv(4096)
                if len(data) == 0: break
                local_socket.send(data)
    except Exception as e:
        logger.debug(f"Tunnel connection closed: {e}")
    finally:
        local_socket.close()
        remote_socket.close()
        logger.info("Tunnel closed.")

def start_gatekeeper():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        logger.info(f"Connecting to SSH server {SSH_HOST}...")
        client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASSWORD)
        transport = client.get_transport()

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", LOCAL_PORT))
        server_socket.listen(5)

        logger.info(f"Gatekeeper listening on localhost:{LOCAL_PORT} -> {REMOTE_TARGET}:{REMOTE_PORT}")

        while True:
            local_conn, addr = server_socket.accept()
            logger.info(f"Incoming connection from {addr[0]}:{addr[1]}")
            thr = threading.Thread(
                target=tunnel_handler, 
                args=(local_conn, REMOTE_TARGET, REMOTE_PORT, transport)
            )
            thr.setDaemon(True)
            thr.start()

    except Exception as e:
        logger.critical(f"Main service failure: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    start_gatekeeper()
