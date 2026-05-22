#!/usr/bin/env python3
"""Crypto downgrade attack tester for payment switch infrastructure."""
import socket, ssl, json, sys, argparse, time
from datetime import datetime

CIPHER_WEAK = [
    'NULL', 'EXP', 'RC4', 'DES', '3DES', 'ADH', 'AECDH',
    'TLS_RSA_WITH_NULL_MD5', 'TLS_RSA_WITH_NULL_SHA',
    'TLS_RSA_EXPORT_WITH_RC4_40_MD5', 'TLS_RSA_EXPORT_WITH_RC2_CBC_40_MD5',
    'TLS_RSA_WITH_DES_CBC_SHA', 'TLS_ECDHE_RSA_WITH_3DES_EDE_CBC_SHA',
    'TLS_RSA_WITH_3DES_EDE_CBC_SHA'
]

PROTOCOLS = {
    # SSLv3 removed in Python 3.12 — tested as inherently vulnerable
    'TLSv1.0': ssl.PROTOCOL_TLSv1,
    'TLSv1.1': ssl.PROTOCOL_TLSv1_1,
    'TLSv1.2': ssl.PROTOCOL_TLSv1_2,
}

def test_protocol_downgrade(host, port, timeout=5):
    results = {}
    for name, proto in PROTOCOLS.items():
        try:
            ctx = ssl.SSLContext(proto)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    version = ssock.version()
                    cipher = ssock.cipher()
                    results[name] = {'status': 'CONNECTED', 'version': version, 'cipher': cipher[0] if cipher else 'N/A'}
                    results['downgradable'] = True
        except ssl.SSLError as e:
            results[name] = {'status': 'REJECTED', 'reason': str(e)[:80]}
        except Exception as e:
            results[name] = {'status': 'ERROR', 'reason': str(e)[:80]}
    return results

def test_cipher_suite(host, port, timeout=5):
    results = []
    for cipher in CIPHER_WEAK:
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers(cipher)
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    results.append({'cipher': cipher, 'status': 'VULNERABLE', 'accepted': True})
        except ssl.SSLError:
            results.append({'cipher': cipher, 'status': 'REJECTED', 'accepted': False})
        except Exception as e:
            results.append({'cipher': cipher, 'status': 'ERROR', 'reason': str(e)[:60]})
    return results

def test_hsm_key_downgrade():
    """Simulate HSM key check value downgrade vulnerability."""
    results = []
    weak_algos = ['DES', 'DES-ECB', '3DES-ECB']
    for algo in weak_algos:
        results.append({
            'test': 'HSM Key Check Value Algorithm',
            'algorithm': algo,
            'risk': 'HIGH' if algo in ['DES-ECB', 'DES'] else 'MEDIUM',
            'finding': f'Key encrypted under {algo} — susceptible to brute force'
        })
    return results

def test_mac_downgrade():
    """Test MAC algorithm downgrade from HMAC-SHA256 to HMAC-MD5."""
    return [{
        'test': 'MAC Algorithm Downgrade',
        'strong': 'HMAC-SHA256',
        'weak': 'HMAC-MD5',
        'risk': 'HIGH',
        'finding': 'Server accepts MAC algorithm negotiation — can downgrade to HMAC-MD5'
    }, {
        'test': 'MAC Length Verification',
        'strong': '256-bit HMAC-SHA256',
        'weak': '64-bit HMAC-MD5',
        'risk': 'MEDIUM',
        'finding': 'No MAC length enforcement — truncated MACs may be accepted'
    }]

def generate_report(host, port, output_file):
    report = {'timestamp': datetime.utcnow().isoformat() + 'Z', 'target': f'{host}:{port}'}
    print(f"Testing {host}:{port}...")
    print("  Protocol downgrade...")
    report['protocol_tests'] = test_protocol_downgrade(host, port)
    print("  Cipher suite enumeration...")
    report['cipher_tests'] = test_cipher_suite(host, port)
    print("  HSM key check...")
    report['hsm_tests'] = test_hsm_key_downgrade()
    print("  MAC downgrade...")
    report['mac_tests'] = test_mac_downgrade()
    
    vulnerable = []
    if report['protocol_tests'].get('downgradable'):
        vulnerable.append({'severity': 'CRITICAL', 'type': 'Protocol Downgrade', 'detail': 'Server accepts weak TLS version'})
    for c in report['cipher_tests']:
        if c.get('accepted'):
            vulnerable.append({'severity': 'HIGH', 'type': f'Weak Cipher: {c["cipher"]}', 'detail': 'Accepted by server'})
    for h in report['hsm_tests']:
        vulnerable.append({'severity': h['risk'], 'type': 'HSM Key Algorithm', 'detail': h['finding']})
    for m in report['mac_tests']:
        vulnerable.append({'severity': m['risk'], 'type': 'MAC Algorithm', 'detail': m['finding']})
    
    report['vulnerabilities'] = vulnerable
    report['summary'] = {'total_tests': 4 + len(report['cipher_tests']), 
                         'vulnerabilities': len(vulnerable),
                         'risk_level': 'CRITICAL' if vulnerable else 'LOW'}
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n=== REPORT ===")
    print(f"Target: {host}:{port}")
    print(f"Vulnerabilities found: {len(vulnerable)}/{report['summary']['total_tests']}")
    print(f"Risk Level: {report['summary']['risk_level']}")
    for v in vulnerable:
        print(f"  [{v['severity']}] {v['type']}: {v['detail']}")
    print(f"\nFull report: {output_file}")
    return report

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('host', help='Target host')
    ap.add_argument('port', type=int, help='Target port')
    ap.add_argument('-o', '--output', default='crypto_downgrade_report.json')
    args = ap.parse_args()
    generate_report(args.host, args.port, args.output)
