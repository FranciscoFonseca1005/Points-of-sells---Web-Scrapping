"""Cliente compartido con caché, reintentos y navegador opcional."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.exceptions import SourceResponseError
from src.normalization import normalize_identifier


USER_AGENT = "store-extractor/2.0 (+public store locator research)"
BLOCK_MARKERS = (
    "please wait while your request is being verified",
    "sorry, you have been blocked",
    "verify you are human",
    "checking your browser",
    "attention required! | cloudflare",
    "cf-chl-",
)


def looks_like_access_interstitial(html: str) -> bool:
    """Detecta páginas servidas en lugar del contenido solicitado."""

    normalized = normalize_identifier(html[:50_000])
    return any(marker in normalized for marker in BLOCK_MARKERS)


class BrowserRenderer:
    """Renderizador Playwright iniciado únicamente cuando hace falta."""

    def __init__(self, *, headless: bool, timeout_ms: int = 60_000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    def _start(self) -> None:
        if self._context is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise SourceResponseError(
                "La página requiere navegador, pero Playwright no está "
                "instalado. Ejecute: py -m pip install -r requirements.txt"
            ) from error

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless
            )
            self._context = self._browser.new_context(user_agent=USER_AGENT)
        except Exception as error:
            self.close()
            raise SourceResponseError(
                "No fue posible iniciar Chromium. Ejecute una vez: "
                "py -m playwright install chromium. "
                f"Detalle: {type(error).__name__}: {error}"
            ) from error

    def get_html(self, url: str) -> str:
        """Renderiza una página pública y devuelve su HTML final."""

        self._start()
        page = self._context.new_page()

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )

            html = page.content()

            # Algunas verificaciones no interactivas se resuelven solas.
            for _ in range(30):
                if not looks_like_access_interstitial(html):
                    break
                page.wait_for_timeout(1_000)
                html = page.content()

            if looks_like_access_interstitial(html):
                raise SourceResponseError(
                    "La fuente mostró una verificación o bloqueo de seguridad. "
                    "El programa no intenta evadirla."
                )

            return html
        except SourceResponseError:
            raise
        except Exception as error:
            raise SourceResponseError(
                "No fue posible renderizar la fuente pública: "
                f"{url}. Detalle: {type(error).__name__}: {error}"
            ) from error
        finally:
            page.close()

    def close(self) -> None:
        """Libera navegador y proceso de Playwright si fueron iniciados."""

        for resource in (self._context, self._browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass

        self._context = None
        self._browser = None
        self._playwright = None


class HttpClient:
    """Consulta fuentes públicas y reutiliza respuestas por URL."""

    def __init__(
        self,
        timeout: float = 30.0,
        *,
        allow_browser: bool = True,
        headless: bool = True,
    ) -> None:
        self.timeout = timeout
        self.allow_browser = allow_browser
        self.headless = headless
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._json_cache: dict[str, Any] = {}
        self._html_cache: dict[str, str] = {}
        self._text_cache: dict[tuple[str, str], str] = {}
        self._renderer: BrowserRenderer | None = None

        retries = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get(self, url: str, accept: str) -> requests.Response:
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"Accept": accept},
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            raise SourceResponseError(
                "No fue posible consultar la fuente pública: "
                f"{url}. Detalle: {type(error).__name__}: {error}"
            ) from error

    def get_json(self, url: str) -> Any:
        """Realiza un GET JSON y conserva la respuesta en memoria."""

        if url in self._json_cache:
            return self._json_cache[url]

        response = self._get(
            url,
            "application/json, text/plain;q=0.9, */*;q=0.8",
        )

        try:
            payload = response.json()
        except requests.JSONDecodeError as error:
            raise SourceResponseError(
                f"La fuente no devolvió JSON válido: {url}"
            ) from error

        self._json_cache[url] = payload
        return payload

    def get_text(self, url: str, accept: str = "text/plain, */*") -> str:
        """Obtiene una fuente textual sin asumir que sea HTML o JSON."""

        cache_key = (url, accept)
        if cache_key in self._text_cache:
            return self._text_cache[cache_key]

        response = self._get(url, accept)

        if "charset=" not in response.headers.get(
            "Content-Type",
            "",
        ).casefold():
            response.encoding = response.apparent_encoding

        text = response.text
        self._text_cache[cache_key] = text
        return text

    def _render_html(self, url: str) -> str:
        if not self.allow_browser:
            raise SourceResponseError(
                "La fuente requiere un navegador y la ejecución usó "
                "--no-browser."
            )

        if self._renderer is None:
            self._renderer = BrowserRenderer(headless=self.headless)

        return self._renderer.get_html(url)

    def get_html(self, url: str) -> str:
        """Obtiene HTML y usa Chromium solo ante bloqueo o fallo estático."""

        if url in self._html_cache:
            return self._html_cache[url]

        try:
            response = self._get(
                url,
                "text/html, application/xhtml+xml;q=0.9, */*;q=0.8",
            )

            if "charset=" not in response.headers.get(
                "Content-Type",
                "",
            ).casefold():
                response.encoding = response.apparent_encoding

            html = response.text
        except SourceResponseError as static_error:
            if not self.allow_browser:
                raise

            try:
                html = self._render_html(url)
            except SourceResponseError as browser_error:
                raise SourceResponseError(
                    f"{static_error} Respaldo de navegador: {browser_error}"
                ) from browser_error
        else:
            if looks_like_access_interstitial(html):
                html = self._render_html(url)

        self._html_cache[url] = html
        return html

    def close(self) -> None:
        """Cierra HTTP y el navegador opcional."""

        self.session.close()

        if self._renderer is not None:
            self._renderer.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
