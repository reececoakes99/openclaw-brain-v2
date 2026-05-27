#!/usr/bin/env python3
"""
pipeline/stages/stage6_evasion.py
OpenClaw Pipeline — Stage 6: Anti-Detection & Evasion
Agent: Elkin 🔱 | Version: 2.1 — Production
"""
import os, random, logging, time, socket
from datetime import datetime
from typing import Optional, Dict, List

log = logging.getLogger("stage6_evasion")

USER_AGENTS = {
    'chrome_win': [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ],
    'chrome_mac': [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    ],
    'firefox_win': [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    ],
    'safari_mac': [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    ],
    'mobile_ios': [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    ],
    'mobile_android': [
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    ],
}

HEADER_PROFILES = {
    'chrome': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Connection': 'keep-alive',
    },
    'firefox': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    },
    'api_client': {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
    },
}

WAF_SIGNATURES = {
    'cloudflare': ['cf-ray', 'cf-cache-status', '__cfduid', 'cloudflare'],
    'akamai': ['akamai', 'x-check-cacheable', 'x-akamai-transformed'],
    'aws_waf': ['x-amzn-requestid', 'x-amz-cf-id'],
    'imperva': ['x-iinfo', 'x-cdn', 'incap_ses', 'visid_incap'],
    'f5_big_ip': ['bigipserver', 'x-wa-info'],
    'datadome': ['datadome', 'dd_session'],
    'perimeterx': ['_pxhd', '_pxde', 'px-'],
    'kasada': ['x-kpsdk-ct', 'x-kpsdk-r'],
    'recaptcha': ['recaptcha', 'g-recaptcha'],
    'hcaptcha': ['hcaptcha'],
}

TIMING_PROFILES = {
    'human_casual': {'min_ms': 1200, 'max_ms': 4500, 'think_probability': 0.3, 'think_ms': (5000, 15000)},
    'human_fast': {'min_ms': 400, 'max_ms': 1500, 'think_probability': 0.1, 'think_ms': (2000, 5000)},
    'automated_slow': {'min_ms': 800, 'max_ms': 2000, 'think_probability': 0.0, 'think_ms': (0, 0)},
    'automated_fast': {'min_ms': 100, 'max_ms': 500, 'think_probability': 0.0, 'think_ms': (0, 0)},
    'stealth': {'min_ms': 2000, 'max_ms': 8000, 'think_probability': 0.4, 'think_ms': (10000, 30000)},
}


