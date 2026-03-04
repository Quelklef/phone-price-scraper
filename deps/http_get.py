import json
import re
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

import pretty_log

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_COOKIE_DIR = _PROJECT_DIR / "data" / "cookies"
_CACHE_DIR = _PROJECT_DIR / "data" / "http-cache"

_HOST_CONFIGS = {
    "www.amazon.com": {
        "seller": "amazon",
        "headers": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Priority": "u=0, i",
            "TE": "trailers",
        },
    },
    "www.ebay.com": {
        "seller": "ebay",
        "headers": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.ebay.com/sch/i.html?_fsrp=1&_nkw=google+pixel",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Priority": "u=0, i",
            "TE": "trailers",
        },
    },
    "www.backmarket.com": {
        "seller": "backmarket",
        "headers": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://duckduckgo.com/",
            "Alt-Used": "www.backmarket.com",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Priority": "u=0, i",
            "TE": "trailers",
        },
    },
}

_DEFAULT_CONFIG = {
    "seller": "web",
    "headers": {"User-Agent": "Mozilla/5.0"},
}


class WriteDeferredCacheSession:
    """A cache facade that defers writes in-memory until explicit commit.

    Reads and writes are intentionally decoupled from the source cache:
    - Reads first check this session's in-memory writes.
    - If missing, reads check the source cache's on-disk cache/index state.
    - Cache misses are fetched over HTTP and stored only in-memory here.

    This means new writes done by the source cache remain visible here, while
    this session's writes remain isolated until commit_to(...) is called.
    """

    def __init__(self, source_cache):
        self._source_cache = source_cache
        self._responses = {}
        self._committed = False

    def _record_response(self, url, text, status_code=None):
        self._responses[url] = {"text": text, "status_code": status_code}

    def _get_local_response(self, url):
        payload = self._responses.get(url)
        if payload is None:
            return None
        status_code = payload.get("status_code")
        text = payload["text"]
        if status_code == 404:
            _raise_cached_http_error(url, status_code, text)
        return text

    def get(self, url):
        import deps

        timing = deps.timing
        with timing.time_stage("http.get.cached"):
            url_lock = self._source_cache._get_url_lock(url)
            lock_wait_timer = timing.stage_start("cache.http.lock_wait.url")
            with url_lock:
                lock_wait_timer.end()
                with timing.time_stage("cache.http.fetch"):
                    local_text = self._get_local_response(url)
                    if local_text is not None:
                        return local_text

                    cached_text = self._source_cache._read_cached_response(url)
                    if cached_text is not None:
                        return cached_text

                    try:
                        with timing.time_stage("cache.http.fetch_miss"):
                            text = self._source_cache._request_text(url)
                        self._record_response(url, text, status_code=None)
                        return text
                    except Exception as exc:
                        status_code = getattr(getattr(exc, "response", None), "status_code", None)
                        if status_code == 404:
                            text = getattr(exc.response, "text", "")
                            self._record_response(url, text, status_code=404)
                        raise

    def commit_to(self, other):
        if self._committed:
            return
        for url, payload in self._responses.items():
            other._set_cached_response(
                url,
                payload["text"],
                status_code=payload.get("status_code"),
            )
        self._committed = True

    def pending_urls(self):
        return tuple(self._responses.keys())


