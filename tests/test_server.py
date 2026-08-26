import pytest
from fastapi.testclient import TestClient

from conftest import make_session
from segment_reviewer.server import create_app


@pytest.fixture
def client(segments_dir):
    session = make_session(segments_dir, labels=["rain"])
    return TestClient(create_app(session, session.config, token=None)), session


def test_bootstrap_carries_everything_the_gui_needs(client):
    api, session = client
    data = api.get("/api/bootstrap").json()
    assert data["folder"] == session.backend.display
    assert {lang["code"] for lang in data["languages"]} == {"en", "pt-BR"}
    assert data["state"]["segment"]["label"] == "BOAALB"
    assert data["state"]["counts"]["pending"] == 3
    assert data["state"]["labels"][0] == "rain"


def test_index_page_is_served(client):
    api, _ = client
    body = api.get("/").text
    assert "app.js" in body and "Segment Reviewer" in body


def test_translations_endpoint(client):
    api, _ = client
    data = api.get("/api/i18n/pt-BR").json()
    assert data["lang"] == "pt-BR"
    assert data["bundle"]["nav"]["true"].endswith("Verdadeiro")
    # An unknown tag falls back rather than failing.
    assert api.get("/api/i18n/xx").json()["lang"] == "en"


def test_navigation(client):
    api, _ = client
    assert api.post("/api/nav", json={"delta": 1}).json()["segment"]["index"] == 1
    assert api.post("/api/nav", json={"delta": -5}).json()["segment"]["index"] == 0
    assert api.post("/api/nav", json={"index": 2}).json()["segment"]["index"] == 2


def test_verdict_moves_the_file(client, segments_dir):
    api, _ = client
    data = api.post("/api/verdict", json={"verdict": "true"}).json()
    assert data["counts"]["pending"] == 2
    assert data["counts"]["true"] == 1
    assert (segments_dir / "true" / data["moved"].split("/")[-1]).exists()


def test_unknown_verdict_is_rejected(client):
    api, _ = client
    assert api.post("/api/verdict", json={"verdict": "maybe"}).status_code == 400


def test_audio_supports_range_requests(client):
    api, _ = client
    full = api.get("/api/audio?index=0")
    assert full.status_code == 200
    assert full.headers["accept-ranges"] == "bytes"
    part = api.get("/api/audio?index=0", headers={"Range": "bytes=0-9"})
    assert part.status_code == 206
    assert part.content == full.content[:10]
    assert part.headers["content-range"] == f"bytes 0-9/{len(full.content)}"


def test_audio_out_of_range_index(client):
    api, _ = client
    assert api.get("/api/audio?index=99").status_code == 404


def test_spectrogram_renders_a_png(client):
    api, _ = client
    res = api.get("/api/spectrogram?index=0&type=mel&fmin=0&fmax=0&db=-80")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content.startswith(b"\x89PNG")


def test_spectrogram_rejects_a_bad_type(client):
    api, _ = client
    assert api.get("/api/spectrogram?index=0&type=wavelet").status_code == 422


def test_token_guards_the_api(segments_dir):
    session = make_session(segments_dir)
    api = TestClient(create_app(session, session.config, token="s3cret"))
    assert api.get("/api/state").status_code == 401
    assert api.get("/health").status_code == 200
    assert api.get("/api/state", headers={"x-segrev-token": "s3cret"}).status_code == 200
    # The token in the query string is exchanged for a cookie, then dropped.
    landing = api.get("/?token=s3cret", follow_redirects=False)
    assert landing.status_code == 303
    assert api.get("/api/state").status_code == 200
