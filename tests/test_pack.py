import zipfile
from pathlib import Path

import pytest

from arklight.cli.main import main
from arklight.compiler.pipeline import build
from arklight.packer.bundle import PackError, pack, unpack

SIMPLE_SITE = """
from arklight import *
site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"), Text("Hello from ARKlight."))

@site.page("/about")
def about():
    return Page(Heading("About"))
"""


def write_site(tmp_path: Path) -> Path:
    path = tmp_path / "site.py"
    path.write_text(SIMPLE_SITE)
    return path


def build_dir(tmp_path: Path) -> Path:
    site_path = write_site(tmp_path)
    out_dir = tmp_path / "ARK"
    build(site_path, out_dir)
    return out_dir


def test_pack_produces_a_bundle_file(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"

    result = pack(out_dir, bundle_path)

    assert bundle_path.exists()
    assert result.output_path == bundle_path
    assert "index.html" in result.packed_paths
    assert "styles.css" in result.packed_paths
    assert "arklight.js" in result.packed_paths
    assert "about.html" in result.packed_paths


def test_pack_is_sealed_by_default(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"

    result = pack(out_dir, bundle_path)

    assert result.sealed is True
    assert result.passphrase_protected is False


def test_bundle_front_matter_is_self_contained_html(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    data = bundle_path.read_bytes()
    html_end = data.index(b"</html>") + len(b"</html>")
    front_matter = data[:html_end].decode("utf-8")

    assert front_matter.startswith("<!DOCTYPE html")
    # The <link>/<script src> tags are replaced with inlined content --
    # nothing in the front matter should still point at an external file.
    assert "styles.css" not in front_matter
    assert "arklight.js" not in front_matter
    assert "<style>" in front_matter
    assert "<script>" in front_matter
    # The actual CSS/JS content made it into the inlined tags.
    assert "body" in front_matter  # from the default stylesheet


def test_sealed_bundle_archive_half_is_not_a_valid_zip(tmp_path):
    """The whole point of sealing: a generic archive tool can't open it."""
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    with pytest.raises(zipfile.BadZipFile):
        zipfile.ZipFile(bundle_path)


def test_sealed_bundle_does_not_contain_plaintext_page_source(tmp_path):
    """The un-inlined about.html (only present in the archive half) should
    not appear as readable text anywhere in a sealed bundle."""
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    data = bundle_path.read_bytes()
    assert b"About" not in data  # the <h1>About</h1> text from about.html


def test_pack_plain_opt_out_produces_a_real_zip_tail(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    result = pack(out_dir, bundle_path, sealed=False)

    assert result.sealed is False

    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())
        assert names == {"index.html", "about.html", "styles.css", "arklight.js"}
        # The zip's copy of index.html is the *original*, un-inlined
        # build output -- extracting it should work exactly like a
        # normal `arklight build` folder.
        extracted_index = zf.read("index.html").decode("utf-8")
        assert '<link rel="stylesheet" href="styles.css">' in extracted_index
        assert '<script src="arklight.js" defer></script>' in extracted_index


def test_assets_are_carried_into_the_bundle(tmp_path):
    out_dir = build_dir(tmp_path)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir()
    raw_png = b"\x89PNG\r\n fake"
    (assets_dir / "logo.png").write_bytes(raw_png)

    bundle_path = tmp_path / "site.ark"
    result = pack(out_dir, bundle_path, sealed=False)

    assert "assets/logo.png" in result.packed_paths
    assert result.skipped_paths == []

    with zipfile.ZipFile(bundle_path) as zf:
        assert "assets/logo.png" in zf.namelist()
        # Carried in as raw bytes, untouched.
        assert zf.read("assets/logo.png") == raw_png


def test_pack_raises_on_missing_build_dir(tmp_path):
    with pytest.raises(PackError, match="not found"):
        pack(tmp_path / "does-not-exist", tmp_path / "site.ark")


def test_pack_raises_on_incomplete_build_dir(tmp_path):
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "index.html").write_text("<html></html>")
    # styles.css / arklight.js missing

    with pytest.raises(PackError, match="styles.css"):
        pack(incomplete, tmp_path / "site.ark")


# -- unpack ---------------------------------------------------------------


def test_unpack_roundtrips_a_sealed_embedded_key_bundle(tmp_path):
    out_dir = build_dir(tmp_path)
    (out_dir / "assets").mkdir()
    (out_dir / "assets" / "logo.png").write_bytes(b"\x89PNG fake")

    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    restored_dir = tmp_path / "restored"
    result = unpack(bundle_path, restored_dir)

    assert result.was_sealed is True
    assert set(result.extracted_paths) == {
        "index.html", "about.html", "styles.css", "arklight.js", "assets/logo.png",
    }
    assert (restored_dir / "index.html").exists()
    assert (restored_dir / "assets" / "logo.png").read_bytes() == b"\x89PNG fake"


def test_unpack_roundtrips_a_plain_bundle(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path, sealed=False)

    restored_dir = tmp_path / "restored"
    result = unpack(bundle_path, restored_dir)

    assert result.was_sealed is False
    assert (restored_dir / "index.html").exists()


def test_unpack_roundtrips_a_passphrase_sealed_bundle(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    result = pack(out_dir, bundle_path, passphrase="correct horse battery staple")
    assert result.passphrase_protected is True

    restored_dir = tmp_path / "restored"
    unpacked = unpack(bundle_path, restored_dir, passphrase="correct horse battery staple")

    assert unpacked.was_sealed is True
    assert (restored_dir / "index.html").exists()


def test_unpack_passphrase_sealed_bundle_without_passphrase_fails(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path, passphrase="correct horse battery staple")

    with pytest.raises(PackError, match="passphrase"):
        unpack(bundle_path, tmp_path / "restored")


def test_unpack_passphrase_sealed_bundle_with_wrong_passphrase_fails(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path, passphrase="correct horse battery staple")

    with pytest.raises(PackError, match="Integrity check failed"):
        unpack(bundle_path, tmp_path / "restored", passphrase="wrong guess")


def test_unpack_rejects_tampered_sealed_bundle(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    pack(out_dir, bundle_path)

    data = bytearray(bundle_path.read_bytes())
    data[-1] ^= 0xFF  # flip a bit in the ciphertext tail
    bundle_path.write_bytes(bytes(data))

    with pytest.raises(PackError, match="Integrity check failed"):
        unpack(bundle_path, tmp_path / "restored")


def test_unpack_raises_on_missing_bundle(tmp_path):
    with pytest.raises(PackError, match="not found"):
        unpack(tmp_path / "nope.ark", tmp_path / "restored")


# -- CLI --------------------------------------------------------------------


def test_cli_pack_success(tmp_path, capsys):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"

    exit_code = main(["pack", str(out_dir), "-o", str(bundle_path)])

    assert exit_code == 0
    assert bundle_path.exists()
    captured = capsys.readouterr()
    assert "packed" in captured.out
    assert str(bundle_path) in captured.out
    assert "SEALED" in captured.out


def test_cli_pack_default_output_is_site_ark(tmp_path, monkeypatch):
    out_dir = build_dir(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["pack", str(out_dir)])

    assert exit_code == 0
    assert (tmp_path / "site.ark").exists()


def test_cli_pack_plain_flag_produces_a_real_zip(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"

    exit_code = main(["pack", str(out_dir), "-o", str(bundle_path), "--plain"])

    assert exit_code == 0
    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.testzip() is None


def test_cli_pack_failure_returns_nonzero(tmp_path, capsys):
    missing_dir = tmp_path / "nope"

    exit_code = main(["pack", str(missing_dir)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight pack failed" in captured.err


def test_cli_unpack_roundtrip(tmp_path):
    out_dir = build_dir(tmp_path)
    bundle_path = tmp_path / "site.ark"
    main(["pack", str(out_dir), "-o", str(bundle_path)])

    restored_dir = tmp_path / "restored"
    exit_code = main(["unpack", str(bundle_path), "-o", str(restored_dir)])

    assert exit_code == 0
    assert (restored_dir / "index.html").exists()


def test_cli_unpack_failure_returns_nonzero(tmp_path, capsys):
    exit_code = main(["unpack", str(tmp_path / "nope.ark")])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ARKlight unpack failed" in captured.err
