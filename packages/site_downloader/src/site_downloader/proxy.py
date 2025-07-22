import logging, threading, os, asyncio

try:
    from swiftshadow.classes import ProxyInterface
    from swiftshadow import QuickProxy
except Exception:  # pragma: no cover
    ProxyInterface = None  # type: ignore
    QuickProxy = None  # type: ignore

logger = logging.getLogger(__name__)

__all__ = ["ProxyPool"]

class ProxyPool:
    """
    Wrapper around SwiftShadow ProxyInterface using autoRotate + autoUpdate.
    Optional background refresh for multi-hour batches.
    """
    def __init__(
        self,
        max_proxies: int = 50,
        cache_minutes: int = 10,
        verbose: int = 0,
        enable_background_refresh: bool = False,
        refresh_interval_minutes: int | None = None,
    ):
        if ProxyInterface is None:
            raise RuntimeError("swiftshadow not installed; cannot create ProxyPool.")
        self.verbose = verbose
        self._swift = None  # type: ignore
        self._init_task: asyncio.Task | None = None
        self._init_exception: BaseException | None = None
        try:
            loop = asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            loop = None
            in_loop = False

        # Inside a running loop we **must not** let swiftshadow call synchronous .update()
        # (it uses asyncio.run internally). So we disable autoUpdate and schedule async_update.
        if in_loop:
            self._swift = ProxyInterface(autoRotate=True,
                                       autoUpdate=False,
                                       maxProxies=max_proxies,
                                       cachePeriod=cache_minutes,
                                       debug=verbose >= 2)
            self._init_task = loop.create_task(self._async_initial_update(), name="swiftshadow-initial-update")
        else:
            # Safe to allow autoUpdate=True outside event loop
            self._swift = ProxyInterface(autoRotate=True,
                                       autoUpdate=True,
                                       maxProxies=max_proxies,
                                       cachePeriod=cache_minutes,
                                       debug=verbose >= 2)
        self._bg_thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        env_interval = os.getenv("SD_PROXY_BG_REFRESH_INTERVAL_MIN")
        if env_interval and env_interval.isdigit():
            refresh_interval_minutes = int(env_interval)
            enable_background_refresh = True
        if enable_background_refresh:
            interval = (refresh_interval_minutes
                        if refresh_interval_minutes is not None
                        else max(1, cache_minutes // 2))
            self._start_background_refresh(interval)

    async def _async_initial_update(self):
        """Internal task performing initial async update when constructed in loop."""
        try:
            if hasattr(self._swift, "async_update"):
                await self._swift.async_update()
            else:
                # Fallback (should not happen if swiftshadow provides async_update)
                await asyncio.to_thread(self._swift.update)
        except Exception as e:  # pragma: no cover
            self._init_exception = e
            logger.warning("Initial proxy async_update failed: %s", e)

    async def ensure_ready(self):
        """
        Await initial population when created inside a running event loop.
        Safe to call multiple times.
        """
        if self._init_task:
            if not self._init_task.done():
                await self._init_task
            if self._init_exception:
                raise self._init_exception
        return True

    def _start_background_refresh(self, interval_minutes: int):
        def loop():
            logger.info("ProxyPool background refresher started (interval=%sm)", interval_minutes)
            while not self._stop_evt.wait(interval_minutes * 60):
                try:
                    self._swift.update()
                    logger.debug("ProxyPool background refresh completed")
                except Exception as e:  # pragma: no cover
                    logger.warning("Background proxy refresh failed: %s", e)
        self._bg_thread = threading.Thread(target=loop, name="proxy-refresh", daemon=True)
        self._bg_thread.start()

    def close(self):
        self._stop_evt.set()
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=2)

    def get(self) -> str:
        """
        Return next proxy as 'host:port'. If pool empty, attempt a refresh once;
        fall back to a QuickProxy instance on failure.
        """
        # Fast path
        try:
            return self._swift.get().as_string()
        except ValueError:
            pass

        # If initial async update still running, wait (best-effort) without deadlocking.
        if self._init_task and not self._init_task.done():
            # Caller *should* have awaited ensure_ready(); we wait briefly.
            try:
                asyncio.get_running_loop()
                # In-event-loop: cannot block; just return fallback and leave update to finish.
            except RuntimeError:
                # No loop: we can block until task done
                self._init_task.wait()

        # Try one explicit refresh (async if possible)
        try:
            loop = asyncio.get_running_loop()
            # Schedule async_update but don't await fully (avoid forcing caller to be async)
            loop.create_task(self._swift.async_update())
        except RuntimeError:
            # No running loop: safe to call synchronous update()
            try:
                if hasattr(self._swift, "update"):
                    self._swift.update()
            except Exception as e:  # pragma: no cover
                logger.debug("Synchronous proxy update failed: %s", e)

        # Second attempt
        try:
            return self._swift.get().as_string()
        except ValueError:
            if QuickProxy:
                try:
                    return QuickProxy().as_string()
                except Exception as e:  # pragma: no cover
                    raise RuntimeError("No proxies available after fallback") from e
            raise RuntimeError("No proxies available")

    def get_requests_dict(self):
        try:
            return self._swift.get().as_requests_dict()
        except ValueError:
            self._swift.update()
            try:
                return self._swift.get().as_requests_dict()
            except ValueError:
                if QuickProxy:
                    qp = QuickProxy().as_string()
                    return {"http": f"http://{qp}", "https": f"http://{qp}"}
                raise

    def next_proxy(self):  # backward compat
        return self.get()
