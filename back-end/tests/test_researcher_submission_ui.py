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


def test_rendered_rows_resynchronise_edited_styling_after_draft_restore():
    app_source = APP_JS.read_text(encoding="utf-8")

    assert "function syncRenderedRoadEditedState()" in app_source
    render_body = app_source.split("function renderRoadModule1Inputs()", 1)[1].split(
        "function syncRenderedRoadEditedState()", 1,
    )[0]
    assert "syncRenderedRoadEditedState();" in render_body
    assert "roadInputValueDiffersFromDefault" in app_source.split(
        "function syncRenderedRoadEditedState()", 1,
    )[1].split("function handleRoadModule1InputChange", 1)[0]


def test_esto_vintage_selector_is_simple_and_warns_before_switching_edits():
    app_source = APP_JS.read_text(encoding="utf-8")
    index_source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="road-esto-vintage-select"' in index_source
    assert "Changing it loads a separate input package" in index_source
    assert "Switch ESTO vintage?" in app_source
    assert "They will not be copied to the new vintage" in app_source
    assert "saveRoadModule1DraftNow()" in app_source
    assert "baseYear !== estoVintage - 2" in app_source


def test_run_payload_records_selected_esto_vintage():
    app_source = APP_JS.read_text(encoding="utf-8")
    assert "esto_vintage: State.roadModule1.estoVintage" in app_source
