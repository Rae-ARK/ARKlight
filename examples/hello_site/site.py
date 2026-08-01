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
        Link("Back home", href="/"),
        title="About - ARKlight",
    )
