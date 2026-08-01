from arklight.api import Button, Container, Heading, Image, Link, Page, Text
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
