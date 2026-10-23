"""Visual charter (see .claude/skills/road-safety-viz/SKILL.md): colour tokens, Plotly template, helpers.

Sections never hard-code a colour: they import it from here.
"""
import plotly.graph_objects as go
import plotly.io as pio

COLORS = {
    "background": "#0e1116",
    "surface": "#14171c",
    "text": "#e8eaed",
    "text_secondary": "#a7adb7",
    "grid": "#262b33",
    "axis": "#3a404a",
    "killed": "#e5484d",       # deaths / key figures only, never a road-user category
    "highlight": "#f5c518",    # annotations and the selected département: text or thin marks only
    "reference": "#8b93a1",    # national value when a département is selected
    "muted": "#5b616b",        # "Other" / "Unknown", and the muted part of highlight-and-mute charts
    "map_border": "#2a2f38",
    "seniors": "#e8eaed",      # "aged 65+" series in the trend chart: light neutral, not a road-user hue
}
TRANSPARENT = "rgba(0,0,0,0)"  # outline-only marks (national reference bars, selected département)

# Fixed road-user colours: the colour follows the category in every chart, whatever the filters
MODE_COLORS = {
    "Pedestrian": "#c98500",
    "Bicycle": "#199e70",
    "E-scooter / PMD": "#9085e9",
    "Powered two-wheeler": "#d95926",
    "Car / van": "#3987e5",
    "Heavy vehicle / bus": "#d55181",
    "Other": COLORS["muted"],
    "Unknown": COLORS["muted"],
}
MODE_ORDER = list(MODE_COLORS)

# Single-hue sequential scale (dark -> bright = more dangerous) for the choropleth and heatmaps
SEQ_RED = ["#3a1d20", "#5e2427", "#8a2c2e", "#b83536", "#e5484d", "#f27a75", "#f9b0aa"]

NATIONAL_LABEL = "France (metro.)"
PLOTLY_CONFIG = {"displayModeBar": False}   # maps keep the default mode bar (zoom / reset)

# Small-number rule: no rate shown below these thresholds
MIN_PEOPLE, MIN_KILLED = 30, 10

_axis = dict(gridcolor=COLORS["grid"], linecolor=COLORS["axis"], zeroline=False,
             title_font=dict(color=COLORS["text_secondary"]))
pio.templates["roadsafety"] = go.layout.Template(layout=dict(
    paper_bgcolor=COLORS["surface"], plot_bgcolor=COLORS["surface"],
    font=dict(color=COLORS["text"], size=14), title=dict(font=dict(size=18)),
    colorway=[c for m, c in MODE_COLORS.items() if m not in ("Other", "Unknown")],
    xaxis=_axis, yaxis=_axis,
    hoverlabel=dict(bgcolor=COLORS["background"], bordercolor=COLORS["axis"], font=dict(color=COLORS["text"])),
    legend=dict(orientation="h", y=1.08, x=0, title_text=""),
    margin=dict(l=10, r=10, t=50, b=10),
))
pio.templates.default = "roadsafety"


# ---------- Helpers ----------

def enough_data(people: int, killed: int) -> bool:
    """True if a rate can be shown under the small-number rule."""
    return people >= MIN_PEOPLE and killed >= MIN_KILLED


def kicker(label: str) -> None:
    """Small uppercase label above a section headline (WHERE, WHO, WHEN...), for article-like navigation."""
    import streamlit as st   # local import: the rest of this module does not depend on Streamlit
    st.markdown(f"<div style='color:{COLORS['text_secondary']};font-size:.8rem;letter-spacing:.12em;"
                f"margin-top:2.5rem'>{label.upper()}</div>", unsafe_allow_html=True)


def fmt_int(n: float) -> str:
    """Thousands separator: 3167 -> '3,167'."""
    return f"{n:,.0f}"


def apply_layout(fig: go.Figure, x_title: str, y_title: str, height: int | None = None) -> go.Figure:
    """Axis titles (with units) on every chart, optional fixed height."""
    fig.update_layout(xaxis_title=x_title, yaxis_title=y_title)
    if height:
        fig.update_layout(height=height)
    return fig


def add_reference_line(fig: go.Figure, value: float, axis: str = "x", label: str = NATIONAL_LABEL) -> go.Figure:
    """Dashed grey line for the national value (axis="x": vertical line, axis="y": horizontal line)."""
    style = dict(line_dash="dash", line_color=COLORS["reference"], line_width=1.5,
                 annotation_text=label, annotation_font_color=COLORS["reference"])
    return fig.add_vline(x=value, **style) if axis == "x" else fig.add_hline(y=value, **style)


def annotate(fig: go.Figure, x, y, text: str, **kwargs) -> go.Figure:
    """Yellow callout with a thin arrow, for the one point a chart is about (kwargs: ax, ay, xanchor...)."""
    return fig.add_annotation(x=x, y=y, text=text, showarrow=True, arrowhead=2, arrowwidth=1,
                              arrowcolor=COLORS["highlight"], font=dict(color=COLORS["highlight"]), **kwargs)
