import pytest

from arklight.api import (
    Audio,
    Blockquote,
    Button,
    Caption,
    Code,
    Container,
    Details,
    FieldSet,
    Figure,
    FigCaption,
    Form,
    Header,
    Heading,
    HorizontalRule,
    Image,
    Input,
    Label,
    Legend,
    LineBreak,
    Link,
    Nav,
    Option,
    Page,
    Pre,
    Select,
    Source,
    Summary,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeaderCell,
    TableRow,
    Text,
    Textarea,
    Video,
)
from arklight.backend.html.render import HTMLBackend
from arklight.ir.build import build_website_ir
from arklight.ir.normalize import normalize_ark_ast
from arklight.ir.validate import validate_ark_ast


def render(pages: dict, site_name: str = "site"):
    normalized = normalize_ark_ast(pages)
    validate_ark_ast(normalized)
    ir = build_website_ir(site_name, normalized)
    return HTMLBackend().render(ir)


def test_renders_basic_page_to_html():
    output = render({"/": Page(Heading("Hi"), Text("body"), title="My Page")})
    html = output["index.html"]
    assert "<!DOCTYPE html>" in html
    assert "<title>My Page</title>" in html
    assert "<h1>Hi</h1>" in html
    assert "<p>body</p>" in html


def test_route_to_file_path_mapping():
    output = render(
        {
            "/": Page(Heading("Home")),
            "/about": Page(Heading("About")),
            "/blog/post-one": Page(Heading("Post")),
        }
    )
    assert set(output.keys()) == {"index.html", "about.html", "blog/post-one.html"}


def test_heading_level_prop_controls_tag():
    output = render({"/": Page(Heading("Sub", level=3))})
    assert "<h3>Sub</h3>" in output["index.html"]


def test_link_href_and_image_src_render_as_attributes():
    output = render({"/": Page(Container(Link("go", href="/x"), Image(src="a.png", alt="pic")))})
    html = output["index.html"]
    assert '<a href="/x">go</a>' in html
    assert '<img src="a.png" alt="pic" />' in html


def test_html_escaping_of_text_content():
    output = render({"/": Page(Text("<script>alert(1)</script>"))})
    html = output["index.html"]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_button_renders_as_button_tag():
    output = render({"/": Page(Button("Click me"))})
    assert "<button>Click me</button>" in output["index.html"]


def test_unknown_prop_becomes_data_attribute():
    output = render({"/": Page(Container(Text("x"), foo="bar"))})
    assert 'data-foo="bar"' in output["index.html"]


def test_unknown_route_href_left_untouched():
    # "/x" isn't a registered route in this site, so it can't be a
    # relative-path target -- it's left exactly as written.
    output = render({"/": Page(Link("go", href="/x"))})
    assert '<a href="/x">go</a>' in output["index.html"]


def test_known_route_href_rewritten_to_relative_path_same_level():
    output = render(
        {
            "/": Page(Link("About", href="/about")),
            "/about": Page(Link("Home", href="/")),
        }
    )
    assert '<a href="about.html">About</a>' in output["index.html"]
    assert '<a href="index.html">Home</a>' in output["about.html"]


def test_known_route_href_rewritten_across_nested_depth():
    output = render(
        {
            "/": Page(Link("Post", href="/blog/post")),
            "/blog/post": Page(Link("Home", href="/")),
        }
    )
    assert '<a href="blog/post.html">Post</a>' in output["index.html"]
    assert '<a href="../index.html">Home</a>' in output["blog/post.html"]


def test_image_src_relative_asset_path_rewritten_for_nested_pages():
    # Bugfix: a relative asset reference like "sprites/25.png" is
    # root-relative (assets/ is copied to <output_dir>/assets by the
    # build), same as styles.css/favicon -- so it must be corrected the
    # same way when the page itself is nested, not left verbatim.
    output = render(
        {
            "/": Page(Image(src="sprites/25.png", alt="pikachu")),
            "/pokemon/pikachu": Page(Image(src="sprites/25.png", alt="pikachu")),
        }
    )
    assert '<img src="sprites/25.png" alt="pikachu" />' in output["index.html"]
    assert '<img src="../sprites/25.png" alt="pikachu" />' in output["pokemon/pikachu.html"]


