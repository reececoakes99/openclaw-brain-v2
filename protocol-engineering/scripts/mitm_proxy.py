#!/usr/bin/env python3
"""ISO8583 MITM Proxy for HISO93/HISO87 testing."""
import socket, threading, json, time, argparse, sys

class MITMProxy:
    def __init__(self, listen_port, target_host, target_port):
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.transactions = []
        self.mutation_rate = 0.0
        self.inject_delay_ms = 0

    def hex_dump(self, data, limit=64):
        hex_str = data[:limit].hex()
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:limit])
        return f"{hex_str}  {ascii_str}"

    def parse_iso8583(self, data):
        # Basic ISO8583 parsing for HISO93 (binary) and HISO87 (ASCII)
        result = {}
        if len(data) < 4:
            return result
        mti_bytes = data[:2]
        if all(b < 128 for b in mti_bytes):
            result['mti'] = mti_bytes.decode('ascii', errors='replace')
            result['encoding'] = 'ASCII'
            if len(data) >= 5:
                len_bytes = data[2:4]
                try:
                    msg_len = int(len_bytes.decode())
                    result['payload'] = data[4:4+msg_len]
                except: pass
        else:
            result['mti'] = str(int.from_bytes(mti_bytes, 'big'))
            result['encoding'] = 'BINARY'
            if len(data) > 16:
                bitmap = data[2:10]
                result['bitmap'] = bitmap.hex()
                fields = []
                offset = 10
                for i, bit in enumerate(bitmap):
                    for sub in range(8):
                        if bit & (0x80 >> sub):
                            field_num = i * 8 + sub + 1
                            if field_num in [1,2,3,4,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128]:
                                fields.append(field_num)
                result['fields'] = fields
        return result

    def handle_client(self, client_sock, addr):
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] Connection from {addr}")
        try:
            target_sock = socket.create_connection((self.target_host, self.target_port), timeout=10)
            def forward(src, dst, direction):
                while True:
                    try:
                        data = src.recv(4096)
                        if not data:
                            break
                        if direction == '→' and self.inject_delay_ms > 0:
                            time.sleep(self.inject_delay_ms / 1000)
                        if direction == '→' and self.mutation_rate > 0:
                            import random
                            if random.random() < self.mutation_rate:
                                mut_pos = random.randint(0, len(data)-1)
                                data = bytearray(data)
                                data[mut_pos] ^= 0xFF
                                print(f"  ⚠ MUTATION at byte {mut_pos}")
                                data = bytes(data)
                        ts2 = time.strftime('%H:%M:%S.%f')[:-3]
                        parsed = self.parse_iso8583(data)
                        print(f"[{ts2}] {direction} {len(data)} bytes | MTI={parsed.get('mti','?')} | "
                              f"encoding={parsed.get('encoding','?')} | fields={parsed.get('fields',[])}")
                        print(f"    hex: {data[:64].hex()}")
                        dst.sendall(data)
                        entry = {'ts': ts2, 'dir': direction, 'len': len(data), 
                                 'mti': parsed.get('mti'), 'hex': data.hex()}
                        self.transactions.append(entry)
                    except Exception as e:
                        break
            t1 = threading.Thread(target=forward, args=(client_sock, target_sock, '→'))
            t2 = threading.Thread(target=forward, args=(target_sock, client_sock, '←'))
            t1.daemon = t2.daemon = True
            t1.start(); t2.start()
            t1.join(); t2.join()
        except Exception as e:
            print(f"  ✗ Error: {e}")
        finally:
            client_sock.close()
            try: target_sock.close()
            except: pass

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', self.listen_port))
        srv.listen(10)
        print(f"MITM Proxy listening on :{self.listen_port} → {self.target_host}:{self.target_port}")
        print(f"  Mutation rate: {self.mutation_rate*100:.1f}%  |  Delay: {self.inject_delay_ms}ms")
        while True:
            client_sock, addr = srv.accept()
            t = threading.Thread(target=self.handle_client, args=(client_sock, addr))
            t.daemon = True
            t.start()

    def export(self, path):
        with open(path, 'w') as f:
            json.dump(self.transactions, f, indent=2)
        print(f"Exported {len(self.transactions)} transactions to {path}")

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='ISO8583 MITM Proxy')
    ap.add_argument('-l', '--listen', type=int, default=9090, help='Listen port')
    ap.add_argument('-t', '--target', default='127.0.0.1:7000', help='Target host:port')
    ap.add_argument('-m', '--mutate', type=float, default=0.0, help='Mutation rate 0-1')
    ap.add_argument('-d', '--delay', type=int, default=0, help='Inject delay ms')
    ap.add_argument('-e', '--export', default=None, help='Export transactions to JSON')
    args = ap.parse_args()
    host, port = args.target.split(':')
    proxy = MITMProxy(args.listen, host, int(port))
    proxy.mutation_rate = args.mutate
    proxy.inject_delay_ms = args.delay
    try:
        proxy.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if args.export:
            proxy.export(args.export)
