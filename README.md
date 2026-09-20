

<div align="center">
  
# The F1 Season... At A Glance

![README](https://img.shields.io/badge/Actively%20Maintained-Green)
![README](https://img.shields.io/github/v/release/drumandbytes/paddock-api)
![README](https://img.shields.io/docker/pulls/drumandbytes/paddock-api)
![README](https://img.shields.io/github/issues/drumandbytes/paddock-api)


![README](https://img.shields.io/github/commit-activity/w/drumandbytes/paddock-api)
![README](https://img.shields.io/github/commits-since/drumandbytes/paddock-api/latest)

___

<h3>

[Background](#background) • [Why Use This Repo?](#why-use-this-repo) • [Solution](#solution)
<br>
[Installation](#installation) • [API Reference](#api-reference) • [Development](#development) • [Demo](#demo)

</h3>

</div>

# Background
I host [glance](https://github.com/glanceapp/glance) on one of my home servers. As a big F1 fan, I was excited to see that the community had added a [F1 integration](https://github.com/glanceapp/community-widgets/blob/main/widgets/formula1-widgets-by-abaza738/README.md), but was disappointed with the rigidity of the API it uses.

# Why Use this Repo?
I ran into the following issues with the API that this repository solves:

1. Times were shown in UTC, not specific to a users timezone.
2. API calls were slow and there was no smart caching, slowing down my Glance.
3. Lack of control over data fields like team name. It shows lengthy official team names like "Mercedes AMG Petronas F1 Team" instead of just "Mercedes"
4. Lacking detail. For instance, I wanted a track map, and previous race results when it displayed the next race.
5. Lack of dynamic control over event time. While you can select what event to have a countdown to (IE race vs. qualifying), you have to manually specify this instead of using time analysis to show the next event that hasn't passed.

# Solution
## APIs
As a solution, I built a small FastAPI service that gives me full control over what I fetch and how it's cached. Every endpoint uses smart caching so it only refreshes after the underlying data can actually have changed (e.g. once a session starts, or a few hours after a race finishes), keeping Glance fast without hammering upstream data sources.

Data comes from [FastF1](https://github.com/theOehrly/Fast-F1) (schedules, lap/tyre data) and its bundled [Ergast/Jolpica](https://github.com/jolpica/jolpica-f1) mirror (standings, results) - see [API Reference](#api-reference) for the full endpoint list. Track maps are the one exception: they're drawn from [bacinger/f1-circuits](https://github.com/bacinger/f1-circuits)' static circuit geometry instead of session telemetry, so they work even for a circuit that's never hosted a session (a brand-new venue's debut weekend, for instance) with no live-timing rate limit to worry about.

## Widgets
I really enjoyed the theme and style of the community widgets by @abaza738, so I largely use their theming and design, I just change the underlying API to achieve more custom results.

See the [`Glance Widgets/`](./Glance%20Widgets/) folder for the widgets you can drop straight into your Glance config - each subfolder has its own README with a preview. Not every endpoint has a matching widget yet (there's currently none for tyre usage); any endpoint in the [API Reference](#api-reference) works with Glance's `custom-api` widget type if you want to build your own. For more info on adding config files like these, see the [Glance documentation](https://github.com/glanceapp/glance/blob/main/docs/configuration.md#including-other-config-files).

# Installation
This repo uses docker compose to install. Verify that you are up to date. Below is an example compose file.
```yaml
version: "3.9"

services:
  paddock-api:
    container_name: paddock-api
    image: ghcr.io/drumandbytes/paddock-api:latest
    environment:
      - TIMEZONE=America/Edmonton # Specify your timezone.
      - TRACK_COLOUR=#e5d486 # Specify desired track map color
      - EVENT_DETAIL=main # Optional. main tracks qualis and races (inc. sprints), race tracks races. 
    ports:
      - 4463:4463
    restart: unless-stopped
```

| Variable | Required | Description |
|---|---|---|
| `TIMEZONE` | Yes | IANA timezone name (e.g. `America/Edmonton`, `Europe/Tallinn`) - every timestamp in the API is converted to this before being returned. |
| `TRACK_COLOUR` | Yes | Hex colour (e.g. `#e5d486`) for the track-map line. |
| `EVENT_DETAIL` | No, defaults to `main` | Controls which sessions `/f1/next_race/` counts down to: `main` (quali + races, skips practice), `race` (races only), or `detailed` (every session). |

To integrate with your Glance setup (to install Glance, see their documentation), add the widget YAMLs you want from [`Glance Widgets/`](./Glance%20Widgets/) - currently [Next Race](./Glance%20Widgets/Next%20Race/), [Last Race Results](./Glance%20Widgets/Last%20Race/), [Drivers Championship](./Glance%20Widgets/Drivers%20Championship/), and [Constructors Championship](./Glance%20Widgets/Constructors%20Championship/) - to your Glance config, making sure to replace `${F1_API_URL}` with your device's IP and updating the port if needed.

# API Reference
All endpoints return JSON except the track map, which returns an SVG image directly.

| Endpoint | Description |
|---|---|
| `GET /f1/next_race/` | The next (or currently in-progress) race weekend: full session schedule, localized to `TIMEZONE`, plus a countdown to the next session per `EVENT_DETAIL`. |
| `GET /f1/last_race/` | Full classification for the most recently completed race. |
| `GET /f1/drivers_standings/` | Current drivers' championship standings, with simplified team names and nationality flags. |
| `GET /f1/constructors_standings/` | Current constructors' championship standings, with simplified team names and nationality flags. |
| `GET /f1/next_map/` | An SVG track map for the next race's circuit. |
| `GET /f1/tyre_usage/` | Per-driver tyre compound and stint length for each session of the current race weekend (FP1-Race), for whichever sessions have happened so far. Usage only - see the endpoint's own module docstring for why allocation/sets-remaining isn't included. |

# Development
Requires Python 3.11+.

```sh
cd API
pip install -r requirements-dev.txt
pytest
```

CI runs the test suite on every push and PR (see [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)). [`.github/workflows/regenerate-track-maps.yml`](./.github/workflows/regenerate-track-maps.yml) re-renders every circuit's track map monthly (or on demand) and opens a PR if any changed; [`.github/workflows/publish.yml`](./.github/workflows/publish.yml) builds and pushes the Docker image on a `v*` tag push (`git tag vX.Y.Z && git push origin vX.Y.Z`).

To run the full thing locally the same way it runs in production:
```sh
docker compose up --build
```

# Demo
On the left below is a possible configuration using this custom API. On the right is a configuration using the default API used in the community widget.

The largest difference is localized time zones, track map, added track details, and general tidying up of the championship orders. 

<div align="center" >
  <img src="./Demo Images/glance-f1.png" width="225px" height = "600px" hspace="20px" />
  <img src="./Demo Images/community-f1.png" width="225px" height = "600px" hspace="20px" />
</div>

# Project Structure
```
paddock-api/
├── API/
│   ├── main.py                    # FastAPI application entry point
│   ├── requirements.txt           # Runtime dependencies
│   ├── requirements-dev.txt       # + test dependencies
│   ├── pytest.ini
│   ├── Dockerfile                 # Container build instructions
│   ├── scripts/
│   │   └── generate_track_maps.py # Pre-renders static track map SVGs
│   ├── static/track_maps/         # Pre-rendered SVGs, served directly when present
│   ├── tests/
│   └── API_Endpoints/
│       ├── constructors_cleaner.py
│       ├── current_race_cleaner.py
│       ├── drivers_cleaner.py
│       ├── last_race_cleaner.py
│       ├── tyre_usage_cleaner.py
│       ├── helpers/                # Shared schedule/time/formatting helpers
│       └── map/
│           ├── circuit_geometry.py # Static track geometry (bacinger/f1-circuits)
│           ├── map_generator.py    # Track SVG rendering
│           └── router.py           # Map endpoint logic
├── Glance Widgets/                # YAML files for Glance integration
├── .github/
│   ├── workflows/                 # CI, track-map regeneration, publish, auto-merge
│   └── dependabot.yml
├── LICENSE
└── docker-compose.yaml            # Local development compose file
```

# License
MIT - see [LICENSE](./LICENSE).
