import pytest

from arklight.parser.discover import discover


def test_discover_finds_site_and_pages():
    source = """
from arklight import *

site = Site()

@site.page("/")
def home():
    return Page(Heading("Hi"))

@site.page("/about")
def about():
    return Page(Text("About"))
"""
    result = discover(source)
    assert result.variable_name == "site"
    routes = {p.route: p.function_name for p in result.pages}
    assert routes == {"/": "home", "/about": "about"}


def test_discover_raises_without_site():
    source = "x = 1\n"
    with pytest.raises(ValueError, match="No `Site\\(\\)` instantiation found"):
        discover(source)


def test_discover_raises_without_pages():
    source = "from arklight import *\nsite = Site()\n"
    with pytest.raises(ValueError, match="No pages registered"):
        discover(source)


def test_discover_raises_on_syntax_error():
    with pytest.raises(SyntaxError):
        discover("def broken(:\n")


def test_discover_ignores_unrelated_decorators():
    source = """
from arklight import *
site = Site()

def other_decorator(fn):
    return fn

@other_decorator
def not_a_page():
    pass

@site.page("/")
def home():
    return Page(Heading("Hi"))
"""
    result = discover(source)
    assert len(result.pages) == 1
    assert result.pages[0].function_name == "home"
