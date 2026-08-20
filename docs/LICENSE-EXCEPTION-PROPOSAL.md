# ARKlight / carklight — License Proposal: GPLv3 + ARKlight-Specific Exceptions

Status: **exploratory design note, not committed, not legal advice.**
This draft contains literal proposed license text so the shape of the
change is fully visible — that is not the same as this text being
final. Before either repo's `LICENSE` file actually changes, this
needs review by a lawyer, ideally one with FSF-license experience, the
same way Bison's and GCC's own exception texts went through real
revision and community dispute before settling. Treat everything below
as a complete draft to react to, not a ruling.

---

## 1. What this is

Not "adopt GCC's license" or "adopt Bison's license." Both of those
are fixed texts tied to those specific projects. What follows is:
**GPLv3-or-later, unmodified, as the base — with a new, ARKlight-
specific exception paragraph attached to each repo**, built by taking
the *structure* of Bison's and GCC's exceptions (the only two
mechanisms that exist for this problem) and substituting ARKlight's
own files, names, and existing attribution requirement.

The accurate SPDX-style name for the result would be something like
`GPL-3.0-or-later WITH ARKlight-runtime-exception` for ARKlight-py, and
`GPL-3.0-or-later WITH carklight-linking-exception` for carklight —
the same pattern SPDX already uses for `GPL-2.0-with-bison-exception`
and `GPL-3.0-with-GCC-exception`. This is the standard, and only,
mechanism for attaching project-specific carve-outs to GPL: the base
GPL text can't itself be edited and still be called GPL, so every
project in this position ends up with its own named variant.

---

## 2. The problem, restated precisely

Two different technical mechanisms put ARKlight's own bytes inside
something a third party distributes, and they need different clauses:

- **Text embedding** (ARKlight-py): `arklight.js` is copied verbatim
  into every compiled site's output.
- **Object-code linking** (carklight, once desktop/Android backends
  exist per `docs/DESIGN-NOTES.md`): `libcarklight.so` /
  `C_ARKlight_gui.so` get linked into someone else's compiled app.

ARKlight-py already has a bespoke clause for the first case.
carklight currently has no clause of its own — `C_ARKlight/README.md`
just says "Tracks upstream ARKlight's license," inheriting a clause
written for a mechanism carklight doesn't actually use.

**What's already fine and needs no clause at all:** merely running
`arklight`/`carklight` to compile a project has never made that
project's own output GPL. Mere tool use isn't a derivative-work event.
Nothing below changes that baseline.

**Also already fine, worth naming explicitly:** per `PROPOSAL.md`
§4.3's two JS distribution paths — the subprocess-spawn engine (pipe
`.arklight` bytes to a compiled `carklight` binary over stdin/stdout,
read output back) is *mere use of a tool*, exactly like invoking `gcc`
from a shell script. It needs no exception. Only the FFI/native-addon
engine — where `libcarklight` is actually linked into another
process's address space — is the case the carklight exception below
is for.

---

## 3. Precedent

**Bison's exception** (added in Bison v2.2, after the FSF found plain
GPL alone forced every Bison-generated parser to also be GPL — an
outcome they later called a mistake) is the model for ARKlight-py,
because it covers the same mechanism: a tool's own source, copied
verbatim into its output.

**GCC's Runtime Library Exception (RLE)** covers `libgcc`/`libstdc++`
being linked into a compiled binary. This is the model for carklight,
because that's carklight's actual mechanism once anything links
against `libcarklight`.

---

## 4. Draft text — ARKlight-py (`ARKlight/LICENSE`)

Replace the current bespoke additional-terms section with:

```
ARKLIGHT RUNTIME EXCEPTION

As a special exception, you may create a larger work that contains
part or all of an ARKlight runtime file (including, but not limited
to, `arklight.js`, and any file within ARKlight's package that is
copied verbatim into a compiled site's build output) and distribute
that work under terms of your choice, provided that:

  1. The copyright and attribution notice contained within each
     embedded ARKlight runtime file is preserved, unmodified, in the
     distributed work; and

  2. That work is not itself a tool that compiles ARKlight site
     definitions into rendered output, using the runtime file or a
     modified version of it as part of that tool's own output.

This exception does not extend to modifications of an ARKlight
runtime file itself, nor to any ARKlight source code outside of the
runtime file(s) actually embedded in your output -- those remain
governed solely by the GNU General Public License as stated above.

For the avoidance of doubt: this exception is not the reason your own
site's source code, or the HTML/CSS/JS structure and content your site
produces, are free of these terms -- they were never covered by the
GNU General Public License in the first place, since compiling a site
with ARKlight is use of a tool, not incorporation of ARKlight's own
code into your work. This exception exists solely to address the one
case where ARKlight's own code IS incorporated: the embedded runtime
file(s) named above.

Alternatively, if you modify or redistribute an ARKlight runtime file
itself, you may (at your option) remove this special exception for
that file, which will cause it to be licensed under the GNU General
Public License without this special exception.

This special exception was added for ARKlight version [X.X.X].
```