# ---------------------------------------------------------------------------
# HTML backend refactor Stage 2 (docs/Backends/HTML-BACKEND-REFACTOR.md /
# docs/Backends/REFACTOR-INDEX.md row 1, `html-2`): the
# `UNROUTED_REFERENCE_ATTRS` fix. `srcset`/`poster`/`action`/`formaction`
# are now route/asset-rewritten the same way `href`/`src` already were,
# instead of only triggering a build-time warning -- see
# `arklight/backend/html/routing.py`'s module docstring for the
# per-attribute reasoning. `test_form_elements_render_with_form_attrs`
# above already covers the "unknown route left untouched, no warning"
# half of this for `action`; the tests below cover the "known route/
# asset actually rewritten" half for all four attributes.
# ---------------------------------------------------------------------------


def test_known_route_form_action_rewritten_to_relative_path():
    output = render(
        {
            "/": Page(Form(action="/thanks", method="post")),
            "/thanks": Page(Heading("Thanks")),
        }
    )
    assert '<form action="thanks.html" method="post">' in output["index.html"]


def test_known_route_formaction_rewritten_and_reaches_the_real_attribute():
    # Also exercises the separate pre-existing bug fixed alongside this:
    # `formaction` was missing from PASSTHROUGH_ATTRS entirely, so it
    # used to render as `data-formaction` regardless of routing.
    output = render(
        {
            "/": Page(Button("Save & continue", type="submit", formaction="/next")),
            "/next": Page(Heading("Next")),
        }
    )
    html = output["index.html"]
    assert 'formaction="next.html"' in html
    assert "data-formaction" not in html


def test_nested_page_known_route_formaction_rewritten_across_depth():
    output = render(
        {
            "/": Page(Heading("Home")),
            "/blog/post": Page(Button("Reply", type="submit", formaction="/")),
        }
    )
    assert 'formaction="../index.html"' in output["blog/post.html"]


def test_video_poster_relative_asset_path_rewritten_for_nested_pages():
    # Same asset-path bug class test_image_src_relative_asset_path_...
    # covers for `src`, now also covered for `poster` -- a video poster
    # names a static image asset, not a route (see routing.py).
    output = render(
        {
            "/": Page(Video(Source(src="a.mp4"), poster="cover.jpg")),
            "/films/one": Page(Video(Source(src="a.mp4"), poster="cover.jpg")),
        }
    )
    assert 'poster="cover.jpg"' in output["index.html"]
    assert 'poster="../cover.jpg"' in output["films/one.html"]


def test_video_poster_known_route_resolved_like_an_embed():
    # ASSET_OR_ROUTE_AWARE_ATTRS checks known routes first (an IFrame-
    # style embed) before falling back to asset resolution -- `poster`
    # gets that same route-checked-first treatment `src` already has.
    output = render(
        {
            "/": Page(Video(Source(src="a.mp4"), poster="/about")),
            "/about": Page(Heading("About")),
        }
    )
    assert 'poster="about.html"' in output["index.html"]


def test_picture_source_srcset_multiple_entries_asset_paths_rewritten_for_nested_pages():
    from arklight.api import Picture, PictureSource

    output = render(
        {
            "/": Page(Picture(PictureSource(srcset="wide.jpg 800w, narrow.jpg 400w"))),
            "/blog/post": Page(Picture(PictureSource(srcset="wide.jpg 800w, narrow.jpg 400w"))),
        }
    )
    assert 'srcset="wide.jpg 800w, narrow.jpg 400w"' in output["index.html"]
    assert 'srcset="../wide.jpg 800w, ../narrow.jpg 400w"' in output["blog/post.html"]


def test_picture_source_srcset_single_entry_with_density_descriptor():
    from arklight.api import Picture, PictureSource

    output = render(
        {
            "/": Page(Picture(PictureSource(srcset="hi-res.jpg 2x"))),
            "/blog/post": Page(Picture(PictureSource(srcset="hi-res.jpg 2x"))),
        }
    )
    assert 'srcset="hi-res.jpg 2x"' in output["index.html"]
    assert 'srcset="../hi-res.jpg 2x"' in output["blog/post.html"]


def test_picture_source_srcset_external_url_left_untouched():
    from arklight.api import Picture, PictureSource

    output = render({"/": Page(Picture(PictureSource(srcset="https://cdn.example.com/wide.jpg 800w")))})
    assert 'srcset="https://cdn.example.com/wide.jpg 800w"' in output["index.html"]


