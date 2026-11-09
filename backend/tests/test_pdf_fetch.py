import asyncio

import httpx
import pytest

from app.services import pdf_fetch
from app.services.pdf_fetch import PdfFetchError, fetch_pdf

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture()
def net(monkeypatch):
    """Transport tiruan + DNS tiruan: 'repo.kampus.ac.id' publik, 'dalam.kampus.ac.id' menunjuk alamat privat."""
    state = {"handler": None, "requests": []}

    async def fake_resolve(host):
        return {"repo.kampus.ac.id": ["93.184.216.34"], "dalam.kampus.ac.id": ["10.0.0.5"]}.get(host, ["93.184.216.34"])

    monkeypatch.setattr(pdf_fetch, "_resolve_all", fake_resolve)

    real = httpx.AsyncClient

    def factory(*a, **kw):
        def route(req):
            state["requests"].append(str(req.url))
            return state["handler"](req)

        kw["transport"] = httpx.MockTransport(route)
        return real(*a, **kw)

    monkeypatch.setattr(pdf_fetch.httpx, "AsyncClient", factory)
    return state


def run(url):
    return asyncio.run(fetch_pdf(url))


def test_fetches_pdf(net):
    net["handler"] = lambda req: httpx.Response(200, content=PDF)
    assert run("https://repo.kampus.ac.id/a.pdf") == PDF


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/a.pdf",
        "http://10.1.2.3/a.pdf",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/a.pdf",
        "http://dalam.kampus.ac.id/a.pdf",
        "file:///etc/passwd",
        "ftp://repo.kampus.ac.id/a.pdf",
    ],
)
def test_rejects_internal_and_non_http(net, url):
    net["handler"] = lambda req: httpx.Response(200, content=PDF)
    with pytest.raises(PdfFetchError):
        run(url)
    assert net["requests"] == [], "tidak boleh ada permintaan keluar"


def test_localhost_by_name_is_rejected(monkeypatch):
    async def fake_resolve(host):
        return ["127.0.0.1"]

    monkeypatch.setattr(pdf_fetch, "_resolve_all", fake_resolve)
    with pytest.raises(PdfFetchError) as e:
        run("http://localhost/a.pdf")
    assert e.value.status == 400


def test_redirect_to_private_address_is_blocked(net):
    def handler(req):
        if req.url.host == "repo.kampus.ac.id":
            return httpx.Response(302, headers={"location": "http://dalam.kampus.ac.id/rahasia.pdf"})
        return httpx.Response(200, content=PDF)

    net["handler"] = handler
    with pytest.raises(PdfFetchError, match="non-publik"):
        run("https://repo.kampus.ac.id/a.pdf")
    assert net["requests"] == ["https://repo.kampus.ac.id/a.pdf"], "hop ke alamat privat tidak boleh dikirim"


def test_follows_public_redirect_with_relative_location(net):
    def handler(req):
        if req.url.path == "/a.pdf":
            return httpx.Response(301, headers={"location": "/files/b.pdf"})
        return httpx.Response(200, content=PDF)

    net["handler"] = handler
    assert run("https://repo.kampus.ac.id/a.pdf") == PDF
    assert net["requests"][-1] == "https://repo.kampus.ac.id/files/b.pdf"


def test_redirect_loop_is_cut(net):
    net["handler"] = lambda req: httpx.Response(302, headers={"location": "https://repo.kampus.ac.id/lagi"})
    with pytest.raises(PdfFetchError, match="pengalihan"):
        run("https://repo.kampus.ac.id/a.pdf")


def test_html_landing_page_is_not_pdf(net):
    net["handler"] = lambda req: httpx.Response(200, content=b"<html>halaman penerbit</html>")
    with pytest.raises(PdfFetchError) as e:
        run("https://repo.kampus.ac.id/a.pdf")
    assert e.value.status == 415


def test_size_limit(net, monkeypatch):
    monkeypatch.setattr(pdf_fetch, "MAX_BYTES", 100)
    net["handler"] = lambda req: httpx.Response(200, content=PDF + b"x" * 500)
    with pytest.raises(PdfFetchError) as e:
        run("https://repo.kampus.ac.id/a.pdf")
    assert e.value.status == 413


def test_upstream_error_status(net):
    net["handler"] = lambda req: httpx.Response(403)
    with pytest.raises(PdfFetchError, match="403"):
        run("https://repo.kampus.ac.id/a.pdf")


def test_endpoint_requires_pdf_url_and_ownership(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi"}).json()["thesis_id"]
    cits = client.post(
        f"/theses/{tid}/citations",
        headers=headers,
        json=[
            {"title": "Tanpa PDF", "publication_year": 2020},
            {"title": "Dengan PDF", "publication_year": 2021, "pdf_url": "https://repo.kampus.ac.id/a.pdf"},
        ],
    ).json()
    no_pdf, with_pdf = cits[0]["citation_id"], cits[1]["citation_id"]

    assert client.get(f"/theses/{tid}/citations/{no_pdf}/pdf", headers=headers).status_code == 404
    assert client.get(f"/theses/{tid}/citations/id-asing/pdf", headers=headers).status_code == 404
    assert client.get(f"/theses/{tid}/citations/{with_pdf}/pdf").status_code == 401

    async def fake_fetch(url):
        assert url == "https://repo.kampus.ac.id/a.pdf"
        return PDF

    from app.routers import pdf as pdf_router

    monkeypatch.setattr(pdf_router, "fetch_pdf", fake_fetch)
    ok = client.get(f"/theses/{tid}/citations/{with_pdf}/pdf", headers=headers)
    assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf" and ok.content == PDF

    async def bad_fetch(url):
        raise PdfFetchError("bukan PDF", 415)

    monkeypatch.setattr(pdf_router, "fetch_pdf", bad_fetch)
    assert client.get(f"/theses/{tid}/citations/{with_pdf}/pdf", headers=headers).status_code == 415
