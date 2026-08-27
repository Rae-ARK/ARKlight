import pytest

from arklight.backend.css.selectors import (
    CSSSelectorSyntaxError,
    parse_selector_list,
    render_selector_list,
)


@pytest.mark.parametrize(
    "selector",
    [
        ".a > .b",
        ".a + .b",
        ".a ~ .b",
        ".a .b",
        "h1, h2, h3",
        "blockquote",
        '[type="email"]',
        '[data-x^="foo"]',
        ":not(.a)",
        ":has(> .icon)",
        ":is(h1, h2)",
        ":where(.a, .b)",
        ":nth-child(2n+1)",
        ":nth-child(odd)",
        ":nth-last-of-type(3)",
        ".card::before",
        ".card:hover::after",
        "a.button:hover",
        'div[data-state="open"] .panel',
        ".a:not(.b):hover",
        ":focus-within",
        ":target",
        ":empty",
        ":required",
        ":invalid",
        ":in-range",
        ":only-child",
        "input:required:invalid",
    ],
)
def test_round_trips_a_valid_selector(selector):
    ast = parse_selector_list(selector)
    assert render_selector_list(ast) == selector


@pytest.mark.parametrize(
    "selector",
    [
        "",
        "foo-bar",  # not a known HTML tag
        ".a > > .b",  # dangling combinator
        ".a b .c",  # tag in the middle of a compound
        ":bogus",  # unknown parameterless pseudo-class
        ":nth-child(foo)",  # invalid An+B syntax
        ":nth-child()",  # missing argument
        ".a; DROP TABLE",  # injection attempt
        "[type=email]",  # unquoted attribute value
        ".1abc",  # class name starting with a digit
        ".a,,.b",  # empty item in a comma list
        ":not(> .a)",  # :not() doesn't accept a relative selector
        ".a::bogus",  # unknown pseudo-element
    ],
)
def test_rejects_an_invalid_selector(selector):
    with pytest.raises(CSSSelectorSyntaxError):
        parse_selector_list(selector)


def test_has_accepts_a_relative_selector_but_not_and_where():
    # :has() is the one functional pseudo-class CSS allows to start
    # with a bare combinator ("relative selector"); :not()/:is()/
    # :where() don't.
    parse_selector_list(":has(> .icon)")
    with pytest.raises(CSSSelectorSyntaxError):
        parse_selector_list(":is(> .icon)")
    with pytest.raises(CSSSelectorSyntaxError):
        parse_selector_list(":where(> .icon)")


def test_grouped_selector_list_length_matches_comma_count():
    ast = parse_selector_list("h1, h2, h3")
    assert len(ast) == 3


def test_attribute_selector_rejects_embedded_quote_in_value():
    with pytest.raises(CSSSelectorSyntaxError):
        parse_selector_list('[data-x="foo\\"bar"]')
