import io
import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from app.database import SessionLocal
from app.models import GeneratedPdf
from tests.conftest import TEST_STORAGE
from tests.test_programs import WORKOUT, create


@pytest.fixture()
def student(auth_client):
    return auth_client.post("/api/students", json={"first_name": "علی", "last_name": "رضایی"}).json()


@pytest.fixture()
def approved(auth_client, student):
    p = create(auth_client, student)
    return auth_client.post(f"/api/programs/{p['id']}/approve").json()


def text_of(pdf_bytes: bytes) -> str:
    """Extract text with poppler (handles Persian shaping better than pypdf)."""
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", "-", "-"], input=pdf_bytes, capture_output=True, check=True)
    # Drop bidi control marks added by the extractor; note pdftotext extracts the
    # lam-alef ligature as «ال», so test needles avoid «لا».
    text = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", out.stdout.decode())
    # pdftotext spacing around numbers is unreliable: compare without whitespace
    return re.sub(r"\s+", "", text)


def test_no_pdf_for_draft(auth_client, student):
    p = create(auth_client, student)
    assert auth_client.post(f"/api/programs/{p['id']}/generate-pdf").status_code == 409


def test_generate_pdf_a4_with_persian_content(auth_client, approved):
    auth_client.put("/api/settings/pdf-template", json={
        "club_name": "باشگاه بشرنیا", "coach_name": "مربی تست", "phone": "09120000000",
        "primary_color": "#1F4E79", "footer_text": "سلامت شما هدف ماست"})
    r = auth_client.post(f"/api/programs/{approved['id']}/generate-pdf")
    assert r.status_code == 201, r.text
    pdf = r.json()
    assert pdf["version"] == 1 and pdf["is_outdated"] is False

    d = auth_client.get(f"/api/pdfs/{pdf['id']}/download")
    assert d.status_code == 200 and d.headers["content-type"] == "application/pdf"
    assert d.headers["content-disposition"].startswith("attachment;")
    assert "no-store" in d.headers["cache-control"]
    data = d.content
    assert data.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(data))
    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (595, 842)  # A4 in points
    assert b"Vazirmatn" in data  # local font embedded, no CDN

    text = text_of(data)
    for needle in ["علی رضایی", "سینه دمبل", "پرس سینه دستگاه", "باشگاه بشرنیا", "سینه و پشت بازو", "۴۰ کیلوگرم",
                   "۱ دقیقه", "جلسه اول", "جلسه دوم", "۱۴۰۵/۰۸/۰۱"]:
        assert needle.replace(" ", "") in text, needle
    # Footer page number uses the Farsi-digit font
    assert "صفحه" in text


def test_inline_download_for_print(auth_client, approved):
    pdf = auth_client.post(f"/api/programs/{approved['id']}/generate-pdf").json()
    d = auth_client.get(f"/api/pdfs/{pdf['id']}/download?inline=1")
    assert d.headers["content-disposition"].startswith("inline;")


def test_versions_are_kept_and_outdated_flag(auth_client, approved):
    v1 = auth_client.post(f"/api/programs/{approved['id']}/generate-pdf").json()
    body = {k: v for k, v in WORKOUT.items() if k != "program_type"}
    body["title"] = "نسخه دوم"
    auth_client.put(f"/api/programs/{approved['id']}", json=body)
    pdfs = auth_client.get(f"/api/programs/{approved['id']}/pdfs").json()
    assert pdfs[0]["is_outdated"] is True
    assert auth_client.get(f"/api/programs/{approved['id']}").json()["latest_pdf"]["is_outdated"] is True

    v2 = auth_client.post(f"/api/programs/{approved['id']}/generate-pdf").json()
    assert v2["version"] == 2 and v2["is_outdated"] is False
    pdfs = auth_client.get(f"/api/programs/{approved['id']}/pdfs").json()
    assert [p["version"] for p in pdfs] == [2, 1]
    with SessionLocal() as s:
        paths = [Path(TEST_STORAGE) / p.file_path for p in s.query(GeneratedPdf).all()]
    assert all(p.is_file() for p in paths) and len(set(paths)) == 2
    assert all(f"pdf/{approved['student']['id']}/{approved['id']}/" in str(p) for p in paths)
    # old version still downloadable
    assert auth_client.get(f"/api/pdfs/{v1['id']}/download").status_code == 200


