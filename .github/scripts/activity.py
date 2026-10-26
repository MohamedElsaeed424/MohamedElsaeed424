"""Draws the Activity card of the profile README from the GitHub contribution calendar, in a light and a dark file.

Runs in GitHub Actions (.github/workflows/profile-assets.yml):  python3 .github/scripts/activity.py <out dir>
The palettes and fonts come from profile.json next to this file, written by the LinkedIn planner.
Written by the LinkedIn planner from templates/github/activity.py: edit it there, not here. Standard library only.
"""

import datetime as dt
import html
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date contributionCount contributionLevel } } } } } }"""
LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
HEAT = {"dark": ["#12282e", "#0f4c50", "#0e7c86", "#18a9a3", "#45d3c7"],
        "light": ["#ebe6da", "#bfe3e1", "#7cc9c4", "#18a9a3", "#0e7c86"]}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def calendar(login: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-assets"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("errors"):
        sys.exit(f"GitHub GraphQL errors: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def stats(cal: dict) -> dict:
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"], d["contributionLevel"])
            for w in cal["weeks"] for d in w["contributionDays"]]
    longest = run = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    for i, (_, count, _) in enumerate(reversed(days)):
        if count:
            current += 1
        elif i:  # today without a contribution yet does not end the streak
            break
    by_day = [0] * 7
    for day, count, _ in days:
        by_day[day.weekday()] += count
    return {"total": cal["totalContributions"], "active": sum(1 for _, c, _ in days if c), "current": current,
            "best": max((c for _, c, _ in days), default=0),
            "longest": longest, "busiest": WEEKDAYS[by_day.index(max(by_day))] if any(by_day) else "", "weeks": cal["weeks"]}


def text(x, y, s, font, size, fill, anchor="start", ls=0):
    extra = (f' text-anchor="{anchor}"' if anchor != "start" else "") + (f' letter-spacing="{ls}"' if ls else "")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font},Segoe UI,Arial,sans-serif" font-weight="{font[2:]}" '
            f'font-size="{size}" fill="{fill}"{extra}>{html.escape(str(s))}</text>')


def card(st: dict, t: dict, theme: str, fonts: dict, today: dt.date) -> str:
    W, H = 1000, 250
    out = []
    faces = "".join(f"@font-face{{font-family:{k};src:url(data:font/woff2;base64,{fonts[k]}) format('woff2')}}" for k in ("SG700", "IN500", "IN400"))
    css = (faces + "text{font-kerning:none}.c{animation:in .5s ease-out both}.up{animation:up .8s cubic-bezier(.2,.7,.2,1) both}"
           "@keyframes in{from{opacity:0}to{opacity:1}}@keyframes up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
           ".g{animation:drift 16s ease-in-out infinite alternate}@keyframes drift{to{transform:translate(-40px,20px)}}"
           "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
    out.append(f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg0"]}"/><stop offset="1" stop-color="{t["bg1"]}"/></linearGradient>'
               f'<radialGradient id="gl"><stop offset="0" stop-color="{t["teal2"]}" stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["teal2"]}" stop-opacity="0"/></radialGradient>'
               f'<clipPath id="cl"><rect width="{W}" height="{H}" rx="22"/></clipPath></defs>'
               f'<g clip-path="url(#cl)"><rect width="{W}" height="{H}" fill="url(#bg)"/><g class="g"><circle cx="{W}" cy="0" r="420" fill="url(#gl)"/></g></g>'
               f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="22" fill="none" stroke="{t["line"]}"/>')
    out.append(text(36, 48, "CONTRIBUTIONS · LAST 12 MONTHS", "SG700", 13, t["teal"], ls=2.6))
    out.append(text(W - 36, 48, f"Refreshed {today:%d %b %Y}", "IN500", 12.5, t["muted"], anchor="end"))
    third = (f"{st['current']}", "day streak now") if st["current"] >= 2 else (f"{st['best']}", "best day")
    blocks = [(f"{st['total']:,}", "contributions"), (f"{st['active']}", "active days"), third, (f"{st['longest']}", "longest streak")]
    for i, (value, label) in enumerate(blocks):
        x, y = 36 + (i % 2) * 112, 104 + (i // 2) * 74
        out.append(f'<g class="up" style="animation-delay:{i * .1:.1f}s">{text(x, y, value, "SG700", 30, t["text"])}'
                   f'{text(x, y + 21, label, "IN500", 12.5, t["muted"])}</g>')
    x0, y0, step, cell = 268, 82, 13.2, 10.4
    month = None
    for c, week in enumerate(st["weeks"]):
        first = dt.date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != month and c < len(st["weeks"]) - 2:
            if month is not None or first.day <= 7:
                out.append(text(x0 + c * step, y0 - 8, f"{first:%b}", "IN500", 11, t["muted"]))
            month = first.month
        for day in week["contributionDays"]:
            r = (dt.date.fromisoformat(day["date"]).weekday() + 1) % 7  # Sunday on top, like GitHub
            level = LEVELS.index(day["contributionLevel"]) if day["contributionLevel"] in LEVELS else 0
            out.append(f'<rect class="c" style="animation-delay:{.2 + c * .018:.3f}s" x="{x0 + c * step:.1f}" y="{y0 + r * step:.1f}" '
                       f'width="{cell}" height="{cell}" rx="2.6" fill="{HEAT[theme][level]}"/>')
    ly = y0 + 7 * step + 26
    if st["busiest"]:
        out.append(text(x0, ly + 9, f"Most active on {st['busiest']}s", "IN500", 12.5, t["text2"]))
    lx = W - 36 - 5 * 15 - 34
    out.append(text(lx - 8, ly + 9, "Less", "IN400", 11.5, t["muted"], anchor="end"))
    for i, color in enumerate(HEAT[theme]):
        out.append(f'<rect x="{lx + i * 15:.1f}" y="{ly}" width="{cell}" height="{cell}" rx="2.6" fill="{color}"/>')
    out.append(text(lx + 5 * 15 + 4, ly + 9, "More", "IN400", 11.5, t["muted"]))
    label = f"GitHub contributions in the last 12 months: {st['total']}, current streak {st['current']} days, longest {st['longest']} days"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}">'
            f"<title>{html.escape(label)}</title><style>{css}</style>{''.join(out)}</svg>")


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = json.loads((HERE / "profile.json").read_text(encoding="utf-8"))
    login = os.environ.get("GITHUB_REPOSITORY_OWNER") or profile["login"]
    st = stats(calendar(login, os.environ["GITHUB_TOKEN"]))
    today = dt.datetime.now(dt.timezone.utc).date()
    for theme in ("light", "dark"):
        (out_dir / f"activity-{theme}.svg").write_text(card(st, profile["themes"][theme], theme, profile["fonts"], today), encoding="utf-8")
    print(f"{login}: {st['total']} contributions, streak {st['current']}, longest {st['longest']}")


if __name__ == "__main__":
    main()