class EvasionProfile:
    def __init__(self, config: dict, target: str):
        self.config = config
        self.target = target
        self.evasion_cfg = config.get('evasion', {})
        self.proxies: List[str] = self.evasion_cfg.get('proxy_list', [])
        self.proxy_index = 0
        self.proxy_failures: Dict[str, int] = {}
        self.request_count = 0
        self.detection_events = 0
        self.waf_detected: Optional[str] = None
        self.timing_profile = self.evasion_cfg.get('timing_profile', 'human_fast')
        self.ua_category = self.evasion_cfg.get('ua_category', 'chrome_win')
        self.current_ua = self._pick_ua()
        self.referer_chain: List[str] = []

    def _pick_ua(self) -> str:
        pool = USER_AGENTS.get(self.ua_category, USER_AGENTS['chrome_win'])
        return random.choice(pool)

    def rotate_ua(self) -> str:
        self.current_ua = self._pick_ua()
        return self.current_ua

    def _random_ip(self) -> str:
        while True:
            ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
            if not (ip.startswith('10.') or ip.startswith('192.168.') or ip.startswith('172.16.') or ip.startswith('127.')):
                return ip

    def get_headers(self, url: str = '', method: str = 'GET', content_type: str = '') -> Dict[str, str]:
        if 'chrome' in self.ua_category:
            profile = dict(HEADER_PROFILES['chrome'])
        elif 'firefox' in self.ua_category:
            profile = dict(HEADER_PROFILES['firefox'])
        elif content_type == 'application/json':
            profile = dict(HEADER_PROFILES['api_client'])
        else:
            profile = dict(HEADER_PROFILES['chrome'])
        profile['User-Agent'] = self.current_ua
        if self.referer_chain:
            profile['Referer'] = self.referer_chain[-1]
        if self.evasion_cfg.get('spoof_xff', True):
            profile['X-Forwarded-For'] = self._random_ip()
        langs = ['en-US,en;q=0.9', 'en-GB,en;q=0.8', 'en-AU,en;q=0.9,en-US;q=0.8']
        profile['Accept-Language'] = random.choice(langs)
        if method == 'POST' and content_type:
            profile['Content-Type'] = content_type
        return profile

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.proxy_index % len(self.proxies)]
            self.proxy_index += 1
            if self.proxy_failures.get(proxy, 0) < 3:
                return proxy
        return None

    def mark_proxy_failed(self, proxy: str):
        self.proxy_failures[proxy] = self.proxy_failures.get(proxy, 0) + 1

    def sleep(self, multiplier: float = 1.0):
        profile = TIMING_PROFILES.get(self.timing_profile, TIMING_PROFILES['human_fast'])
        delay_ms = random.randint(profile['min_ms'], profile['max_ms']) * multiplier
        if random.random() < profile['think_probability']:
            delay_ms += random.randint(*profile['think_ms'])
        time.sleep(delay_ms / 1000.0)
        self.request_count += 1

    def detect_waf(self, response_headers: dict, response_body: str = '') -> Optional[str]:
        headers_lower = {k.lower(): v.lower() for k, v in response_headers.items()}
        combined = ' '.join(headers_lower.keys()) + ' ' + ' '.join(headers_lower.values()) + ' ' + response_body.lower()
        for waf_name, signatures in WAF_SIGNATURES.items():
            if any(sig.lower() in combined for sig in signatures):
                self.waf_detected = waf_name
                log.warning(f"WAF detected: {waf_name}")
                return waf_name
        return None

    def get_waf_bypass_headers(self, waf_name: str) -> Dict[str, str]:
        bypass = {}
        if waf_name == 'cloudflare':
            bypass['CF-Connecting-IP'] = self._random_ip()
            bypass['X-Real-IP'] = self._random_ip()
            bypass['True-Client-IP'] = self._random_ip()
        elif waf_name == 'akamai':
            bypass['X-Forwarded-For'] = self._random_ip()
            bypass['X-Original-URL'] = '/'
        elif waf_name in ('datadome', 'perimeterx', 'kasada'):
            self.rotate_ua()
            bypass['User-Agent'] = self.current_ua
            self.timing_profile = 'human_casual'
        return bypass

    def handle_rate_limit(self, retry_after: int = 60):
        self.detection_events += 1
        backoff = retry_after + random.randint(10, 30)
        log.warning(f"Rate limit — backing off {backoff}s, rotating UA and proxy")
        self.rotate_ua()
        time.sleep(backoff)

    def get_tls_config(self) -> dict:
        cipher_profiles = [
            ['TLS_AES_128_GCM_SHA256', 'TLS_AES_256_GCM_SHA384', 'TLS_CHACHA20_POLY1305_SHA256'],
            ['TLS_AES_256_GCM_SHA384', 'TLS_CHACHA20_POLY1305_SHA256', 'TLS_AES_128_GCM_SHA256'],
            ['TLS_CHACHA20_POLY1305_SHA256', 'TLS_AES_128_GCM_SHA256', 'TLS_AES_256_GCM_SHA384'],
        ]
        return {
            'cipher_suites': random.choice(cipher_profiles),
            'tls_version': random.choice(['TLSv1.2', 'TLSv1.3']),
            'verify': True,
        }

    def to_dict(self) -> dict:
        return {
            'target': self.target,
            'ua_category': self.ua_category,
            'current_ua': self.current_ua,
            'timing_profile': self.timing_profile,
            'proxy_count': len(self.proxies),
            'active_proxy': self.get_proxy(),
            'waf_detected': self.waf_detected,
            'request_count': self.request_count,
            'detection_events': self.detection_events,
            'tls_config': self.get_tls_config(),
        }


