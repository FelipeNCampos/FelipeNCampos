"""Collect publicly visible GitHub data and render a self-contained SVG dashboard."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USERNAME = "FelipeNCampos"
SAO_PAULO = timezone(timedelta(hours=-3))  # Current São Paulo offset; recent events only.
COLORS = ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"]
LANGUAGE_COLORS = {"Python": "#3572a5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
                   "HTML": "#e34c26", "CSS": "#a78bfa", "Go": "#00add8", "SCSS": "#c6538c"}


def request(url):
    headers = {"User-Agent": f"{USERNAME}-profile-metrics", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=45) as response:
        return response.read().decode("utf-8")


def api(path):
    return json.loads(request(f"https://api.github.com{path}"))


def pages(path, limit=None):
    result = []
    page = 1
    while limit is None or page <= limit:
        batch = api(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        result.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return result


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells, self.tips = {}, {}
        self.tip = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.cells[attrs["id"]] = {"date": attrs["data-date"], "level": int(attrs["data-level"])}
        if tag == "tool-tip":
            self.tip = attrs.get("for")
            self.tips[self.tip] = ""

    def handle_data(self, data):
        if self.tip is not None:
            self.tips[self.tip] += data

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.tip = None


def parse_calendar(html):
    parser = CalendarParser()
    parser.feed(html)
    if not parser.cells:
        raise ValueError("GitHub contribution calendar not found; keeping previous dashboard.")
    days = []
    for cell_id, cell in parser.cells.items():
        match = re.match(r"^(No|[\d,]+) contributions?\b", parser.tips.get(cell_id, "").strip())
        if not match:
            raise ValueError(f"Unknown contribution tooltip for {cell['date']}")
        days.append({**cell, "count": 0 if match[1] == "No" else int(match[1].replace(",", ""))})
    return sorted(days, key=lambda day: day["date"])


def collect():
    profile = api(f"/users/{USERNAME}")
    repos = pages(f"/users/{USERNAME}/repos?type=owner")
    records = []
    for repo in repos:
        records.append({"name": repo["name"], "fork": repo["fork"], "private": repo["private"],
                        "stars": repo["stargazers_count"], "forks": repo["forks_count"],
                        "languages": {} if repo["fork"] else api(f"/repos/{USERNAME}/{repo['name']}/languages")})
    events = pages(f"/users/{USERNAME}/events/public", limit=3)
    days = parse_calendar(request(f"https://github.com/users/{USERNAME}/contributions"))
    dates = [date.fromisoformat(day["date"]) for day in days]
    if len(dates) < 360 or any(b - a != timedelta(days=1) for a, b in zip(dates, dates[1:])):
        raise ValueError("Incomplete contribution calendar; keeping previous dashboard.")
    return {"collected_at": datetime.now(timezone.utc).isoformat(), "username": USERNAME,
            "profile": {key: profile[key] for key in ("name", "followers", "following")},
            "repos": records, "events": [{key: event[key] for key in ("id", "type", "created_at")}
                                         for event in events], "days": days}


def aggregate(data):
    originals = [repo for repo in data["repos"] if not repo["fork"] and not repo.get("private", False)]
    languages = Counter()
    for repo in originals:
        languages.update(repo["languages"])
    hours, weekdays = [0] * 24, [0] * 7
    for event in data["events"]:
        if event["type"] == "PushEvent":
            local = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).astimezone(SAO_PAULO)
            hours[local.hour] += 1
    for day in data["days"]:
        weekdays[(date.fromisoformat(day["date"]).weekday() + 1) % 7] += day["count"]
    return {"languages": languages.most_common(), "hours": hours, "weekdays": weekdays,
            "contributions": sum(day["count"] for day in data["days"]),
            "active_days": sum(day["count"] > 0 for day in data["days"]),
            "stars": sum(repo["stars"] for repo in originals),
            "forks": sum(repo["forks"] for repo in originals), "originals": len(originals)}


def text(x, y, value, size=14, color="#e6edf3", weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')


def rect(x, y, width, height, fill, radius=4):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" rx="{radius}" fill="{fill}"/>'


def bars(values, labels, x, baseline, width, height, color):
    result = []
    step = width / len(values)
    for index, (value, label) in enumerate(zip(values, labels)):
        h = height * value / max(max(values), 1)
        bx = x + index * step
        result.append(rect(bx, baseline - max(h, 2), step * .55, max(h, 2), color if value else "#30363d"))
        if value and len(values) < 10:
            result.append(text(bx + step * .275, baseline - h - 8, value, 12, "#8b949e", anchor="middle"))
        if label:
            result.append(text(bx + step * .275, baseline + 23, label, 12, "#8b949e", anchor="middle"))
    return "".join(result)


def render(data):
    stats = aggregate(data)
    days = data["days"]
    start, end = days[0]["date"], days[-1]["date"]
    updated = datetime.fromisoformat(data["collected_at"].replace("Z", "+00:00")).astimezone(SAO_PAULO)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="940" viewBox="0 0 1080 940" '
             'role="img" aria-labelledby="title description">',
             '<title id="title">Felipe Nunes Campos — atividade no GitHub</title>',
             '<desc id="description">Contribuições, calendário isométrico, pushes por hora, contribuições '
             'por dia da semana e distribuição de linguagens em bytes. Fontes e limites no README e em data.json.</desc>',
             rect(0, 0, 1080, 940, "#0d1117", 14),
             '<g font-family="Segoe UI,Arial,sans-serif">',
             text(32, 46, data["profile"].get("name") or data["username"], 27, "#58a6ff", 650),
             text(32, 73, f'@{data["username"]} · Python, automação e desenvolvimento web', 14, "#8b949e"),
             text(1048, 43, "GITHUB / VISÃO GERAL", 12, "#8b949e", 600, "end"),
             '<path d="M32 96H1048" stroke="#30363d"/>']
    for x, value, label in [(32, stats["contributions"], "contribuições no calendário"),
                             (292, len(data["repos"]), "repositórios públicos"),
                             (552, stats["active_days"], "dias com contribuições"),
                             (812, data["profile"]["followers"], "seguidores")]:
        parts += [text(x, 140, f"{value:,}".replace(",", "."), 30, "#e6edf3", 650),
                  text(x, 167, label, 13, "#8b949e")]
    parts += [text(32, 198, f"{start} a {end} · {stats['originals']} originais · "
                   f"{stats['stars']} estrelas e {stats['forks']} forks recebidos nos originais", 12, "#8b949e"),
              '<path d="M32 220H1048 M530 245V880" stroke="#30363d"/>',
              text(32, 260, "Ritmo de atividade", 20, "#58a6ff", 600),
              text(32, 287, "Eventos públicos de push por hora · São Paulo (UTC−3)", 13, "#8b949e")]
    event_dates = sorted(event["created_at"][:10] for event in data["events"])
    sample = f"Amostra: {sum(stats['hours'])} pushes / {len(data['events'])} eventos"
    parts.append(text(32, 309, sample, 12, "#8b949e"))
    if event_dates:
        parts.append(text(32, 330, f"Eventos (UTC): {event_dates[0]} a {event_dates[-1]}", 11, "#8b949e"))
    parts.append(bars(stats["hours"], [f"{i:02}" if i % 3 == 0 else "" for i in range(24)], 36, 434, 454, 80, "#39d353"))
    if not sum(stats["hours"]):
        parts.append(text(32, 385, "Sem eventos de push na amostra", 13, "#8b949e"))
    parts += [text(32, 508, "Contribuições por dia da semana", 15, "#e6edf3", 600),
              bars(stats["weekdays"], ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"], 42, 660, 454, 106, "#26a641"),
              text(32, 734, "Tecnologias em projetos", 20, "#58a6ff", 600)]
    for index, label in enumerate(["Python", "FastAPI", "PostgreSQL", "Docker", "React", "TypeScript", "Playwright", "Git"]):
        x, y = 32 + (index % 4) * 121, 758 + (index // 4) * 39
        parts += [rect(x, y, 111, 29, "#161b22"), text(x + 10, y + 20, label, 12)]
    parts += [text(32, 859, "Ferramentas utilizadas; sem classificação de domínio.", 12, "#8b949e"),
              text(562, 260, "Calendário de contribuições", 20, "#58a6ff", 600),
              text(562, 287, "Visão isométrica · altura proporcional à contagem", 13, "#8b949e")]
    first = date.fromisoformat(start)
    offset = (first.weekday() + 1) % 7
    maximum = max(day["count"] for day in days)
    for index, day in enumerate(days):
        week, weekday = divmod(index + offset, 7)
        x, y = 615 + week * 7.2 - weekday * 8, 347 + week * 2.5 + weekday * 5
        h = 54 * math.sqrt(day["count"] / max(maximum, 1))
        color = COLORS[day["level"]]
        tip = f"{day['date']}: {day['count']} contribuições"
        if h:
            parts += [f'<path d="M{x-7:.1f},{y:.1f}v{-h:.1f}l7,3v{h:.1f}z" fill="#0e4429"/>',
                      f'<path d="M{x:.1f},{y+3:.1f}v{-h:.1f}l7,-3v{h:.1f}z" fill="#006d32"/>']
        parts.append(f'<polygon points="{x:.1f},{y-h-3:.1f} {x+7:.1f},{y-h:.1f} '
                     f'{x:.1f},{y-h+3:.1f} {x-7:.1f},{y-h:.1f}" fill="{color}"><title>{tip}</title></polygon>')
    parts += [text(562, 541, "Menos", 12, "#8b949e"), text(741, 541, "Mais", 12, "#8b949e")]
    for i, color in enumerate(COLORS):
        parts.append(rect(612 + i * 23, 529, 17, 13, color, 2))
    parts += [text(562, 570, "Contagens visíveis; podem incluir atividade privada anônima.", 12, "#8b949e"),
              text(562, 620, "Linguagens nos repositórios", 20, "#58a6ff", 600),
              text(562, 647, "Bytes de código · repositórios próprios, excluindo forks", 13, "#8b949e")]
    languages = stats["languages"]
    if not languages:
        parts.append(text(562, 700, "Sem linguagens disponíveis", 14, "#8b949e"))
    else:
        rows = languages[:5]
        if len(languages) > 5:
            rows.append(("Outras", sum(value for _, value in languages[5:])))
        total = sum(value for _, value in languages)
        for index, (name, value) in enumerate(rows):
            y = 681 + index * 34
            share = value / total
            parts += [text(562, y, name, 13), rect(667, y - 11, 300, 10, "#21262d"),
                      rect(667, y - 11, 300 * share, 10, LANGUAGE_COLORS.get(name, "#8b949e")),
                      text(1048, y, f"{share:.1%}", 13, "#8b949e", anchor="end")]
    parts += ['<path d="M32 891H1048" stroke="#30363d"/>',
              text(32, 918, f"Atualizado em {updated:%d/%m/%Y %H:%M} · São Paulo", 12, "#8b949e"),
              text(1048, 918, "Fontes e metodologia no README", 12, "#8b949e", anchor="end"), '</g></svg>']
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Render a saved snapshot without network access")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8")) if args.input else collect()
    svg = render(data)  # Finish collection and rendering before replacing the last successful snapshot.
    output = ROOT / "assets" / "metrics"
    output.mkdir(parents=True, exist_ok=True)
    (output / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "dashboard.svg").write_text(svg + "\n", encoding="utf-8")
    print(f"Generated dashboard for {data['username']}: {aggregate(data)['contributions']} contributions")


if __name__ == "__main__":
    main()