def test_pdf_for_nutrition_and_supplements(auth_client, student):
    n = create(auth_client, student, {"title": "رژیم", "program_type": "nutrition", "notes": "آب کافی",
                                      "meals": [{"title": "صبحانه", "time_text": "08:00",
                                                 "content": "۲ عدد تخم‌مرغ\nنان سنگک"}]})
    auth_client.post(f"/api/programs/{n['id']}/approve")
    pdf = auth_client.post(f"/api/programs/{n['id']}/generate-pdf").json()
    text = text_of(auth_client.get(f"/api/pdfs/{pdf['id']}/download").content)
    assert "صبحانه" in text and "نانسنگک" in text and "۰۸:۰۰" in text

    v = create(auth_client, student, {"title": "ویتامین‌ها", "program_type": "vitamin",
                                      "supplements": [{"name": "ویتامین D", "amount_text": "1000 واحد"}]})
    auth_client.post(f"/api/programs/{v['id']}/approve")
    pdf = auth_client.post(f"/api/programs/{v['id']}/generate-pdf").json()
    text = text_of(auth_client.get(f"/api/pdfs/{pdf['id']}/download").content)
    assert "ویتامینD" in text and "۱۰۰۰" in text


def test_html_is_escaped_in_pdf(auth_client, student):
    from app.database import SessionLocal
    from app.pdf.render import render_html
    from app.services.programs import load_program
    from app.services.settings import PdfTemplate

    body = {**WORKOUT, "title": "<script>alert(1)</script>",
            "sessions": [{"title": "<b>x</b>", "exercises": [{"name": "<img src=x onerror=alert(1)>"}]}]}
    p = create(auth_client, student, body)
    with SessionLocal() as db:
        html = render_html(load_program(db, p["id"]), "علی", PdfTemplate(footer_text="<i>f</i>"), None, issued=None)
    assert "<script>alert" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
    # and it still renders to a PDF
    auth_client.post(f"/api/programs/{p['id']}/approve")
    assert auth_client.post(f"/api/programs/{p['id']}/generate-pdf").status_code == 201


def test_long_program_has_page_numbers(auth_client, student):
    sessions = [
        {"title": f"جلسه {i}", "exercises": [{"name": f"حرکت شماره {j}", "sets": 3, "reps": "12",
                                              "notes": "توضیح نسبتاً طولانی برای بررسی شکست صفحه"} for j in range(15)]}
        for i in range(4)
    ]
    p = create(auth_client, student, {"title": "بلند", "program_type": "workout", "sessions": sessions})
    auth_client.post(f"/api/programs/{p['id']}/approve")
    pdf = auth_client.post(f"/api/programs/{p['id']}/generate-pdf").json()
    data = auth_client.get(f"/api/pdfs/{pdf['id']}/download").content
    pages = len(PdfReader(io.BytesIO(data)).pages)
    assert pages >= 2
    text = text_of(data)
    # Footer on every page (digits are drawn Persian by the FD font; extracted as ASCII)
    assert text.count("صفحه") >= pages


def test_logo_upload_and_in_pdf(auth_client, approved):
    buf = io.BytesIO()
    Image.new("RGB", (400, 200), (31, 78, 121)).save(buf, format="PNG")
    r = auth_client.put("/api/settings/logo", files={"file": ("logo.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["has_logo"] is True
    assert auth_client.get("/api/settings/logo").status_code == 200
    pdf = auth_client.post(f"/api/programs/{approved['id']}/generate-pdf").json()
    data = auth_client.get(f"/api/pdfs/{pdf['id']}/download").content
    assert b"/Subtype /Image" in data or b"/Image" in data


def test_template_color_validation(auth_client):
    r = auth_client.put("/api/settings/pdf-template", json={"primary_color": "red; background:url(x)"})
    assert r.status_code == 422
    r = auth_client.get("/api/settings/pdf-template")
    assert r.json()["club_name"] == "Basharnia" and r.json()["has_logo"] is False


def test_concurrent_generation_gets_distinct_versions(auth_client, approved):
    from concurrent.futures import ThreadPoolExecutor

    url = f"/api/programs/{approved['id']}/generate-pdf"
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: auth_client.post(url), range(3)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    assert sorted(r.json()["version"] for r in results) == [1, 2, 3]