Condition 2 exists for the same reason Bison's has an equivalent
clause ("so long as that work isn't itself a parser generator using
the skeleton") -- it stops the exception from being used to build a
competing ARKlight-compatible compiler that ships the real runtime
file without adopting GPL for the compiler itself.

---

## 5. Draft text — carklight (new `C_ARKlight/LICENSE`)

Replace "Tracks upstream ARKlight's license" with GPLv3-or-later plus:

```
CARKLIGHT LINKING EXCEPTION

As a special exception, if you link this library (`libcarklight`, or
any backend module built from the `core/` or `backends/` directories
of this repository) statically or dynamically with other files to
produce an executable, shared library, or application package
(including but not limited to a desktop application bundle or an
Android APK), this library does not by itself cause the resulting
work to be covered by the GNU General Public License. This exception
does not invalidate any other reason the resulting work might be
covered by the GNU General Public License.

This exception applies only to linking against carklight's compiled
library code as built from this repository's unmodified public
interface (`include/carklight.h`). It does not apply if you copy
carklight's source code, in whole or substantial part, directly into
another work rather than linking against it -- that remains governed
solely by the GNU General Public License as stated above.

Merely invoking a `carklight`-built executable as a separate process
(for example, piping `.arklight` bytes to it over standard input and
reading its output) is use of the program, not linking, and requires
no exception -- it was never covered by the GNU General Public License
to begin with.

This special exception was added for carklight version [X.X.X].
```

The middle paragraph (copying source vs. linking against compiled
output) has no direct GCC RLE equivalent in this simplified form --
GCC's actual RLE has a more elaborate "Eligible Compilation Process"
definition to handle edge cases precisely. Flagged in §7 as something
real legal review needs to tighten, not something this draft claims
to have solved with full rigor.

---

## 6. Where each piece actually attaches

- `ARKlight/LICENSE` -- replace the current additional-terms section
  with §4's text.
- `arklight/pwa.py` / wherever `arklight.js` is emitted -- the
  attribution comment inside the emitted file is the thing condition 1
  in §4 is actually enforcing; confirm it still matches what the
  exception text promises to protect.
- `C_ARKlight/LICENSE` (new file) -- §5's text, GPLv3-or-later plus
  the carklight-specific exception.
- `C_ARKlight/README.md` -- change "Tracks upstream ARKlight's
  license" to point at carklight's own `LICENSE`, noting it shares
  ARKlight's base license family but has its own exception.
- `include/carklight.h` -- add a short header comment noting the
  linking exception applies to this public interface, mirroring how
  GCC's own headers reference RLE.

---

## 7. Open questions before this is more than a draft

- **Legal review of the exact wording**, especially §5's "linking vs.
  copying source" boundary, which is the one place this draft
  simplifies past what GCC's actual RLE bothers to define precisely.
- **Version numbers to fill in** (`[X.X.X]`) -- tie to whichever
  release actually ships this, same as Bison's exception is dated to
  v2.2.
- **Timing for carklight's exception** -- nothing links against
  `libcarklight` yet. Natural trigger point is Stage 7 (ABI freeze) or
  whichever of `v0.060`/`v0.080`-equivalent backend work starts first
  -- settle this before the first real linker, not after.
- **GPLv3-or-later vs. GPLv3-only** -- no reason surfaced here to
  diverge from ARKlight's existing "-or-later" choice, but worth an
  explicit decision rather than an inherited default.

---

## 8. What this doc is not claiming

- That this text is final or litigation-tested. It is structurally
  sound, modeled on two decades-old, real-world-tested precedents, but
  the specific wording is a first draft.
- That either repo's base license family changes. It doesn't --
  GPLv3-or-later stays on both.
- That this is urgent. carklight's exception has nothing to attach to
  yet in shipped code; ARKlight-py's is a wording upgrade to an
  already-working clause, not a fix to a broken one.
