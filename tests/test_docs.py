"""Checks that README.md, the project's front page, has no broken links and dates its numbers.

GitHub shows a broken link or image without any error, so a renamed file would go unnoticed.
The README's numbers are typed by hand while FINDINGS.md is regenerated every week, so the
README must say which data its numbers came from and point to FINDINGS.md for the latest.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")

# Markdown links and images: [text](target) and ![alt](target).
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")


def relative_targets(markdown: str) -> list[str]:
    """Link targets that point inside the repo, with any #anchor removed."""
    targets = []
    for target in LINK.findall(markdown):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        targets.append(target.split("#", 1)[0])
    return targets


def test_relative_targets_skips_web_links_and_anchors() -> None:
    markdown = "[a](https://x.org) ![b](docs/img/x.png) [c](#top) [d](LICENSE#mit)"
    assert relative_targets(markdown) == ["docs/img/x.png", "LICENSE"]


def test_every_readme_link_and_image_exists() -> None:
    targets = relative_targets(README)
    assert targets, "README should link to at least one file in the repo"
    missing = [t for t in targets if not (ROOT / t).exists()]
    assert missing == []


def test_readme_numbers_are_dated_and_point_to_findings() -> None:
    """Hand-typed numbers go stale after a refresh, so the reader must know their date."""
    assert re.search(r"data as of \d{4}-\d{2}-\d{2}", README)
    assert "(analysis/FINDINGS.md)" in README


def test_readme_has_live_links() -> None:
    """The live links are the first thing a visitor clicks, so neither may be a placeholder."""
    for label in ("Live dashboard", "Live API"):
        line = next(line for line in README.splitlines() if f"**{label}:**" in line)
        assert "(https://" in line, f"{label} has no web link: {line}"
