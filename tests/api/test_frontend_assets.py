"""Smoke tests for the static local UI asset boundaries."""

from pathlib import Path

STATIC_DIR = Path("app/web/static")


def test_static_html_references_expected_assets() -> None:
    html = (STATIC_DIR / "index.html").read_text()

    assert '<link rel="icon" href="data:," />' in html
    assert '<link rel="stylesheet" href="/ui/assets/styles.css" />' in html
    assert '<script type="module" src="/ui/assets/main.js"></script>' in html
    assert 'id="rail-toggle"' in html
    assert 'id="primary-nav"' in html


def test_api_client_centralizes_backend_endpoint_paths() -> None:
    api_client = (STATIC_DIR / "api-client.js").read_text()

    assert 'requestJson("/imports/csv/batch"' in api_client
    assert 'requestJson("/imports")' in api_client
    assert "`/imports/${encodeURIComponent(fileId)}`" in api_client
    assert "`/imports/${encodeURIComponent(fileId)}/report`" in api_client
    assert "`/imports/${encodeURIComponent(fileId)}/rows`" in api_client
    assert "`/imports/${encodeURIComponent(fileId)}/reprocess`" in api_client
    assert "`/transactions?${params.toString()}`" in api_client
    assert "`/transactions/summary?${params.toString()}`" in api_client


def test_components_cover_empty_warning_failed_and_long_row_rendering() -> None:
    components = (STATIC_DIR / "components.js").read_text()

    assert "No imports match the current filters." in components
    assert "Selected import is hidden by the current filters." in components
    assert "Review warnings" in components
    assert "fail-card" in components
    assert "repairStatusLabel" in components
    assert "No repair needed" in components
    assert "transactions-next" in components
    assert "rawRowPreview" in components
    assert "details><summary" in components
    assert "Needs action" in components
    assert "Transaction detail" in components
    assert "Open source import" in components
    assert "sourceImportQuery" in components