def test_image_src_leading_slash_asset_path_rewritten_for_nested_pages():
    # Bugfix: a leading-slash "absolute" asset path is likewise a
    # root-relative asset, not an (unregistered) route -- it must
    # resolve the same way the equivalent value without the leading
    # "/" does, not silently pass through unchanged.
    output = render({"/pokemon/pikachu": Page(Image(src="/sprites/25.png", alt="pikachu"))})
    assert '<img src="../sprites/25.png" alt="pikachu" />' in output["pokemon/pikachu.html"]


def test_image_src_matching_known_route_still_resolved_as_route():
    # If a `src` happens to match a real page route (e.g. an IFrame
    # embedding another ARKlight page), that takes priority over
    # treating it as a static asset.
    output = render(
        {
            "/": Page(Text("home")),
            "/pokemon/pikachu": Page(Image(src="/", alt="home thumbnail")),
        }
    )
    assert '<img src="../index.html" alt="home thumbnail" />' in output["pokemon/pikachu.html"]


def test_image_src_external_and_data_urls_left_untouched():
    output = render(
        {
            "/pokemon/pikachu": Page(
                Container(
                    Image(src="https://example.com/a.png", alt="ext"),
                    Image(src="data:image/png;base64,abc==", alt="inline"),
                    Image(src="//cdn.example.com/a.png", alt="protocol-relative"),
                )
            )
        }
    )
    html = output["pokemon/pikachu.html"]
    assert '<img src="https://example.com/a.png" alt="ext" />' in html
    assert '<img src="data:image/png;base64,abc==" alt="inline" />' in html
    assert '<img src="//cdn.example.com/a.png" alt="protocol-relative" />' in html


def test_stylesheet_link_present_and_relative_for_nested_pages():
    output = render(
        {
            "/": Page(Text("home")),
            "/blog/post": Page(Text("post")),
        }
    )
    assert '<link rel="stylesheet" href="styles.css">' in output["index.html"]
    assert '<link rel="stylesheet" href="../styles.css">' in output["blog/post.html"]


def test_class_name_prop_renders_as_class_attribute():
    output = render({"/": Page(Container(Text("x"), class_name="nav"))})
    assert 'class="nav"' in output["index.html"]


def test_style_dict_prop_renders_as_inline_css():
    output = render({"/": Page(Text("hi", style={"color": "red", "font_weight": "bold"}))})
    html = output["index.html"]
    assert "color: red" in html
    assert "font-weight: bold" in html


def test_script_tag_present_and_relative_for_nested_pages():
    output = render(
        {
            "/": Page(Text("home")),
            "/blog/post": Page(Text("post")),
        }
    )
    assert '<script src="arklight.js" defer></script>' in output["index.html"]
    assert '<script src="../arklight.js" defer></script>' in output["blog/post.html"]


def test_behavior_props_render_as_data_ark_attributes():
    output = render(
        {"/": Page(Button("Show", on_click="toggle", behavior_target="#panel", toggle_class="hidden"))}
    )
    html = output["index.html"]
    # htmx-5: reverted to a bespoke data-ark-on-click attribute, but
    # with a "behavior:" prefix now (matched-pair with the "action:"
    # prefix ActionRef already used) -- see arklight/backend/html/
    # attrs.py's module docstring and tests/test_htmx_5.py for why
    # htmx-1's hx-on:click shape was reverted (it routed every
    # behavior click through HTMX's own eval-equivalent
    # Function-from-string attribute dispatch).
    assert 'data-ark-on-click="behavior:toggle"' in html
    assert "hx-on:click" not in html
    assert "arkRunBehavior" not in html
    assert 'data-ark-target="#panel"' in html
    assert 'data-ark-toggle-class="hidden"' in html
    # And NOT emitted as a real "target" HTML attribute, which would be wrong
    # (must check for a standalone " target=", not the substring inside
    # "data-ark-target"):
    assert ' target="#panel"' not in html


def test_external_and_fragment_hrefs_are_not_rewritten():
    output = render(
        {
            "/": Page(
                Container(
                    Link("ext", href="https://example.com"),
                    Link("frag", href="#section"),
                    Link("mail", href="mailto:a@b.com"),
                )
            )
        }
    )
    html = output["index.html"]
    assert 'href="https://example.com"' in html
    assert 'href="#section"' in html
    assert 'href="mailto:a@b.com"' in html


