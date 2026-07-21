import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dr_gen import generate_metadata  # noqa: E402
from generate_pages import gen_html, parse_content  # noqa: E402


class ReportBrowserTests(unittest.TestCase):
    def test_parse_content_uses_native_language_metadata_config(self):
        metadata = generate_metadata(
            word_count=1234,
            reading_time=6,
            data_until="2026-07",
            generate_time="2026-07-21 12:00:00",
            depth_mode="deep",
            source_count=7,
            top_sources=["Example"],
            skill_version="test",
            lang="ar",
        )["full_block"]
        content = f"# عنوان التقرير\n\n{metadata}\n"
        report = parse_content(content, "reports/ar/report-20260721-120000.md")
        self.assertEqual(report["lang"], "ar")
        self.assertEqual(report["mode"], "deep")
        self.assertEqual(report["word_count"], 1234)
        self.assertEqual(report["sources"], 7)

    def test_local_browser_escapes_metadata_and_lazy_loads_sanitized_body(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            stale_dir = out / "data"
            stale_dir.mkdir()
            (stale_dir / "stale.js").write_text("stale", encoding="utf-8")
            secret = "SECRET-BODY </script><script>alert(1)</script>"
            reports = [{
                "title": 'Bad </script><img src=x onerror="alert(2)">',
                "path": 'reports/en/bad"><script>.md',
                "lang": "en",
                "lang_name": 'English"><svg onload=alert(3)>',
                "mode": "deep",
                "word_count": 100,
                "date": "2026-07-21",
                "sources": 1,
                "_content": secret + "\n[bad](javascript:alert(4))",
            }]

            gen_html(reports, local=True, out_dir=str(out))

            index = (out / "index.html").read_text(encoding="utf-8")
            self.assertNotIn(secret, index)
            self.assertNotIn("<img src=x", index)
            self.assertIn("&lt;/script&gt;&lt;img", index)
            self.assertIn("reports/en/bad%22%3E%3Cscript%3E.md", index)
            self.assertIn("DOMPurify.sanitize", index)
            self.assertIn("dompurify.min.js", index)
            self.assertIn("FORBID_TAGS", index)
            self.assertIn('data-word="100"', index)
            self.assertIn("Number(a.dataset.word)", index)
            self.assertNotIn("var RD=", index)

            payloads = list((out / "data").glob("*.js"))
            self.assertEqual(len(payloads), 1)
            payload = payloads[0].read_text(encoding="utf-8")
            self.assertIn("SECRET-BODY", payload)
            self.assertNotIn("</script>", payload)
            self.assertIn("<\\/script>", payload)
            self.assertFalse((out / "data" / "stale.js").exists())

            node = shutil.which("node")
            if node:
                inline_scripts = re.findall(
                    r"<script>(.*?)</script>", index, flags=re.DOTALL
                )
                self.assertEqual(len(inline_scripts), 1)
                script = out / "browser.js"
                script.write_text(inline_scripts[0], encoding="utf-8")
                syntax = subprocess.run(
                    [node, "--check", str(script)],
                    check=False, capture_output=True, text=True,
                )
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                payload_syntax = subprocess.run(
                    [node, "--check", str(payloads[0])],
                    check=False, capture_output=True, text=True,
                )
                self.assertEqual(payload_syntax.returncode, 0, payload_syntax.stderr)

    def test_vendored_dompurify_asset_has_expected_digest(self):
        asset = TOOLS_DIR.parent / "reports-browser" / "dompurify.min.js"
        self.assertTrue(asset.is_file())
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "89e1fa7647cb495370d3a997ace4387f5d15d9f4c5af12352c53daa400956287",
        )

    def test_cli_generates_complete_local_browser_only_in_requested_temp_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            report_dir = reports / "en"
            report_dir.mkdir(parents=True)
            metadata = generate_metadata(
                word_count=321, reading_time=2, data_until="2026-07",
                generate_time="2026-07-22 00:00:00", depth_mode="quick",
                source_count=1, top_sources=["Example"],
                skill_version="test", lang="en",
            )["full_block"]
            (report_dir / "temporary-20260722-000000.md").write_text(
                f"# Temporary Report\n\n{metadata}\n\nTemporary body.\n",
                encoding="utf-8",
            )
            output = root / "browser"

            result = subprocess.run([
                sys.executable, str(TOOLS_DIR / "generate_pages.py"),
                "--local", "--reports-dir", str(reports),
                "--output-dir", str(output),
            ], check=False, capture_output=True, text=True)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "reports.json").is_file())
            self.assertEqual(len(list((output / "data").glob("*.js"))), 1)
            for asset in (
                "marked.min.js", "dompurify.min.js", "html-docx.min.js",
                "html2pdf.bundle.min.js", "favicon.svg",
            ):
                self.assertTrue((output / asset).is_file(), asset)


if __name__ == "__main__":
    unittest.main()
