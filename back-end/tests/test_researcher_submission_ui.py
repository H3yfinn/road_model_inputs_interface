from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_JS = REPO_ROOT / "front-end" / "app.js"
INDEX_HTML = REPO_ROOT / "front-end" / "index.html"


def test_every_researcher_comment_field_uses_source_reason_guidance():
    app_source = APP_JS.read_text(encoding="utf-8")
    comment_inputs = re.findall(
        r'<input[^>]+class="road-comment-input"[^>]*>',
        app_source,
    )

    assert comment_inputs
    assert all("${roadSourceReasonInputAttributes()}" in field for field in comment_inputs)
    assert 'placeholder="Comment' not in app_source
    assert 'aria-label="Source and reason for change"' in app_source


def test_source_reason_guidance_is_visible_and_repeated_before_run():
    app_source = APP_JS.read_text(encoding="utf-8")
    index_source = INDEX_HTML.read_text(encoding="utf-8")

    assert "dataset or document, source year, link or reference" in app_source
    assert "dataset or document, source year, link or reference" in index_source
    assert "no source / reason note" in app_source
    assert "The run can continue" in app_source