def test_semantic_layout_tags_render_correctly():
    output = render(
        {
            "/": Page(
                Header(Nav(Link("Home", href="/"))),
                Text("body"),
            )
        }
    )
    html = output["index.html"]
    assert "<header>" in html and "</header>" in html
    assert "<nav>" in html and "</nav>" in html


def test_figure_and_figcaption_render():
    output = render({"/": Page(Figure(Image(src="a.png", alt="pic"), FigCaption("a caption")))})
    html = output["index.html"]
    assert "<figure>" in html
    assert "<figcaption>a caption</figcaption>" in html


def test_details_summary_render_native_disclosure():
    output = render({"/": Page(Details(Summary("More"), Text("hidden content"), open=True))})
    html = output["index.html"]
    assert "<details open>" in html
    assert "<summary>More</summary>" in html


def test_pre_code_pairing_renders_as_container():
    output = render({"/": Page(Pre(Code("x = 1")))})
    assert "<pre><code>x = 1</code></pre>" in output["index.html"]


def test_blockquote_renders():
    output = render({"/": Page(Blockquote(Text("quoted")))})
    assert "<blockquote><p>quoted</p></blockquote>" in output["index.html"]


def test_void_tags_render_self_closing():
    output = render({"/": Page(Text("a"), HorizontalRule(), LineBreak())})
    html = output["index.html"]
    assert "<hr />" in html
    assert "<br />" in html


def test_form_elements_render_with_form_attrs():
    output = render(
        {
            "/": Page(
                Form(
                    Label("Email", for_="email"),
                    Input(type="email", name="email", id="email", required=True),
                    Textarea("", name="message", rows=4),
                    Select(Option("A", value="a"), Option("B", value="b")),
                    action="/submit",
                    method="post",
                )
            )
        }
    )
    html = output["index.html"]
    assert '<label for="email">Email</label>' in html
    assert '<input type="email" name="email" id="email" required />' in html
    assert '<textarea name="message" rows="4"></textarea>' in html
    assert '<option value="a">A</option>' in html
    assert '<form action="/submit" method="post">' in html


def test_fieldset_and_legend_render():
    output = render({"/": Page(FieldSet(Legend("Details"), Text("x")))})
    html = output["index.html"]
    assert "<fieldset>" in html
    assert "<legend>Details</legend>" in html


def test_table_elements_render():
    output = render(
        {
            "/": Page(
                Table(
                    Caption("A table"),
                    TableHead(TableRow(TableHeaderCell("Name"))),
                    TableBody(TableRow(TableCell("Alice"))),
                )
            )
        }
    )
    html = output["index.html"]
    assert "<table>" in html
    assert "<caption>A table</caption>" in html
    # TableHeaderCell/TableCell are real containers (like Container),
    # not text-only, so they can hold links, spans, etc. -- a bare
    # string child is wrapped in a Text node the same way it would be
    # inside a Container, hence the nested <p>.
    assert "<thead><tr><th><p>Name</p></th></tr></thead>" in html
    assert "<tbody><tr><td><p>Alice</p></td></tr></tbody>" in html


def test_media_elements_render_with_source_child():
    output = render(
        {
            "/": Page(
                Video(Source(src="movie.mp4", type="video/mp4"), controls=True),
                Audio(Source(src="song.mp3"), controls=True),
            )
        }
    )
    html = output["index.html"]
    assert '<video controls>' in html
    assert '<source src="movie.mp4" type="video/mp4" />' in html
    assert '<audio controls>' in html


def test_aria_prop_convention_renders_as_aria_dash_attribute():
    output = render({"/": Page(Button("Close", aria_label="Close dialog", aria_expanded=False))})
    html = output["index.html"]
    assert 'aria-label="Close dialog"' in html
    # aria_expanded=False is falsy and therefore omitted, matching the
    # existing convention for other boolean-ish props.
    assert "aria-expanded" not in html


def test_aria_boolean_true_renders_as_bare_attribute():
    output = render({"/": Page(Container(Text("x"), aria_hidden=True))})
    assert "aria-hidden" in output["index.html"]


def test_page_without_head_meta_props_renders_unchanged():
    # No description/favicon/og_* props supplied -> no new tags at all,
    # existing sites' output is byte-for-byte unaffected.
    html = render({"/": Page(Heading("Hi"), title="My Page")})["index.html"]
    assert "description" not in html
    assert "og:" not in html
    assert 'rel="icon"' not in html


