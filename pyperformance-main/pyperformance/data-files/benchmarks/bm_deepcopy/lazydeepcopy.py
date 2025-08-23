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
          1) Build an 'inputs' list passed to copy.deepcopy(inputs) once.
             How we build this list depends on alias policy:
                - "preserve": If the *same* object identity appears multiple times
                  in the queue, we only insert it once into inputs and keep a map
                  from each queue position to the single shared index.
                  deepcopy preserves aliasing within a container, so we get exactly
                  one output instance for that input and we can fan it out to all
                  handles that referenced it.
                - "duplicate": We insert each object as a distinct entry, so the
                  outputs are all distinct deepcopies.
          2) Perform one copy.deepcopy on 'inputs'.
          3) Fan out the produced copies to each queued handle based on the map.
          4) Clear the queue.

        Notes:
          - This preserves regular deepcopy semantics *within* the batch according
            to the selected alias policy.
          - If you need time-of-request exactness, use consistency="strict".
        """
        # Fast path: if all queued items asked for duplication, we can build inputs directly.
        if all(alias == "duplicate" for _, _, alias in self._queue):
            inputs = [obj for (_h, obj, _alias) in self._queue]
            outputs = copy.deepcopy(inputs)
            for (h, _obj, _alias), c in zip(self._queue, outputs):
                h._value = c
                h._ready = True
            self._queue.clear()
            self._pending_bytes = 0
            return

        # Mixed or all "preserve": we want equal identities to share a single input slot.
        inputs: List[Any] = []
        index_for_queue_pos: List[int] = []  # queue position -> inputs index
        seen: dict[int, int] = {}            # id(obj) -> inputs index

        for (h, obj, alias) in self._queue:
            if alias == "preserve":
                key = id(obj)
                if key in seen:
                    # Already inserted: remember existing index so both handles share one output.
                    index_for_queue_pos.append(seen[key])
                else:
                    # First time we see this identity: insert into inputs and record its index.
                    seen[key] = len(inputs)
                    index_for_queue_pos.append(seen[key])
                    inputs.append(obj)
            else:
                # "duplicate" item participates as a unique input.
                index_for_queue_pos.append(len(inputs))
                inputs.append(obj)

        # One deepcopy of the entire inputs list.
        outputs = copy.deepcopy(inputs)

        # Fan out results to each handle.
        for (h, _obj, _alias), src_idx in zip(self._queue, index_for_queue_pos):
            h._value = outputs[src_idx]
            h._ready = True

        # Reset queue/state.
        self._queue.clear()
        self._pending_bytes = 0


class _Proxy:
    """
    A minimal lazy proxy that resolves its target on first use.

    It delegates common Python operations to the resolved object:
      - attribute access (__getattr__)
      - item access (__getitem__/__setitem__)
      - iteration, len(), truthiness, str()/repr()

    Caveat:
      - Python may bypass __getattr__ for some dunder/operator methods on builtins.
        For full transparency, consider integrating 'wrapt.ObjectProxy'. This proxy
        focuses on the most common interactions.
    """
    __slots__ = ("_batcher", "_handle")

    def __init__(self, batcher: DeepcopyBatcher, handle: _Handle) -> None:
        # Store references via object.__setattr__ to avoid recursive __setattr__.
        object.__setattr__(self, "_batcher", batcher)
        object.__setattr__(self, "_handle", handle)

    # --------- Internal helper ---------

    def _resolve(self) -> Any:
        """
        Materialize and return the real deep-copied object behind this proxy.

        Implementation:
          - Calls batcher.get(handle), which may trigger a batch flush.
          - Caches nothing locally; always fetches from the handle (already ready after first call).
        """
        return self._batcher.get(self._handle)

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
