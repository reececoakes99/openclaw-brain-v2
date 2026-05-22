#!/usr/bin/env python3
"""
Minimal TCP/UDP echo server for testing ISO8583 framing.
Echoes back raw bytes received and logs connection details.
"""

import socket
import struct
import signal
import sys
import time
from datetime import datetime
from typing import Optional
import argparse


class EchoServer:
    def __init__(self, port: int = 9000, protocol: str = "tcp", hex_dump_bytes: int = 64):
        self.port = port
        self.protocol = protocol.lower()
        self.hex_dump_bytes = hex_dump_bytes
        self.running = True
        self.socket: Optional[socket.socket] = None
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Received signal {signum}, shutting down...")
        self.running = False
        if self.socket:
            self.socket.close()
        sys.exit(0)
    
    def _log_hex_dump(self, data: bytes) -> str:
        """Generate hex dump of first N bytes."""
        hex_part = data[:self.hex_dump_bytes].hex()
        lines = []
        for i in range(0, len(hex_part), 32):
            hex_segment = hex_part[i:i+32]
            ascii_segment = ""
            byte_offset = i // 2
            for j in range(0, len(hex_segment), 2):
                try:
                    byte_val = int(hex_segment[j:j+2], 16)
                    ascii_segment += chr(byte_val) if 32 <= byte_val < 127 else "."
                except ValueError:
                    ascii_segment += "?"
            lines.append(f"    {byte_offset:04x}: {hex_segment:<{32}}  {ascii_segment}")
        return "\n".join(lines) if lines else "    (empty)"
    
    def _log_message(self, timestamp: str, source: str, byte_count: int, hex_dump: str = ""):
        """Log received message details."""
        print(f"[{timestamp}] Received {byte_count} bytes from {source}")
        if hex_dump:
            print(hex_dump)
    
    def run_tcp(self):
        """Run TCP echo server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.port))
        self.socket.listen(5)
        self.socket.settimeout(1.0)
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TCP Echo Server listening on port {self.port}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Hex dump will show first {self.hex_dump_bytes} bytes\n")
        
        while self.running:
            try:
                client_socket, addr = self.socket.accept()
                client_socket.settimeout(30.0)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                source = f"{addr[0]}:{addr[1]}"
                
                try:
                    data = client_socket.recv(8192)
                    
                    if data:
                        hex_dump = self._log_hex_dump(data)
                        self._log_message(timestamp, source, len(data), hex_dump)
                        
                        # Echo back the data
                        client_socket.sendall(data)
                        print(f"[{timestamp}] Echoed {len(data)} bytes back to {source}\n")
                except socket.timeout:
                    print(f"[{timestamp}] Connection from {source} timed out\n")
                except Exception as e:
                    print(f"[{timestamp}] Error handling {source}: {e}\n")
                finally:
                    client_socket.close()
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error: {e}")
                break
        
        self.socket.close()
    
    def run_udp(self):
        """Run UDP echo server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.port))
        self.socket.settimeout(1.0)
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] UDP Echo Server listening on port {self.port}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Hex dump will show first {self.hex_dump_bytes} bytes\n")
        
        while self.running:
            try:
                data, addr = self.socket.recvfrom(8192)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                source = f"{addr[0]}:{addr[1]}"
                
                if data:
                    hex_dump = self._log_hex_dump(data)
                    self._log_message(timestamp, source, len(data), hex_dump)
                    
                    # Echo back the data
                    self.socket.sendto(data, addr)
                    print(f"[{timestamp}] Echoed {len(data)} bytes back to {source}\n")
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error: {e}")
                break
        
        self.socket.close()
    
    def run(self):
        """Run the echo server based on protocol."""
        if self.protocol == "udp":
            self.run_udp()
        else:
            self.run_tcp()


def main():
    parser = argparse.ArgumentParser(description="TCP/UDP Echo Server for ISO8583 Testing")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on (default: 9000)")
    parser.add_argument("--protocol", choices=["tcp", "udp"], default="tcp", help="Protocol (default: tcp)")
    parser.add_argument("--hex-bytes", type=int, default=64, help="Bytes to show in hex dump (default: 64)")
    
    args = parser.parse_args()
    
    server = EchoServer(
        port=args.port,
        protocol=args.protocol,
        hex_dump_bytes=args.hex_bytes
    )
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
