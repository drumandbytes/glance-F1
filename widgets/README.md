# Glance widgets

Drop the `.yml` files below into your Glance config to render this API's data.

Every one of them needs an `F1_API_URL` environment variable pointing at wherever this container runs - `localhost` if Glance and paddock-api are on the same machine, otherwise the container's IP. If you'd rather not use an environment variable, edit each `.yml` and replace `${F1_API_URL}` directly.

Two other things worth knowing, where they apply:
- If you're not a fan of the flag icons, delete the `<img>` tag that points at `flagcdn.com`.
- To change how many rows show before "show more" kicks in, edit the `data-collapse-after` attribute on the relevant `<ul>`.

## Available widgets

| Widget | What it shows |
|---|---|
| [`next-race/`](./next-race/) | Next race weekend, countdown to the next session, and the track map. `f1_nextrace_moredetail.yml` is the same thing with the full session schedule instead of just the next one. |
| [`last-race/`](./last-race/) | Full classification for the most recently completed race. |
| [`drivers-championship/`](./drivers-championship/) | Drivers' championship standings. |
| [`constructors-championship/`](./constructors-championship/) | Constructors' championship standings. |
| [`tyre-usage/`](./tyre-usage/) | Per-session tyre compound and stint length for the current race weekend, once a session's actually run. |
| [`latest-session/`](./latest-session/) | Classification of the most recent finished session (practice, sprint qualifying, qualifying or sprint) - separate from Last Race Results, which covers the Grand Prix. |

The styling throughout is borrowed from [@abaza738](https://github.com/glanceapp/community-widgets/blob/main/widgets/formula1-widgets-by-abaza738/README.md)'s original community widgets; only the API underneath changed.
