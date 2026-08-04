"""
ARK Bundle sealing -- v0.037.

Turns the ZIP half of an `.ark` bundle from a plain, generically-
openable archive into an opaque binary blob: a small stdlib-only
encrypt-then-MAC construction built from `hmac`/`hashlib`/`secrets`,
no third-party crypto dependency, matching this project's zero-
runtime-dependency design (see pyproject.toml -- no `[project]
dependencies` at all).

    stream cipher:  HMAC-SHA256(key, salt || counter) concatenated
                     across counter = 0, 1, 2, ... and XORed against
                     the plaintext -- a standard, minimal way to turn
                     a MAC into a keystream generator.
    authentication:  HMAC-SHA256(key, salt || ciphertext), checked with
                     `hmac.compare_digest` before any bytes are trusted
                     enough to hand to `zipfile` -- corrupted or
                     tampered archives are rejected outright rather
                     than partially decrypted.

Two key modes, chosen by whether `pack()` was given a passphrase:

- **Passphrase mode** (`arklight pack ... --passphrase ...`): the key
  is derived from the passphrase via PBKDF2-HMAC-SHA256 (600,000
  iterations as of `ARKSEAL2` -- see `_LEGACY_MAGIC` below for how
  older bundles sealed at 200,000 still unseal correctly) and a
  random per-bundle salt. Nobody without that
  passphrase -- including someone who has ARKlight's own source --
  can derive the key. This is real confidentiality.
- **Embedded-key mode** (the default, no passphrase given): the key is
  a random 32 bytes generated fresh per bundle and stored, unencrypted,
  in the sealed blob itself, so `arklight unpack` can always open a
  default-sealed bundle without extra input. This blocks a generic
  archive tool, a "rename to .zip", or a hex-editor guess from reading
  or splicing the archive -- but it is NOT a secret from a determined
  person who has (or writes) an ARKlight-compatible unsealer, since the
  key travels with the file by construction. Treat embedded-key sealing
  as tamper-evident packaging, not encryption; use `--passphrase` for
  actual confidentiality.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

MAGIC = b"ARKSEAL2"

# v0.037 originally sealed archives under this 8-byte magic, always at
# a fixed 200,000 PBKDF2 iterations with no way to change it later
# without breaking every bundle already sealed under the old count.
# OWASP's current PBKDF2-HMAC-SHA256 guidance (2023) is 600,000
# iterations, not 200,000 -- but bumping `_PBKDF2_ITERATIONS` in place
# would silently break `unseal()` on every bundle sealed by an older
# ARKlight build: the iteration count was never *in* the blob, so an
# unsealer with a different hardcoded constant just derives the wrong
# key and reports "Integrity check failed" (indistinguishable from a
# wrong passphrase). The fix -- matching the format's own "opaque,
# self-describing blob" design -- is to put the iteration count in the
# blob instead of assuming it: `ARKSEAL2` adds a 4-byte big-endian
# iteration count field, present only in passphrase mode (embedded-key
# mode never runs PBKDF2, so it has nothing to record). `unseal()`
# still recognizes `ARKSEAL1` and falls back to the old fixed count
# for it -- every bundle sealed by every past ARKlight release still
# opens unchanged. Only `seal()`'s *output* changes (new bundles are
# always `ARKSEAL2`); nothing about reading old ones does.
_LEGACY_MAGIC = b"ARKSEAL1"
SEALED_MAGICS = (MAGIC, _LEGACY_MAGIC)

_SALT_LEN = 16
_KEY_LEN = 32
_TAG_LEN = 32
_ITER_FIELD_LEN = 4
_PBKDF2_ITERATIONS = 600_000
_LEGACY_PBKDF2_ITERATIONS = 200_000

_MODE_PASSPHRASE = 0x00
_MODE_EMBEDDED_KEY = 0x01


class SealError(Exception):
    """Raised when a sealed archive can't be unsealed: wrong/missing
    passphrase, or the sealed bytes are corrupt or tampered with."""


def _keystream(key: bytes, salt: bytes, length: int) -> bytes:
    blocks = []
    produced = 0
    counter = 0
    while produced < length:
        block = hmac.new(key, salt + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        blocks.append(block)
        produced += len(block)
        counter += 1
    return b"".join(blocks)[:length]


def _xor(a: bytes, b: bytes) -> bytes:
    if not a:
        return b""
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big")


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, iterations, dklen=_KEY_LEN
    )


def seal(payload: bytes, *, passphrase: str | None = None) -> bytes:
    """
    Encrypt `payload` (the ZIP bytes) into an opaque, self-describing
    blob: `MAGIC || salt || mode_byte || [iterations] || [key] || tag
    || ciphertext`. Always emits the current `ARKSEAL2` format (with
    an embedded PBKDF2 iteration count in passphrase mode) -- see the
    module-level comment above `_LEGACY_MAGIC` for why.
    """
    salt = secrets.token_bytes(_SALT_LEN)

    if passphrase is not None:
        key = _derive_key(passphrase, salt, _PBKDF2_ITERATIONS)
        mode = _MODE_PASSPHRASE
        mode_fields = _PBKDF2_ITERATIONS.to_bytes(_ITER_FIELD_LEN, "big")
    else:
        key = secrets.token_bytes(_KEY_LEN)
        mode = _MODE_EMBEDDED_KEY
        mode_fields = key

    ciphertext = _xor(payload, _keystream(key, salt, len(payload)))
    tag = hmac.new(key, salt + ciphertext, hashlib.sha256).digest()

    return MAGIC + salt + bytes([mode]) + mode_fields + tag + ciphertext


def unseal(blob: bytes, *, passphrase: str | None = None) -> bytes:
    """
    Reverse of `seal()`. Understands both the current `ARKSEAL2`
    format and every bundle sealed by an older ARKlight release under
    `ARKSEAL1` (fixed 200,000 PBKDF2 iterations, no embedded count).
    Raises SealError if `blob` isn't a sealed ARKlight archive, if it
    needed a passphrase that wasn't supplied, or if the authentication
    tag doesn't match (wrong passphrase, or the bytes were
    corrupted/tampered with).
    """
    if blob.startswith(MAGIC):
        legacy = False
    elif blob.startswith(_LEGACY_MAGIC):
        legacy = True
    else:
        raise SealError("Not a sealed ARKlight archive (missing ARKSEAL magic).")

    offset = len(MAGIC)  # both magics are the same length
    salt = blob[offset : offset + _SALT_LEN]
    offset += _SALT_LEN

    if offset >= len(blob):
        raise SealError("Sealed archive is truncated.")
    mode = blob[offset]
    offset += 1

    if mode == _MODE_EMBEDDED_KEY:
        key = blob[offset : offset + _KEY_LEN]
        offset += _KEY_LEN
    elif mode == _MODE_PASSPHRASE:
        if passphrase is None:
            raise SealError(
                "This bundle was sealed with a passphrase -- pass `passphrase=...` "
                "(or `--passphrase` on the CLI) to unseal it."
            )
        if legacy:
            iterations = _LEGACY_PBKDF2_ITERATIONS
        else:
            iterations = int.from_bytes(blob[offset : offset + _ITER_FIELD_LEN], "big")
            offset += _ITER_FIELD_LEN
        key = _derive_key(passphrase, salt, iterations)
    else:
        raise SealError(f"Unrecognized seal mode byte: {mode!r}.")

    tag = blob[offset : offset + _TAG_LEN]
    offset += _TAG_LEN
    ciphertext = blob[offset:]

    expected_tag = hmac.new(key, salt + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise SealError(
            "Integrity check failed -- wrong passphrase, or the bundle's archive "
            "half was corrupted or tampered with."
        )

    return _xor(ciphertext, _keystream(key, salt, len(ciphertext)))
