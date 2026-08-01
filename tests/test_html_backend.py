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
    assert 'data-ark-on-click="toggle"' in html
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
