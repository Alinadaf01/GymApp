import io
import os
from pathlib import Path

import pytest
from PIL import Image

from app.config import get_settings
from app.database import SessionLocal
from app.models import Student
from tests.conftest import TEST_STORAGE


def jpeg_with_gps() -> bytes:
    img = Image.new("RGB", (2000, 1500), (200, 50, 50))
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    gps = {1: "N", 2: (35.0, 41.0, 0.0), 3: "E", 4: (51.0, 25.0, 0.0)}
    exif[0x8825] = gps
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 255, 128)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def student(auth_client):
    return auth_client.post("/api/students", json={"first_name": "علی", "last_name": "رضایی"}).json()


def upload(client, sid, data, name="p.jpg", ctype="image/jpeg", consent=True):
    return client.put(
        f"/api/students/{sid}/profile-photo",
        files={"file": (name, data, ctype)},
        data={"consent": "true" if consent else "false"},
    )


def stored_path(sid) -> Path:
    with SessionLocal() as db:
        rel = db.get(Student, sid).profile_photo_path
    return Path(TEST_STORAGE) / rel if rel else None


def test_upload_requires_consent(auth_client, student):
    r = upload(auth_client, student["id"], jpeg_with_gps(), consent=False)
    assert r.status_code == 422


def test_upload_strips_exif_resizes_and_serves_privately(auth_client, student):
    r = upload(auth_client, student["id"], jpeg_with_gps())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["photo_consent_at"] is not None
    url = body["profile_photo_url"]
    assert url.startswith(f"/api/students/{student['id']}/profile-photo?v=")

    path = stored_path(student["id"])
    assert path.is_file()
    # random, unguessable name; not the original file name; outside any public dir
    assert path.name != "p.jpg" and len(path.stem) >= 40
    assert oct(path.stat().st_mode & 0o777) == "0o640"
    with Image.open(path) as img:
        assert max(img.size) == 1024
        assert not img.getexif()  # no EXIF/GPS
    assert b"SecretCameraMaker" not in path.read_bytes()

    got = auth_client.get(url)
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
    assert "private" in got.headers["cache-control"]
    assert got.headers["x-content-type-options"] == "nosniff"


def test_photo_not_served_without_auth(auth_client, student):
    upload(auth_client, student["id"], jpeg_with_gps())
    auth_client.cookies.clear()
    assert auth_client.get(f"/api/students/{student['id']}/profile-photo").status_code == 401


def test_png_is_converted_to_jpeg(auth_client, student):
    r = upload(auth_client, student["id"], png_bytes(), name="a.png", ctype="image/png")
    assert r.status_code == 200
    with Image.open(stored_path(student["id"])) as img:
        assert img.format == "JPEG"


@pytest.mark.parametrize(
    "data,name,ctype",
    [
        (b"<?php echo 1; ?>", "x.jpg", "image/jpeg"),       # not an image
        (b"GIF89a....", "x.gif", "image/gif"),              # disallowed type
        (None, "x.exe", "image/jpeg"),                      # bad extension
        (None, "x.jpg", "application/octet-stream"),        # bad MIME
        (None, "noext", "image/jpeg"),
    ],
)
def test_rejects_invalid_files(auth_client, student, data, name, ctype):
    r = upload(auth_client, student["id"], data or jpeg_with_gps(), name=name, ctype=ctype)
    assert r.status_code == 422
    assert stored_path(student["id"]) is None


def test_rejects_too_large(auth_client, student):
    big = os.urandom(get_settings().max_upload_mb * 1024 * 1024 + 10)
    r = upload(auth_client, student["id"], big)
    assert r.status_code == 413


def test_replace_deletes_old_file_and_delete_removes(auth_client, student):
    upload(auth_client, student["id"], jpeg_with_gps())
    first = stored_path(student["id"])
    # consent already recorded -> not required again
    upload(auth_client, student["id"], png_bytes(), name="b.png", ctype="image/png", consent=False)
    second = stored_path(student["id"])
    assert first != second and not first.exists() and second.exists()

    assert auth_client.delete(f"/api/students/{student['id']}/profile-photo").status_code == 204
    assert not second.exists()
    assert auth_client.get(f"/api/students/{student['id']}").json()["profile_photo_url"] is None


def test_path_traversal_refused():
    from app.storage import files

    with pytest.raises(files.StorageError):
        files.resolve("../../etc/passwd")
