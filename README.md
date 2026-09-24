

<div align="center">

# paddock-api

**F1 data, shaped for a dashboard - not a spreadsheet.**

[Drumandbytes Projects](https://drumandbytes.com/projects/)

![README](https://img.shields.io/badge/Actively%20Maintained-Green)
![README](https://img.shields.io/github/v/release/drumandbytes/paddock-api)
![README](https://img.shields.io/github/issues/drumandbytes/paddock-api)
![README](https://img.shields.io/github/commit-activity/w/drumandbytes/paddock-api)
![README](https://img.shields.io/github/commits-since/drumandbytes/paddock-api/latest)

___

<h3>

[Why This Exists](#why-this-exists) • [What It Does](#what-it-does) • [How It's Built](#how-its-built)
<br>
[Getting Started](#getting-started) • [API Reference](#api-reference) • [Development](#development) • [Demo](#demo)

</h3>

</div>

# Why This Exists
I run [Glance](https://github.com/glanceapp/glance) on a home server, and I wanted an F1 corner of it that felt like it belonged there - local time, a track map before I've even had coffee on qualifying day, team names short enough to fit a dashboard tile instead of "Mercedes-AMG Petronas Formula One Team." The community's [F1 widget](https://github.com/glanceapp/community-widgets/blob/main/widgets/formula1-widgets-by-abaza738/README.md) got the styling right, but the API behind it was built for a generic consumer, not a self-hosted dashboard: everything in UTC, no caching (so every widget refresh meant a slow round-trip), and just enough detail to be a bit unsatisfying for a Friday-night "what's happening this weekend" glance.

So this exists to be the API I actually wanted underneath those widgets - same look, an engine built for exactly one job.

# What It Does
Point it at a race weekend and it tells you what's actually useful to know: when the next session is, in your own timezone, counting down to whichever one you care about. It knows who's leading the championship and by how much, cleaned up to team names that fit a phone screen. It'll draw you the track before a single lap has been driven there. And once a session's actually happened, it'll tell you what tyres everyone was on and for how long - not the fantasy of who's got how many sets left, just what's real.

Everything is cached deliberately, not by default TTL - a session's data doesn't change until the next session starts, so that's when the cache actually expires, not some arbitrary five minutes later.

# How It's Built
It's a small Go service (Echo), and the interesting decisions are mostly about *where the data comes from* and *when it's actually fetched*.

Schedules, standings, and race results come from the [Jolpica](https://github.com/jolpica/jolpica-f1) Ergast-compatible mirror; tyre stint data comes from [OpenF1](https://openf1.org/). Both are free, but F1's live-timing backend behind them has a real rate ceiling, and it's shared - burn through it chasing something that isn't there, and every other endpoint on the same network starves too. So the rule here is: only ever ask for a session that's actually happened, and never guess. An in-memory cache, keyed to when the underlying data can actually change (not a fixed TTL), keeps most requests from hitting upstream at all.

OpenF1's free tier is locked out entirely (past sessions included) for a stretch around every live session, so once a session has finished its results are treated as immutable and kept for good - in memory, and on disk under `CACHE_DIR` if a volume is mounted there, so a restart during a lockout doesn't blank them. Anything else that never changes once it exists can use the same store.

Track maps break that pattern entirely, on purpose. Tracing a circuit's outline from a car's GPS telemetry only works once a car has actually driven it - which is useless for a brand-new venue's debut weekend, and turned out to be the single most fragile part of this whole service. It's replaced now with [bacinger/f1-circuits](https://github.com/bacinger/f1-circuits), a maintained dataset of real circuit geometry that doesn't care whether a session has happened yet. No live API call, no rate limit, works for a track that's never hosted a race.

# Getting Started
Runs as a single container - `docker compose` is the easiest way in.

```yaml
services:
  paddock-api:
    container_name: paddock-api
    image: ghcr.io/drumandbytes/paddock-api:latest
    environment:
      - TIMEZONE=America/Edmonton # Specify your timezone.
      - TRACK_COLOUR=#e5d486 # Specify desired track map color
      - EVENT_DETAIL=main # Optional. main tracks qualis and races (inc. sprints), race tracks races. 
    volumes:
      - paddock-cache:/data # Optional. Keeps finished-session data across restarts.
    ports:
      - 4463:4463
    restart: unless-stopped

volumes:
  paddock-cache:
```

| Variable | Required | Description |
|---|---|---|
| `TIMEZONE` | Yes | IANA timezone name (e.g. `America/Edmonton`, `Europe/Tallinn`) - every timestamp the API returns is converted to this. |
| `TRACK_COLOUR` | Yes | Hex colour (e.g. `#e5d486`) for the track-map line. |
| `EVENT_DETAIL` | No, defaults to `main` | Which sessions `/f1/next_race/` counts down to: `main` (quali + races, skips practice), `race` (races only), or `detailed` (every session). |
| `CACHE_DIR` | No, defaults to `/data` in the image | Where finished-session data is kept so it survives restarts. Mount a volume there (as above); without one it still works, it just doesn't outlive the container. Runs as UID 65532, so a bind mount or Kubernetes volume needs to be writable by it. |

Once it's running, grab the widgets you want from [`widgets/`](./widgets/) and drop them into your Glance config - see that folder's own README for setup and what each one shows. See the [Glance docs](https://github.com/glanceapp/glance/blob/main/docs/configuration.md#including-other-config-files) for how config files like these get included.

# API Reference
Everything returns JSON except the track map, which is an SVG image.

| Endpoint | Description |
|---|---|
| `GET /f1/next_race/` | The next (or currently in-progress) race weekend - full session schedule in your `TIMEZONE`, counting down to the next session per `EVENT_DETAIL`. |
| `GET /f1/last_race/` | Full classification for the most recently completed race. |
| `GET /f1/drivers_standings/` | Drivers' championship standings, simplified team names, nationality flags. |
| `GET /f1/constructors_standings/` | Constructors' championship standings, simplified team names, nationality flags. |
| `GET /f1/next_map/` | Track map for the next race's circuit. |
| `GET /f1/tyre_usage/` | Per-driver compound and stint length for each session of the current weekend that's happened so far (FP1 through Race). Usage only, not allocation - there's no structured source anywhere for a driver's pre-weekend tyre-compound allocation, so this only reports what was actually used once a session's run. Stays on the latest weekend until the next one's first session starts, and keeps finished sessions in memory since OpenF1's free tier locks out all access while any session is live. |
| `GET /f1/latest_session/` | Classification of the most recently finished non-race session of the current weekend (practice, sprint qualifying, qualifying or sprint) - best lap for the leader, gap for everyone else. The Grand Prix itself is `/f1/last_race/`. Sourced from OpenF1, so it shares its live-session lockout (finished sessions are kept in memory once fetched). |

# Development
Requires Go 1.26+.

```sh
go test ./...
```

`docker compose up --build` runs the whole thing locally the way it runs in production.

Four workflows keep this repo honest: [`ci.yml`](./.github/workflows/ci.yml) runs the test suite and a Docker build on every push and PR; [`regenerate-track-maps.yml`](./.github/workflows/regenerate-track-maps.yml) re-renders every circuit's map monthly (or on demand) via [`cmd/gentrackmaps`](./cmd/gentrackmaps) and opens a PR if anything actually changed; [`release-please.yml`](./.github/workflows/release-please.yml) turns Conventional Commits into a version-bump PR, and merging it tags a release, which [`publish.yml`](./.github/workflows/publish.yml) picks up and builds/pushes to GHCR.

# Demo
<table>
<tr>
<td width="35%" align="center">
  <img src="./docs/demo/paddock-api.png" width="100%" />
</td>
<td width="65%" valign="top">

Same widget styling as the community integration it's built on - the difference is everything underneath it:

- Session times in your own timezone, not UTC
- A track map, drawn before qualifying even happens - even for a circuit that's never hosted a race
- Team names simplified to fit a dashboard tile, not "Mercedes-AMG Petronas Formula One Team"
- Tyre compound and stint length per session, once a race weekend is underway
- Results for the latest practice, qualifying or sprint session, separate from the race
- Smart caching keyed to when the data can actually change, not a fixed TTL

</td>
</tr>
</table>

# Project Structure
```
paddock-api/
├── main.go            # App wiring: config, HTTP client, cache, server setup
├── cache.go           # In-memory TTL cache
├── standings.go       # /f1/drivers_standings, /f1/constructors_standings
├── race.go            # /f1/last_race, /f1/next_race, schedule fetch/parsing
├── tyres.go           # /f1/tyre_usage
├── map.go             # /f1/next_map (serves static SVG, falls back to live render)
├── main_test.go
├── go.mod / go.sum
├── Dockerfile          # Container build instructions
├── static/track_maps/  # Pre-rendered SVGs, served directly when present
├── internal/trackmap/  # Circuit geometry fetch + SVG rendering (shared below)
├── cmd/gentrackmaps/   # Offline pre-renderer for static/track_maps/ (GHA only)
├── widgets/            # Glance widget YAMLs, one folder per widget
├── docs/demo/          # README screenshots
├── .github/
│   ├── workflows/       # CI, track-map regeneration, release, publish, auto-merge
│   └── dependabot.yml
├── LICENSE
└── docker-compose.yaml # Local development compose file
```

# License
MIT - see [LICENSE](./LICENSE).
