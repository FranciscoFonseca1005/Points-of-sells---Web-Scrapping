import requests

from src.http_client import HttpClient, looks_like_access_interstitial


def test_detects_utf8_when_html_omits_charset(monkeypatch) -> None:
    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = "text/html"
    response._content = "<p>Bogotá</p>".encode("utf-8")

    client = HttpClient(allow_browser=False)
    monkeypatch.setattr(client, "_get", lambda *_: response)

    try:
        html = client.get_html("https://example.com")
    finally:
        client.close()

    assert "Bogotá" in html


def test_recognizes_security_interstitial() -> None:
    html = "<title>Attention Required! | Cloudflare</title>"

    assert looks_like_access_interstitial(html)
