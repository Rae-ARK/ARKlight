"""
HTML Backend refactor, Stage 1 (see
docs/Backends/HTML-BACKEND-REFACTOR.md): the first of the six staged
extractions splitting `arklight/backend/html/render.py`'s five
unrelated jobs into their own modules, mirroring the CSS backend
refactor's "modules, not classes-for-everything" split.

This module owns the one piece of that split that's pure data plus a
single tiny pure function: the IR-node-type -> HTML-tag-name mapping.
`TAG_MAP` answers "what tag does this node type render as" for every
node type *except* `Heading` (whose tag depends on its `level` prop,
not just its type -- see `_tag_for`); `VOID_TAGS` answers "does this
tag ever get a closing tag or children" for `_render_node`'s emission
logic. Neither changes at runtime, and neither depends on anything
else in the HTML backend -- routing, attribute rendering, and
per-page assembly (Stages 2-5) all import from here, never the other
way around.

Zero behavior change: same tag names, same void-tag set, same
`_tag_for` logic as before this module existed. `render.py` re-exports
`TAG_MAP`/`VOID_TAGS`/`_tag_for` for backward compatibility with
anything that already imported them from there.
"""

from __future__ import annotations

from arklight.ir.build import IRNode

# Maps an IR node type to an HTML tag name.
TAG_MAP: dict[str, str] = {
    "Page": "body",  # Page's children become <body> content; see _render_page
    "Container": "div",
    "Heading": "h1",  # level overridden via `level` prop, see _tag_for
    "Text": "p",
    "Button": "button",
    "Link": "a",
    "Image": "img",
    "List": "ul",
    "Item": "li",
    # v0.003: semantic layout.
    "Header": "header",
    "Footer": "footer",
    "Main": "main",
    "Nav": "nav",
    "Section": "section",
    "Article": "article",
    "Aside": "aside",
    "Figure": "figure",
    "FigCaption": "figcaption",
    "Details": "details",
    "Summary": "summary",
    # v0.003: text-level semantics.
    "Strong": "strong",
    "Em": "em",
    "Small": "small",
    "Mark": "mark",
    "Code": "code",
    "Cite": "cite",
    "Abbr": "abbr",
    "Sub": "sub",
    "Sup": "sup",
    "Span": "span",
    "Time": "time",
    "HorizontalRule": "hr",
    "LineBreak": "br",
    "Pre": "pre",
    "Blockquote": "blockquote",
    # v0.003: forms.
    "Form": "form",
    "Input": "input",
    "Textarea": "textarea",
    "Select": "select",
    "Option": "option",
    "OptGroup": "optgroup",
    "Label": "label",
    "FieldSet": "fieldset",
    "Legend": "legend",
    # v0.003: tables.
    "Table": "table",
    "TableHead": "thead",
    "TableBody": "tbody",
    "TableFoot": "tfoot",
    "TableRow": "tr",
    "TableHeaderCell": "th",
    "TableCell": "td",
    "Caption": "caption",
    # v0.003: media.
    "Video": "video",
    "Audio": "audio",
    "Source": "source",
    # v0.003 (second addendum): lists.
    "OrderedList": "ol",
    "DescriptionList": "dl",
    "DescriptionTerm": "dt",
    "DescriptionDetails": "dd",
    # v0.003 (second addendum): responsive images.
    "Picture": "picture",
    "PictureSource": "source",
    # v0.003 (second addendum): native widgets.
    "Progress": "progress",
    "Meter": "meter",
    "Datalist": "datalist",
    "Output": "output",
    # v0.003 (second addendum): dialog.
    "Dialog": "dialog",
    # v0.003 (second addendum): more text-level semantics.
    "Kbd": "kbd",
    "Samp": "samp",
    "Var": "var",
    "Data": "data",
    "Ins": "ins",
    "Del": "del",
    "Q": "q",
    "Dfn": "dfn",
    "Address": "address",
    "Wbr": "wbr",
    "Bdi": "bdi",
    "Bdo": "bdo",
    # v0.003 (second addendum): ruby annotations.
    "Ruby": "ruby",
    "Rt": "rt",
    "Rp": "rp",
    # v0.003 (second addendum): table extras.
    "ColGroup": "colgroup",
    "Col": "col",
    # v0.003 (second addendum): media.
    "Track": "track",
    # v0.003 (second addendum): image maps.
    "Map": "map",
    "Area": "area",
    # v0.003 (second addendum): embeds.
    "IFrame": "iframe",
    # v0.003 (second addendum): no-JS fallback.
    "NoScript": "noscript",
}

# Tags that never have a closing tag / children.
VOID_TAGS = {
    "img", "hr", "br", "input", "source",
    # v0.003 (second addendum).
    "wbr", "col", "area", "track",
}


def _tag_for(node: IRNode) -> str:
    if node.type == "Heading":
        level = node.props.get("level", 1)
        if not isinstance(level, int) or not (1 <= level <= 6):
            level = 1
        return f"h{level}"
    return TAG_MAP.get(node.type, "div")