class HttpCache:
    def __init__(
        self,
        *,
        cache_dir=None,
        cookie_dir=None,
        host_configs=None,
        default_config=None,
    ):
        self._cache_dir = Path(cache_dir) if cache_dir is not None else _CACHE_DIR
        self._results_dir = self._cache_dir / "results"
        self._entries_file = self._cache_dir / "entries.json"
        self._cookie_dir = Path(cookie_dir) if cookie_dir is not None else _COOKIE_DIR

        self._host_configs = host_configs or _HOST_CONFIGS
        self._default_config = default_config or _DEFAULT_CONFIG

        self._results_dir.mkdir(parents=True, exist_ok=True)

        self._write_lock = threading.RLock()
        self._url_locks = {}
        self._url_locks_lock = threading.Lock()

        self._entries = self._load_entries()
        self._cache_index = {entry["url"]: entry["resultKey"] for entry in self._entries}
        self._entry_by_url = {entry["url"]: entry for entry in self._entries}

    def _host_config(self, url):
        host = urlparse(url).netloc.lower()
        return self._host_configs.get(host, self._default_config)

    @staticmethod
    def _slugify_host(host):
        return re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")

    @staticmethod
    def _slugify_url(url):
        parsed = urlparse(url)
        slug = (parsed.netloc + parsed.path).replace("/", "-")
        return re.sub(r"[^a-zA-Z0-9\-]", "", slug)[:50]

    def _cookie_path_for_host(self, host):
        return self._cookie_dir / self._slugify_host(host)

    def _load_cookie_for_host(self, host):
        path = self._cookie_path_for_host(host)
        if not path.exists():
            return None
        cookie = path.read_text(encoding="utf-8").strip()
        return cookie or None

    def _save_cookie_for_host(self, host, cookie):
        self._cookie_dir.mkdir(parents=True, exist_ok=True)
        self._cookie_path_for_host(host).write_text(cookie.strip(), encoding="utf-8")

    def _prompt_cookie_for_host(self, host, seller, reason):
        import deps

        printer = deps.printer
        printer.print()
        printer.print(f"[cookie] {seller} ({host}) requires an updated cookie: {reason}")
        printer.print("[cookie] Open the site in a browser while logged OUT, then copy the Cookie request header.")
        printer.print(f"[cookie] Save location: {self._cookie_path_for_host(host)}")
        cookie = printer.input("Paste Cookie header value: ").strip()
        if not cookie:
            raise RuntimeError(f"Missing cookie input for {host}.")
        self._save_cookie_for_host(host, cookie)
        return cookie

    def _load_entries(self):
        if self._entries_file.exists():
            return json.loads(self._entries_file.read_text(encoding="utf-8"))
        return []

    def _save_entries(self):
        self._entries_file.parent.mkdir(parents=True, exist_ok=True)
        self._entries_file.write_text(json.dumps(self._entries, indent=2), encoding="utf-8")

    def _get_url_lock(self, url):
        with self._url_locks_lock:
            lock = self._url_locks.get(url)
            if lock is None:
                lock = threading.Lock()
                self._url_locks[url] = lock
            return lock

    def _remove_entry_for_url(self, url):
        with self._write_lock:
            if self._entry_by_url.pop(url, None) is None:
                return
            self._cache_index.pop(url, None)
            for idx, entry in enumerate(self._entries):
                if entry["url"] == url:
                    del self._entries[idx]
                    break
            self._save_entries()

    def _set_cached_response(self, url, text, status_code=None):
        self._remove_entry_for_url(url)
        self._persist_response(url, text, status_code=status_code)

    def _entry_for_url(self, url):
        return self._entry_by_url.get(url)

    def _persist_response(self, url, text, status_code=None):
        import deps

        timing = deps.timing
        slug = self._slugify_url(url)
        unique_id = str(uuid.uuid4())[:8]
        result_key = f"{slug}-{unique_id}.html"
        result_path = self._results_dir / result_key
        with timing.time_stage("cache.http.write_result"):
            result_path.write_text(text, encoding="utf-8")

        with self._write_lock:
            with timing.time_stage("cache.http.write_index"):
                entry = {"url": url, "resultKey": result_key}
                if status_code is not None:
                    entry["statusCode"] = status_code
                self._entries.append(entry)
                self._cache_index[url] = result_key
                self._entry_by_url[url] = entry
                self._save_entries()

    def _request_text(self, url):
        import deps

        timing = deps.timing
        config = self._host_config(url)
        host = urlparse(url).netloc.lower()
        headers = dict(config["headers"])
        seller = config["seller"]

        existing_cookie = self._load_cookie_for_host(host)
        if existing_cookie is not None:
            headers["Cookie"] = existing_cookie

        pretty_log.fetch(seller, url)
        with timing.time_stage("http.request"):
            resp = requests.get(url, headers=headers)

        prompt_count = 0
        while resp.status_code == 403 and prompt_count < 3:
            prompt_count += 1
            refreshed_cookie = self._prompt_cookie_for_host(
                host,
                seller,
                f"received HTTP 403 (attempt {prompt_count})",
            )
            headers["Cookie"] = refreshed_cookie
            with timing.time_stage("http.request"):
                resp = requests.get(url, headers=headers)

        resp.raise_for_status()
        return resp.text

    def _read_cached_response(self, url):
        import deps

        timing = deps.timing
        result_key = self._cache_index.get(url)
        if result_key is None:
            return None
        entry = self._entry_for_url(url)
        path = self._results_dir / result_key
        try:
            with timing.time_stage("cache.http.read_hit"):
                text = path.read_text(encoding="utf-8")
            status_code = entry.get("statusCode") if entry else None
            if status_code == 404:
                _raise_cached_http_error(url, status_code, text)
            return text
        except FileNotFoundError:
            self._remove_entry_for_url(url)
            return None

    def _fetch_locked(self, url):
        import deps

        timing = deps.timing
        cached_text = self._read_cached_response(url)
        if cached_text is not None:
            return cached_text

        try:
            with timing.time_stage("cache.http.fetch_miss"):
                text = self._request_text(url)
            self._persist_response(url, text)
            return text
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 404:
                text = getattr(exc.response, "text", "")
                self._persist_response(url, text, status_code=404)
            raise

    def get(self, url):
        import deps

        timing = deps.timing
        with timing.time_stage("http.get.cached"):
            url_lock = self._get_url_lock(url)
            lock_wait_timer = timing.stage_start("cache.http.lock_wait.url")
            with url_lock:
                lock_wait_timer.end()
                with timing.time_stage("cache.http.fetch"):
                    return self._fetch_locked(url)

    def create_write_deferred_session(self):
        return WriteDeferredCacheSession(self)


def _raise_cached_http_error(url, status_code, text):
    reason = "Not Found" if status_code == 404 else "Error"
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    response._content = text.encode("utf-8")
    raise requests.HTTPError(
        f"{status_code} Client Error: {reason} for url: {url}",
        response=response,
    )