def test_page_description_renders_as_meta_description():
    html = render({"/": Page(Heading("Hi"), description="A test page.")})["index.html"]
    assert '<meta name="description" content="A test page.">' in html


def test_page_favicon_renders_as_relative_icon_link():
    html = render({"/": Page(Heading("Hi"), favicon="assets/favicon.ico")})["index.html"]
    assert '<link rel="icon" href="assets/favicon.ico">' in html


def test_page_favicon_is_relative_from_nested_route():
    output = render({"/blog/post-one": Page(Heading("Hi"), favicon="assets/favicon.ico")})
    html = output["blog/post-one.html"]
    assert '<link rel="icon" href="../assets/favicon.ico">' in html


def test_page_og_tags_default_to_title_and_description():
    html = render(
        {"/": Page(Heading("Hi"), title="My Page", description="A test page.")}
    )["index.html"]
    assert '<meta property="og:title" content="My Page">' in html
    assert '<meta property="og:description" content="A test page.">' in html


def test_page_og_title_overrides_title_fallback():
    html = render(
        {"/": Page(Heading("Hi"), title="My Page", og_title="Custom OG Title")}
    )["index.html"]
    assert '<meta property="og:title" content="Custom OG Title">' in html


def test_page_og_image_renders_and_escapes():
    html = render({"/": Page(Heading("Hi"), og_image="assets/social.png")})["index.html"]
    assert '<meta property="og:image" content="assets/social.png">' in html


def test_page_description_is_html_escaped():
    html = render({"/": Page(Heading("Hi"), description='<script>alert("x")</script>')})[
        "index.html"
    ]
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


# v0.048 Stage A: structured <head> extension (`meta`/`links`).


def test_page_meta_renders_name_content_pairs():
    html = render({"/": Page(Heading("Hi"), meta={"theme-color": "#0f0f0f"})})["index.html"]
    assert '<meta name="theme-color" content="#0f0f0f">' in html


def test_page_meta_renders_multiple_entries_in_order():
    html = render(
        {"/": Page(Heading("Hi"), meta={"author": "ARK", "robots": "noindex"})}
    )["index.html"]
    assert '<meta name="author" content="ARK">' in html
    assert '<meta name="robots" content="noindex">' in html
    assert html.index('name="author"') < html.index('name="robots"')


def test_page_meta_is_html_escaped():
    html = render({"/": Page(Heading("Hi"), meta={"x": '"><script>alert(1)</script>'})})[
        "index.html"
    ]
    assert "<script>alert" not in html


def test_page_links_renders_arbitrary_attributes():
    html = render(
        {
            "/": Page(
                Heading("Hi"),
                links=[{"rel": "preconnect", "href": "https://fonts.gstatic.com"}],
            )
        }
    )["index.html"]
    assert '<link rel="preconnect" href="https://fonts.gstatic.com">' in html


def test_page_links_renders_multiple_link_tags():
    html = render(
        {
            "/": Page(
                Heading("Hi"),
                links=[
                    {"rel": "preconnect", "href": "https://fonts.gstatic.com"},
                    {"rel": "icon", "href": "assets/icon-32.png", "sizes": "32x32"},
                ],
            )
        }
    )["index.html"]
    assert '<link rel="preconnect" href="https://fonts.gstatic.com">' in html
    assert '<link rel="icon" href="assets/icon-32.png" sizes="32x32">' in html


def test_page_links_is_html_escaped():
    html = render(
        {"/": Page(Heading("Hi"), links=[{"rel": "icon", "href": '"><script>x</script>'}])}
    )["index.html"]
    assert "<script>x" not in html


def test_page_without_meta_or_links_renders_unchanged():
    # No meta/links supplied -> no extra <meta>/<link> tags beyond the
    # fixed charset/viewport/stylesheet ones every page already emits.
    html = render({"/": Page(Heading("Hi"), title="My Page")})["index.html"]
    assert '<meta name="viewport"' in html
    assert '<link rel="stylesheet"' in html
    assert html.count("<meta") == 2
    assert html.count("<link") == 1


def test_page_meta_invalid_shape_raises_validation_error():
    from arklight.ir.validate import ValidationError

    with pytest.raises(ValidationError):
        render({"/": Page(Heading("Hi"), meta={})})


def test_page_links_missing_rel_raises_validation_error():
    from arklight.ir.validate import ValidationError

    with pytest.raises(ValidationError):
        render({"/": Page(Heading("Hi"), links=[{"href": "assets/icon.png"}])})