def check_proxy_health(proxy: str, timeout: int = 5) -> bool:
    try:
        host_port = proxy.split('://')[-1].split('@')[-1]
        host, port = host_port.rsplit(':', 1)
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def build_evasion_profile(target: str, config: dict) -> EvasionProfile:
    evasion_cfg = config.get('evasion', {})
    proxy_file = evasion_cfg.get('proxy_file', '')
    if proxy_file and os.path.exists(proxy_file):
        with open(proxy_file) as f:
            loaded = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        evasion_cfg['proxy_list'] = evasion_cfg.get('proxy_list', []) + loaded
    target_lower = target.lower()
    if any(x in target_lower for x in ['api.', '/api/', '/v1/', '/v2/', '/graphql']):
        evasion_cfg.setdefault('ua_category', 'chrome_win')
        evasion_cfg.setdefault('timing_profile', 'automated_slow')
    elif any(x in target_lower for x in ['mobile', 'app.', 'm.']):
        evasion_cfg.setdefault('ua_category', 'mobile_ios')
        evasion_cfg.setdefault('timing_profile', 'human_fast')
    else:
        evasion_cfg.setdefault('ua_category', random.choice(['chrome_win', 'chrome_mac', 'firefox_win']))
        evasion_cfg.setdefault('timing_profile', 'human_fast')
    config['evasion'] = evasion_cfg
    return EvasionProfile(config, target)


def run(target: str, config: dict) -> dict:
    log.info('=' * 60)
    log.info('Stage 6 — Anti-Detection & Evasion (Production v2.1)')
    log.info(f'Target: {target}')
    start_time = datetime.utcnow()
    tools_invoked = []

    profile = build_evasion_profile(target, config)
    tools_invoked.append('evasion_profile_builder')

    healthy_proxies = []
    if profile.proxies:
        log.info(f"Health-checking {min(len(profile.proxies), 20)} proxies...")
        for proxy in profile.proxies[:20]:
            if check_proxy_health(proxy):
                healthy_proxies.append(proxy)
        log.info(f"Healthy: {len(healthy_proxies)}/{len(profile.proxies[:20])}")
        profile.proxies = healthy_proxies + profile.proxies[20:]
        tools_invoked.append('proxy_health_check')

    if config.get('evasion', {}).get('rotate_user_agents', True):
        tools_invoked.append('ua_rotation')

    tls_config = profile.get_tls_config()
    tools_invoked.append('tls_fingerprint_variance')
    tools_invoked.append(f"timing_jitter_{profile.timing_profile}")
    tools_invoked.append('header_normalization')
    tools_invoked.append('waf_detection_ready')
    tools_invoked.append('xff_spoofing')

    sample_headers = profile.get_headers(url=target)
    timing = TIMING_PROFILES[profile.timing_profile]
    elapsed = (datetime.utcnow() - start_time).total_seconds()

    findings = {
        'stage': 6,
        'name': 'EVASION',
        'target': target,
        'timestamp': start_time.isoformat(),
        'elapsed_seconds': round(elapsed, 2),
        'tools_invoked': tools_invoked,
        'evasion_profile': profile.to_dict(),
        'healthy_proxy_count': len(healthy_proxies),
        'sample_headers': sample_headers,
        'tls_config': tls_config,
        'timing_profile': profile.timing_profile,
        'timing_range_ms': f"{timing['min_ms']}-{timing['max_ms']}",
        'waf_bypass_ready': True,
        'status': 'CONFIGURED',
    }

    config['_evasion_profile'] = profile
    log.info(f"Stage 6 complete — {len(tools_invoked)} evasion modules active")
    return findings
