import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.devto_publish import Devto, marker_for, read_post


class PublisherTests(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", encoding="utf-8", delete=False)
        tmp.write(text)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_valid_draft(self):
        post = self.write("---\ntitle: Test post\ntags: [python]\npublished: false\n---\nHello DEV\n")
        meta, body = read_post(post)
        self.assertFalse(meta["published"])
        self.assertEqual(body, "Hello DEV\n")

    def test_published_requires_body(self):
        post = self.write("---\ntitle: Test post\ntags: [python]\npublished: true\n---\n")
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            read_post(post)

    def test_rejects_fifth_tag(self):
        post = self.write("---\ntitle: Test\ntags: [one, two, three, four, five]\n---\nBody")
        with self.assertRaisesRegex(ValueError, "1–4"):
            read_post(post)

    def test_rejects_non_boolean_publish_flag(self):
        post = self.write("---\ntitle: Test\ntags: [python]\npublished: 'true'\n---\nBody")
        with self.assertRaisesRegex(ValueError, "true or false"):
            read_post(post)

    def test_source_marker_is_stable(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
            self.assertEqual(
                marker_for(Path("posts/first.md")),
                "<!-- devto-source: owner/repo/posts/first.md -->",
            )

    def test_detects_owned_article_without_duplicate(self):
        with patch.dict(os.environ, {"DEVTO_API_KEY": "fake"}):
            api = Devto()
        with patch.object(api, "owned_articles", return_value=[
            {"id": 22, "title": "Renamed article", "published_at": "2026-01-01"},
            {"id": 24, "title": "Other article", "published_at": "2026-01-01"},
        ]), patch.object(api, "detail", side_effect=[
            {"id": 22, "body_markdown": "text\n<!-- devto-source: owner/repo/posts/first.md -->"},
            {"id": 24, "body_markdown": "other content"},
        ]):
            self.assertEqual(
                api.find_managed("<!-- devto-source: owner/repo/posts/first.md -->", "First title")["id"],
                22,
            )


if __name__ == "__main__":
    unittest.main()
