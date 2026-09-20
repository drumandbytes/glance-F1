import io
import math
import os
import re

import svgwrite
from svgwrite.base import Title

EARTH_RADIUS_M = 6371000


def _project_to_local_meters(coordinates):
    """Equirectangular projection of [lon, lat] pairs to flat local meters -
    good enough for a track a few km across, and keeps the SVG drawing math
    below (padding, stroke width) working in roughly the same units a
    telemetry-derived track outline used to be in."""
    mid_lat_rad = math.radians(sum(lat for _, lat in coordinates) / len(coordinates))
    points = []
    for lon, lat in coordinates:
        x = math.radians(lon) * math.cos(mid_lat_rad) * EARTH_RADIUS_M
        # Latitude increases north; SVG y increases downward - flip it so
        # the map isn't upside down.
        y = -math.radians(lat) * EARTH_RADIUS_M
        points.append((x, y))
    return points


def render_track_svg(coordinates, track_name: str = None) -> str:
    track_color = os.environ['TRACK_COLOUR'].strip()

    if not re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', track_color):
        raise ValueError("Not a valid hex string")

    if not coordinates:
        raise ValueError("No track coordinates to draw")

    points = _project_to_local_meters(coordinates)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y

    # Give a 1% margin cause was clipping
    pad_x = width * 0.01
    pad_y = height * 0.01

    # Translate track so it's centered in the viewbox
    viewbox_width = width + 2 * pad_x
    viewbox_height = height + 2 * pad_y
    x_shift = -min_x + pad_x
    y_shift = -min_y + pad_y

    points = [(x + x_shift, y + y_shift) for x, y in points]

    svg_buf = io.StringIO()

    # Match column: small in glance, but probably shouldnt if wanna use in main
    display_width = 300

    # Have to sort out aspect ratio since will differ for every track.
    aspect_ratio = viewbox_height / viewbox_width
    display_height = int(display_width * aspect_ratio)
    dwg = svgwrite.Drawing(svg_buf, profile='full',
                           size=(f"{display_width}px", f"{display_height}px"),
                           viewBox=f"0 0 {viewbox_width} {viewbox_height}",
                           preserveAspectRatio="xMidYMid meet")

    # A single track_color line reads fine on whichever background it was
    # tuned against, but disappears on the other one (e.g. a light track
    # color against a light dashboard theme). Draw a wider black/white
    # border underneath it instead - black on a light background, white on
    # a dark one - so the outline stays visible either way regardless of
    # what track_color itself is.
    outline_class = 'track-outline'
    track_class = 'track-line'
    dwg.defs.add(dwg.style(f"""
        .{outline_class} {{
            fill: transparent;
            stroke: black;
            stroke-width: 56;
            stroke-linecap: round;
            stroke-linejoin: round;
        }}
        @media (prefers-color-scheme: dark) {{
            .{outline_class} {{
                stroke: white;
            }}
        }}
        .{track_class} {{
            fill: transparent;
            stroke: {track_color};
            stroke-width: 40;
            stroke-linecap: round;
            stroke-linejoin: round;
            title: {track_name};
        }}"""))

    outline = dwg.polyline(points=points, class_=outline_class, fill='none')
    dwg.add(outline)

    polyline = dwg.polyline(points=points, class_=track_class, fill='none')
    polyline.elements.append(Title(track_name))
    dwg.add(polyline)
    dwg.write(svg_buf)

    return svg_buf.getvalue()
