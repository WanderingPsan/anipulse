"""One chart style for the whole dashboard.

Every chart uses the same few colors so the pages look like one product. The rule: the
bar or point that the chart's title talks about is the accent blue, and everything else is
a muted gray. A reader's eye goes straight to the thing the title claims.

The colors come from a colorblind-checked palette: blue and orange stay far apart for the
common kinds of color blindness, and the gray has no hue, so it never competes.
"""

import plotly.graph_objects as go

ACCENT = "#2a78d6"  # the highlighted mark, and the theme's primary color
SECOND = "#eb6834"  # the second series, when a chart compares exactly two
MUTED = "#c3c2b7"  # context marks
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3de"
SURFACE = "#fcfcfb"


def highlight_colors(labels: list[str], highlight: str | list[str]) -> list[str]:
    """One color per label: accent for the highlighted label(s), muted for the rest."""
    chosen = {highlight} if isinstance(highlight, str) else set(highlight)
    return [ACCENT if label in chosen else MUTED for label in labels]


def style_figure(fig: go.Figure, title: str, height: int = 380) -> go.Figure:
    """Apply the shared look: takeaway title, quiet grid, no chart junk."""
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 16, "color": TEXT}},
        height=height,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"color": TEXT_SECONDARY},
        showlegend=False,
        hoverlabel={"bgcolor": "white"},
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig
