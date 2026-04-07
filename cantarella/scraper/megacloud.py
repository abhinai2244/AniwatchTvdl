#@cantarellabots
from cantarella.core.proxy import get_random_proxy, get_proxy_dict
import base64
import re
import json
from curl_cffi import requests
from typing import Callable, Iterable, Any

def hash_str(key: str) -> int:
    key_value = 0
    for char in key:
        key_value = (key_value * 31 + ord(char)) & 0xFFFFFFFF
    return key_value

class Megacloud:
    base_url = "https://megacloud.tv"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "origin": base_url,
        "referer": base_url + "/",
    }

    def __init__(self, embed_url: str) -> None:
        self.embed_url = embed_url

    def _extract_client_key(self, html) -> str:
        match = re.search(r'([a-zA-Z0-9]{48})|x: "([a-zA-Z0-9]{16})", y: "([a-zA-Z0-9]{16})", z: "([a-zA-Z0-9]{16})"}', html)
        if not match: return ""
        groups = match.groups()
        if groups[0]: return groups[0]
        return "".join(filter(None, groups[1:]))

    def _lcg(self, n: int) -> int:
        return (n * 1103515245 + 12345) & 0x7FFFFFFF

    def _shuffle_sources(self, sources: list[str], key: str) -> list[str]:
        if not key: return sources
        array_count = len(sources) // len(key)
        arrays = [[""] * len(key) for _ in range(array_count)]
        key_dict = {i: char for i, char in enumerate(key)}
        key_sorted = {i: char for i, char in sorted(key_dict.items(), key=lambda p: p[1])}
        p = 0
        for idx in key_sorted.keys():
            for arr_idx in range(array_count):
                if p < len(sources):
                    arrays[arr_idx][idx] = sources[p]
                    p += 1
        res = []
        for arr in arrays: res.extend(arr)
        return res

    def _process_sources(self, encrypted_data: str, key: str) -> str:
        sources = list(encrypted_data)
        current_hash = hash_str(key)
        new_sources = []
        for char in sources:
            current_hash = self._lcg(current_hash)
            val1 = ord(char) - 32
            val2 = current_hash % 95
            v = (val1 - val2) % 95 + 32
            new_sources.append(chr(v))
        shuffled = self._shuffle_sources(new_sources, key)
        return "".join(shuffled)

    def extract(self) -> dict:
        sid_match = re.search(r"e-1/([a-zA-Z0-9]+)", self.embed_url)
        if not sid_match: return {"sources": [], "tracks": []}
        sid = sid_match.group(1)

        # Derive base_url from embed_url
        base_url_match = re.search(r'(https?://[^/]+)', self.embed_url)
        base_url = base_url_match.group(1) if base_url_match else self.base_url

        try:
            session = requests.Session()
            proxy_dict = get_proxy_dict(get_random_proxy())
            if proxy_dict:
                session.proxies.update(proxy_dict)

            headers = self.headers.copy()
            headers["referer"] = "https://aniwatchtv.to/"

            # Prefer megacloud.tv over megacloud.blog
            curr_embed_url = self.embed_url.replace(".blog", ".tv")
            base_url = "https://megacloud.tv"

            resp_html = session.get(curr_embed_url, headers=headers, impersonate="chrome").text
            client_key = self._extract_client_key(resp_html)

            get_src_url = f"{base_url}/embed-2/v3/e-1/getSources"
            headers["referer"] = curr_embed_url

            resp_obj = session.get(get_src_url, headers=headers, params={"id": sid, "_k": client_key}, impersonate="chrome")
            resp = resp_obj.json()

            if isinstance(resp.get('sources'), str):
                decrypted = self._process_sources(resp['sources'], client_key)
                resp['sources'] = json.loads(decrypted)

            if "sources" not in resp: resp["sources"] = []
            if "tracks" not in resp: resp["tracks"] = []
            return resp
        except Exception as e:
            print(f"Megacloud error: {e}")
            return {"sources": [], "tracks": []}