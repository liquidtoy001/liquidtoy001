"""Render the last 30 days of contributions as light and dark SVG cards.

Reads the public contribution calendar through the GraphQL API, so the numbers
match what any visitor sees on the profile (private work appears only as
counts, and only if "private contributions" is enabled on the profile).
"""
import datetime as dt
import json
import os
import pathlib
import urllib.request

LOGIN = os.environ.get("PROFILE_LOGIN", "liquidtoy001")
DAYS = 30
OUT = pathlib.Path(__file__).resolve().parents[2] / "assets"

THEMES = {
    "light": {"text": "#1f2328", "muted": "#656d76", "bar": "#2da44e", "zero": "#d0d7de"},
    "dark": {"text": "#e6edf3", "muted": "#8d96a0", "bar": "#3fb950", "zero": "#30363d"},
}

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def fetch(token):
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=DAYS - 1)
    body = json.dumps({
        "query": QUERY,
        "variables": {"login": LOGIN, "from": f"{start}T00:00:00Z", "to": f"{today}T23:59:59Z"},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    days = [start + dt.timedelta(days=i) for i in range(DAYS)]
    return [(d, counts.get(d.isoformat(), 0)) for d in days]


def streak(series):
    values = [c for _, c in series]
    # Today is not over yet, so a zero today does not break the streak.
    if values and values[-1] == 0:
        values = values[:-1]
    n = 0
    for c in reversed(values):
        if c == 0:
            break
        n += 1
    return n


def render(series, t):
    w, pad = 400, 4
    total = sum(c for _, c in series)
    week = sum(c for _, c in series[-7:])
    active = sum(1 for _, c in series if c)
    peak = max((c for _, c in series), default=0) or 1

    chart_top, chart_h = 118, 68
    pitch = (w - 2 * pad) / len(series)
    bar_w = pitch * 0.68
    bars = []
    for i, (day, c) in enumerate(series):
        x = pad + i * pitch + (pitch - bar_w) / 2
        h = max(c / peak * chart_h, 2.5)
        fill = t["bar"] if c else t["zero"]
        label = f"{day:%b} {day.day}: {c} contribution{'s' if c != 1 else ''}"
        bars.append(
            f'<rect x="{x:.2f}" y="{chart_top + chart_h - h:.2f}" width="{bar_w:.2f}" '
            f'height="{h:.2f}" rx="1.5" fill="{fill}"><title>{label}</title></rect>'
        )

    first, last = series[0][0], series[-1][0]
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="214" viewBox="0 0 {w} 214" role="img" aria-label="{total} contributions in the last {DAYS} days">
<g font-family="{font}">
<text x="{pad}" y="22" font-size="11" letter-spacing="1.2" fill="{t['muted']}">RECENT ACTIVITY</text>
<text x="{w - pad}" y="22" font-size="11" text-anchor="end" fill="{t['muted']}">last {DAYS} days</text>
<text x="{pad}" y="68" fill="{t['text']}"><tspan font-size="40" font-weight="600">{total}</tspan><tspan dx="8" font-size="14" fill="{t['muted']}">contributions</tspan></text>
<text x="{pad}" y="96" font-size="12" fill="{t['muted']}"><tspan fill="{t['text']}" font-weight="600">{week}</tspan> this week  ·  <tspan fill="{t['text']}" font-weight="600">{streak(series)}</tspan>-day streak  ·  active <tspan fill="{t['text']}" font-weight="600">{active}</tspan>/{DAYS} days</text>
{chr(10).join(bars)}
<text x="{pad}" y="206" font-size="10" fill="{t['muted']}">{first:%b} {first.day}</text>
<text x="{w - pad}" y="206" font-size="10" text-anchor="end" fill="{t['muted']}">{last:%b} {last.day}</text>
</g>
</svg>
"""


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    series = fetch(token)
    OUT.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"activity-{name}.svg").write_text(render(series, theme), encoding="utf-8", newline="\n")
    print(f"{sum(c for _, c in series)} contributions over {DAYS} days")


if __name__ == "__main__":
    main()
