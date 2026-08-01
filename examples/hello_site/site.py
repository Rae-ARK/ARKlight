from arklight import *

site = Site()


def nav():
    """A shared nav bar, reused across every page.

    Plain Python function composition like this is how ARKlight expects
    reusable pieces to work today -- no special "component" mechanism
    needed beyond calling other functions (that arrives officially in
    the v0.010 Components milestone, but nothing stops you starting now).
    The current page's nav link is highlighted automatically at runtime
    by the shipped JS -- no wiring needed here."""
    return Container(
        Link("Home", href="/"),
        Link("About", href="/about"),
        class_name="nav",
    )


@site.page("/")
def home():
    return Page(
        nav(),
        Heading("ARKlight"),
        Text("Build websites with Python.", class_name="muted"),
        Container(
            Text("No JavaScript ships to the browser except a tiny, fixed runtime."),
            Text("Just functions -- no templates, no build step."),
            Button(
                "Show details",
                on_click="toggle",
                behavior_target="#more-details",
                toggle_class="hidden",
            ),
            Container(
                Text(
                    "That button uses ARKlight's built-in `toggle` behavior "
                    "-- no JavaScript written by hand, just `on_click='toggle'` "
                    "and `behavior_target='#more-details'` on the button."
                ),
                id="more-details",
                class_name="hidden",
            ),
            class_name="card",
        ),
        title="ARKlight",
    )


@site.page("/about")
def about():
    return Page(
        nav(),
        Heading("About ARKlight", level=2),
        Text("ARKlight compiles Python straight to HTML, CSS, and a tiny JS runtime."),
        Container(
            Text("Every page is a plain Python function that returns a Page(...)."),
            Text("Components are functions. Children are positional. Props are keyword."),
            class_name="card",
        ),

        # v0.003 vocabulary addendum: a short showcase of the extended
        # component set -- semantic layout, a native disclosure widget,
        # a form, and a table, none of which existed before this
        # addendum (still v0.003, not a new version).
        Section(
            Heading("Extended vocabulary", level=3),
            Details(
                Summary("Semantic layout, forms, tables, and media"),
                # Container (not Text) here because it needs to mix
                # plain strings with `Code` nodes -- Text is text-only
                # and can't hold a nested component.
                Container(
                    "This page's ", Code("Section"), " and the ", Code("Details"),
                    "/", Code("Summary"), " pair you're reading right now are both ",
                    "part of the extended vocabulary, styled with zero extra CSS.",
                ),
                Pre(Code("Details(Summary('More'), Text('...'))")),
            ),
            Form(
                Label("Your name", for_="name"),
                Input(type="text", id="name", name="name", placeholder="Ada Lovelace"),
                Button("Subscribe", type="submit"),
                class_name="stack",
            ),
            Table(
                Caption("New component groups"),
                TableHead(
                    TableRow(TableHeaderCell("Group"), TableHeaderCell("Examples")),
                ),
                TableBody(
                    TableRow(TableCell("Layout"), TableCell("Header, Nav, Section, Aside")),
                    TableRow(TableCell("Forms"), TableCell("Form, Input, Select, Label")),
                    TableRow(TableCell("Tables"), TableCell("Table, TableRow, TableCell")),
                ),
            ),
            class_name="stack",
        ),

        Link("Back home", href="/"),
        title="About - ARKlight",
    )
