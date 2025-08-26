"""
lazydeepcopy.py

A small library that batches multiple deepcopy requests and resolves them
together on first access (copy-on-access). It reduces Python-level overhead
by calling copy.deepcopy once on a list of pending inputs, then fans the
results back to individual handles/proxies.

Two user-facing modes:
  1) Explicit: defer(obj) -> handle; get(handle) -> real copy (flushes batch).
  2) Transparent: defer_proxy(obj) -> proxy; any access auto-resolves/flushes.

Semantics are controllable:
  - consistency="at_access": snapshot is taken at first access/flush time.
  - consistency="strict": snapshot is taken at defer() time (excluded from batch).
  - alias policy: "preserve" (multiple handles to same input share one output
    instance within a batch) or "duplicate" (force distinct outputs).
"""

from __future__ import annotations

import copy
import threading
from typing import Any, List, Tuple, Optional


class _Handle:
    """
    Opaque token representing a deferred deepcopy result.

    Fields:
      _value: the resolved (materialized) deep-copied object once ready.
      _ready: whether this handle has been resolved (True) or is still pending.
    """
    __slots__ = ("_value", "_ready")

    def __init__(self) -> None:
        self._value: Any = None
        self._ready: bool = False


class DeepcopyBatcher:
    """
    Batches multiple deepcopy requests and resolves them together.

    Key ideas:
      - Each defer(obj) enqueues (obj) plus a return handle, without copying yet.
      - On get(handle) or flush(), the batcher performs  *one*  copy.deepcopy
        call on a list of inputs, mapping each produced copy back to its handle.
      - This amortizes Python interpreter recursion/dispatch costs.
      - Alias policy controls whether repeated references to the same input
        (within a batch) should share one output instance or be duplicated.

    Parameters:
      max_items   : int           -> when queue length reaches this, auto-flush.
      max_bytes   : Optional[int] -> (optional) rough soft cap for queued size.
                                     (For simplicity, not actively tracked below.)
      consistency : str           -> "at_access" (default) or "strict".
                                    "strict" snapshots immediately (no batching).
      alias       : str           -> "preserve" (default) or "duplicate".
                                    See _flush_locked for details.

    Thread-safety:
      - All public methods that modify internal state grab a re-entrant lock.
    """

    def __init__(
        self,
        max_items: int = 64,
        max_bytes: Optional[int] = None,
        consistency: str = "at_access",
        alias: str = "preserve",
    ) -> None:
        self._lock = threading.RLock()
        # Internal queue of pending items: (handle, obj, alias_policy_at_enqueue)
        self._queue: List[Tuple[_Handle, Any, str]] = []
        self._max_items = max_items
        self._max_bytes = max_bytes
        self._consistency = consistency
        self._alias = alias
        # Optional space for size tracking (not implemented here).
        self._pending_bytes = 0

    # ------------------------- Public API ---------------------------------

    def defer(
        self,
        obj: Any,
        *,
        consistency: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> _Handle:
        """
        Enqueue a deepcopy request without performing it yet.

        Args:
          obj: The object to deep copy later.
          consistency: Optional override of batcher-wide policy:
                       - "at_access": snapshot at flush/get time (enables batching).
                       - "strict":    snapshot now (single immediate deepcopy).
          alias: Optional override of alias policy for this item:
                 - "preserve": repeated references to the same input within this batch
                               map to a single output instance (deepcopy preserves aliasing).
                 - "duplicate": force distinct outputs (treat as unique input).

        Returns:
          _Handle: a token that will receive the deep-copied object upon flush/get.

        Behavior:
          - If consistency == "strict", we *immediately* perform a deepcopy for this item
            (excluded from batching) and return a ready handle.
          - Else, we append to the pending queue and maybe auto-flush if thresholds hit.
        """
        if consistency is None:
            consistency = self._consistency
        if alias is None:
            alias = self._alias

        h = _Handle()

        if consistency == "strict":
            # Snapshot now: exact state at call time; do not participate in batching.
            h._value = copy.deepcopy(obj)
            h._ready = True
            return h

        with self._lock:
            self._queue.append((h, obj, alias))
            if self._should_flush_locked():
                self._flush_locked()

        return h

    def defer_proxy(
        self,
        obj: Any,
        *,
        consistency: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> "_Proxy":
        """
        Enqueue a deferred deepcopy and return a proxy (lazy object).

        Any access to the proxy (e.g., attribute access, item get) will
        transparently trigger a batch flush, materializing this and all
        other pending copies.

        Args/Returns:
          Same policy overrides as defer(). Returns a _Proxy wrapper.
        """
        h = self.defer(obj, consistency=consistency, alias=alias)
        return _Proxy(self, h)

    def get(self, h: _Handle) -> Any:
        """
        Resolve one handle and return its materialized deep copy.

        If the handle is not ready:
          - Trigger a flush(), which resolves *all* pending items together.
          - Return this handle's copy.

        If already ready, returns the existing materialized copy.
        """
        if h._ready:
            return h._value
        self.flush()
        return h._value

    def flush(self) -> None:
        """
        Force a batch resolution of all pending deepcopies.

        Implementation:
          - Builds a list of inputs in a shape that captures alias policy.
          - Calls copy.deepcopy(inputs) once.
          - Distributes results back to each pending handle.
        """
        with self._lock:
            if not self._queue:
                return
            self._flush_locked()

    # ------------------------- Internals ----------------------------------

    def _should_flush_locked(self) -> bool:
        """
        Decide whether to auto-flush now based on thresholds.

        Current policy:
          - Flush when the number of queued items reaches max_items.
          - (Optional) If max_bytes is configured and exceeded (not tracked here).
        """
        if len(self._queue) >= self._max_items:
            return True
        if self._max_bytes is not None and self._pending_bytes >= self._max_bytes:
            return True
        return False

    def _flush_locked(self) -> None:
        """
        Resolve the current queue in one batch (must be called under lock).

        Steps:
          1) Partition the queue into 'preserve' and 'duplicate' items.
          2) For 'duplicate' items, perform a unique copy.deepcopy for each one
             to guarantee they are distinct instances.
          3) For 'preserve' items, use the original batching logic: build a
             list of unique inputs, perform one deepcopy, and fan out the
             aliased results.
          4) Clear the queue.
        """
        if not self._queue:
            return

        # --- FIX STARTS HERE ---

        # 1. Partition the queue
        preserve_items = []
        duplicate_items = []
        for item in self._queue:
            handle, obj, alias = item
            if alias == "duplicate":
                duplicate_items.append(item)
            else: # 'preserve'
                preserve_items.append(item)
        
        # 2. Handle 'duplicate' items by copying them individually
        for h, obj, _ in duplicate_items:
            h._value = copy.deepcopy(obj)
            h._ready = True

        # 3. Handle 'preserve' items with the original batching logic
        if preserve_items:
            inputs: List[Any] = []
            index_for_queue_pos: List[int] = []  # queue position -> inputs index
            seen: dict[int, int] = {}            # id(obj) -> inputs index

            for (h, obj, alias) in preserve_items:
                # We know alias is "preserve" here
                key = id(obj)
                if key in seen:
                    index_for_queue_pos.append(seen[key])
                else:
                    seen[key] = len(inputs)
                    index_for_queue_pos.append(seen[key])
                    inputs.append(obj)
            
            # One deepcopy of the entire inputs list for preserved items.
            if inputs:
                outputs = copy.deepcopy(inputs)

                # Fan out results to each handle.
                for (h, _obj, _alias), src_idx in zip(preserve_items, index_for_queue_pos):
                    h._value = outputs[src_idx]
                    h._ready = True

        # --- FIX ENDS HERE ---

        # Reset queue/state.
        self._queue.clear()
        self._pending_bytes = 0


class _Proxy:
    """
    A minimal lazy proxy that resolves its target on first use.
    ...
    """
    __slots__ = ("_batcher", "_handle")

    def __init__(self, batcher: DeepcopyBatcher, handle: _Handle) -> None:
        # ... (no changes here)
        object.__setattr__(self, "_batcher", batcher)
        object.__setattr__(self, "_handle", handle)

    # --------- Internal helper ---------

    def _resolve(self) -> Any:
        # ... (no changes here)
        return self._batcher.get(self._handle)

    # --- ADD THIS METHOD ---
    def __deepcopy__(self, memo: dict) -> Any:
        """
        Custom deepcopy implementation for the proxy.

        This ensures that when `copy.deepcopy()` encounters a proxy, it copies
        the underlying, resolved data rather than the proxy object itself.
        """
        # 1. Resolve the proxy to get the real object.
        resolved_obj = self._resolve()
        # 2. Call deepcopy on the real object, passing the memo dict along.
        return copy.deepcopy(resolved_obj, memo)
    # --- END OF ADDED METHOD ---

    # --------- Delegations for common operations ---------

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the resolved object (triggers resolution)."""
        return getattr(self._resolve(), name)

    def __getitem__(self, key: Any) -> Any:
        """Delegate item access (obj[key]) to the resolved object."""
        return self._resolve()[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        """Delegate item assignment (obj[key] = value) to the resolved object."""
        self._resolve()[key] = value

    def __iter__(self):
        """Delegate iteration (for x in obj) to the resolved object."""
        return iter(self._resolve())

    def __len__(self) -> int:
        """Delegate len(obj) to the resolved object."""
        return len(self._resolve())

    def __bool__(self) -> bool:
        """Delegate truthiness (if obj:) to the resolved object."""
        return bool(self._resolve())

    def __repr__(self) -> str:
        """
        Show a helpful representation before/after resolution.
        Does not force resolution unless needed for repr of the target.
        """
        if not self._handle._ready:
            return "<LazyDeepCopy unresolved>"
        return repr(self._handle._value)

    def __str__(self) -> str:
        """Delegate str(obj) to the resolved object (triggers resolution)."""
        return str(self._resolve())
