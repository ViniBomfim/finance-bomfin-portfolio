from io import BytesIO

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token

# Minimal valid 1x1 PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_avatar_upload_get_delete(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)

    me = client.get("/api/v1/users/me", headers=h)
    assert me.status_code == 200
    assert me.json()["has_avatar"] is False

    missing = client.get("/api/v1/users/me/avatar", headers=h)
    assert missing.status_code == 404

    upload = client.post(
        "/api/v1/users/me/avatar",
        headers=h,
        files={"file": ("avatar.png", BytesIO(_PNG_1X1), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["has_avatar"] is True

    got = client.get("/api/v1/users/me/avatar", headers=h)
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("image/png")
    assert got.content == _PNG_1X1

    me2 = client.get("/api/v1/users/me", headers=h)
    assert me2.json()["has_avatar"] is True

    deleted = client.delete("/api/v1/users/me/avatar", headers=h)
    assert deleted.status_code == 200
    assert deleted.json()["has_avatar"] is False

    missing_again = client.get("/api/v1/users/me/avatar", headers=h)
    assert missing_again.status_code == 404


def test_avatar_rejects_non_image(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    bad = client.post(
        "/api/v1/users/me/avatar",
        headers=h,
        files={"file": ("x.txt", BytesIO(b"not-an-image"), "text/plain")},
    )
    assert bad.status_code == 400
