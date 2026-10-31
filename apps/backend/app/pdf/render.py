"""Render a program to an A4 PDF with Chromium (Playwright).

- Fonts and the logo are embedded as data URIs; every network request is blocked,
  so the page cannot reach external resources (no CDN, no SSRF).
- Template autoescaping is on; coach-entered text is never interpreted as HTML.
"""
import base64
import threading
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import Program
from app.pdf import formatting as f
from app.services.settings import PdfTemplate

PDF_DIR = Path(__file__).parent
FONTS = PDF_DIR / "fonts"

TYPE_LABELS = {"workout": "تمرینی", "nutrition": "غذایی", "supplement": "مکمل", "vitamin": "ویتامین"}
ORDINALS = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم"]

# Chromium is memory hungry; never render more than two PDFs at once
_render_slots = threading.BoundedSemaphore(2)


class PdfRenderError(RuntimeError):
    pass


@cache
def _font_uri(name: str) -> str:
    data = (FONTS / name).read_bytes()
    return "data:font/woff2;base64," + base64.b64encode(data).decode()


@cache
def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(PDF_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        fa=f.fa, jalali=f.jalali, seconds=f.seconds, with_unit=f.with_unit, number=f.number,
        ordinal=lambda i: ORDINALS[i - 1] if i <= len(ORDINALS) else f.fa(i),
    )
    return env


def render_html(program: Program, student_name: str, template: PdfTemplate, logo_jpeg: bytes | None, issued) -> str:
    return _env().get_template("program.html").render(
        program=program,
        student_name=student_name,
        template=template,
        type_label=TYPE_LABELS[program.program_type.value],
        issued=f.jalali(issued),
        logo="data:image/jpeg;base64," + base64.b64encode(logo_jpeg).decode() if logo_jpeg else None,
        fonts={"regular": _font_uri("Vazirmatn-Regular.woff2"), "bold": _font_uri("Vazirmatn-Bold.woff2")},
    )


def _footer(template: PdfTemplate) -> str:
    # Farsi-digit font: Chromium fills pageNumber/totalPages with ASCII digits; this
    # variant of Vazirmatn draws them as Persian digits.
    left = _env().from_string("{{ t }}").render(t=template.footer_text or template.club_name or "")
    return f"""
<style>
  @font-face {{ font-family: "VazirFD"; src: url("{_font_uri('Vazirmatn-UI-FD-Regular.woff2')}") format("woff2"); }}
</style>
<div style="font-family: VazirFD, sans-serif; font-size: 8pt; color: #444; width: 100%; padding: 0 12mm;
            direction: rtl; display: flex; justify-content: space-between;">
  <span>{left}</span>
  <span>صفحه <span class="pageNumber"></span> از <span class="totalPages"></span></span>
</div>"""


def html_to_pdf(html: str, template: PdfTemplate, timeout_ms: int = 30_000) -> bytes:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    with _render_slots:
        try:
            with sync_playwright() as p:
                # Docker's default /dev/shm (64MB) is too small for Chromium
                browser = p.chromium.launch(args=["--disable-dev-shm-usage"])
                try:
                    page = browser.new_page()
                    page.set_default_timeout(timeout_ms)
                    # Block everything except inline data: URIs
                    page.route("**/*", lambda route: route.abort())
                    page.set_content(html, wait_until="load")
                    page.evaluate("document.fonts.ready.then(() => true)")
                    return page.pdf(
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        display_header_footer=True,
                        header_template="<span></span>",
                        footer_template=_footer(template),
                        margin={"top": "12mm", "bottom": "16mm", "left": "12mm", "right": "12mm"},
                    )
                finally:
                    browser.close()
        except PlaywrightError as e:
            raise PdfRenderError(str(e)) from e
