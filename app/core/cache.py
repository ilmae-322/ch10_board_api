"""간단한 인메모리 TTL 캐시.

게시글 목록처럼 자주 조회되고 잠깐 오래된 값이어도 괜찮은 응답을 저장한다.
글이 작성/수정/삭제되면 clear()로 무효화한다.
검색어마다 키가 생기므로 최대 개수를 넘으면 가장 오래된 항목부터 버린다.
(서버 프로세스가 여러 개로 늘어나면 Redis 같은 외부 캐시로 교체한다.)
"""

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store.pop(key, None)
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
