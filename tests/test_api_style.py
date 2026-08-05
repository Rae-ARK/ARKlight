import pytest

from arklight.api import CSSSyntaxError, Site


def test_style_registers_rules_under_the_given_name():
    site = Site()
    site.style("pull-quote", {"font-style": "italic", "padding": "1em"})

    assert site.custom_styles == {"pull-quote": {"font-style": "italic", "padding": "1em"}}


def test_style_called_twice_with_same_name_overwrites():
    site = Site()
    site.style("brand", {"color": "red"})
    site.style("brand", {"color": "blue"})

    assert site.custom_styles == {"brand": {"color": "blue"}}


def test_style_two_different_names_both_kept():
    site = Site()
    site.style("brand", {"color": "red"})
    site.style("pull-quote", {"font-style": "italic"})

    assert set(site.custom_styles) == {"brand", "pull-quote"}


@pytest.mark.parametrize(
    "bad_name",
    [
        "bad name",  # space
        "bad!name",  # punctuation
        "1bad",  # starts with a digit
        "",  # empty
        ".bad",  # leading dot (not a bare class name)
    ],
)
def test_style_rejects_invalid_class_names(bad_name):
    site = Site()
    with pytest.raises(ValueError, match="valid CSS class name"):
        site.style(bad_name, {"color": "red"})


@pytest.mark.parametrize("good_name", ["brand", "pull-quote", "pull_quote", "-webkit-ish", "a1"])
def test_style_accepts_valid_class_names(good_name):
    site = Site()
    site.style(good_name, {"color": "red"})
    assert good_name in site.custom_styles


def test_style_rejects_empty_rules_dict():
    site = Site()
    with pytest.raises(ValueError, match="non-empty dict"):
        site.style("brand", {})


def test_style_rejects_non_dict_rules():
    site = Site()
    with pytest.raises(ValueError, match="non-empty dict"):
        site.style("brand", "color: red")  # a raw CSS string, not a dict


def test_style_rejects_empty_property_value():
    site = Site()
    with pytest.raises(ValueError, match="non-empty string value"):
        site.style("brand", {"color": ""})


def test_style_rejects_non_string_property_value():
    site = Site()
    with pytest.raises(ValueError, match="non-empty string value"):
        site.style("brand", {"z-index": 5})


def test_style_rejects_empty_property_name():
    site = Site()
    with pytest.raises(ValueError, match="non-empty CSS property name|non-string or empty"):
        site.style("brand", {"": "red"})


def test_new_site_has_no_custom_styles_by_default():
    site = Site()
    assert site.custom_styles == {}


# --- Pseudo-class shorthand (":pseudo:property") -----------------------


def test_style_accepts_hover_pseudo_class_rule():
    site = Site()
    site.style("btn", {"background": "blue", ":hover:background": "red"})

    assert site.custom_styles == {
        "btn": {"background": "blue", ":hover:background": "red"}
    }


@pytest.mark.parametrize(
    "pseudo",
    ["hover", "focus", "focus-visible", "active", "visited", "disabled", "checked"],
)
def test_style_accepts_every_supported_pseudo_class(pseudo):
    site = Site()
    site.style("btn", {f":{pseudo}:color": "red"})

    assert site.custom_styles == {"btn": {f":{pseudo}:color": "red"}}


def test_style_rejects_unsupported_pseudo_class():
    site = Site()
    with pytest.raises(CSSSyntaxError, match="unsupported pseudo-class"):
        site.style("btn", {":visited-evil:color": "red"})


def test_style_rejects_unsupported_pseudo_class_is_also_a_value_error():
    # CSSSyntaxError subclasses ValueError -- existing `except
    # ValueError` call sites keep working unchanged.
    site = Site()
    with pytest.raises(ValueError):
        site.style("btn", {":lang:color": "red"})


def test_style_rejects_malformed_pseudo_class_key():
    site = Site()
    with pytest.raises(CSSSyntaxError, match="invalid pseudo-class rule key"):
        site.style("btn", {":hover": "red"})  # missing ":property"


def test_style_rejects_malformed_plain_property_name():
    site = Site()
    with pytest.raises(CSSSyntaxError, match="invalid CSS property name"):
        site.style("btn", {"1invalid": "red"})


def test_style_accepts_custom_property_name():
    site = Site()
    site.style("btn", {"--brand-color": "red"})
    assert site.custom_styles == {"btn": {"--brand-color": "red"}}


@pytest.mark.parametrize("bad_value", ["red; } .evil {", "red } .x {", "red\ninject: x"])
def test_style_rejects_values_that_could_break_out_of_declaration(bad_value):
    site = Site()
    with pytest.raises(CSSSyntaxError, match="break out of its declaration"):
        site.style("btn", {"color": bad_value})
