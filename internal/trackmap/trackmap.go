// Package trackmap fetches circuit outline geometry from bacinger/f1-circuits
// and renders it as a track-map SVG. Shared by the API's live /f1/next_map
// fallback (main.go) and the offline pre-renderer (cmd/gentrackmaps).
package trackmap

import (
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"math"
	"net/http"
	"strings"
)

const DefaultGeometryBase = "https://raw.githubusercontent.com/bacinger/f1-circuits/master/circuits"

// CircuitGeometryIDs maps our circuitId (matches the schedule's circuit ids
// and the static SVG filenames) to bacinger/f1-circuits' own
// <country-code>-<year-opened> id. Update when a new circuit joins the
// calendar.
var CircuitGeometryIDs = map[string]string{
	"albert_park": "au-1953", "shanghai": "cn-2004", "suzuka": "jp-1962", "bahrain": "bh-2002",
	"jeddah": "sa-2021", "miami": "us-2022", "imola": "it-1953", "monaco": "mc-1929",
	"catalunya": "es-1991", "villeneuve": "ca-1978", "red_bull_ring": "at-1969", "silverstone": "gb-1948",
	"spa": "be-1925", "hungaroring": "hu-1986", "zandvoort": "nl-1948", "monza": "it-1922",
	"madring": "es-2026", "baku": "az-2016", "sepang": "my-1999", "marina_bay": "sg-2008",
	"americas": "us-2012", "rodriguez": "mx-1962", "interlagos": "br-1940", "vegas": "us-2023",
	"losail": "qa-2004", "yas_marina": "ae-2009",
}

// FetchGeometry returns the [lon, lat] outline and circuit name for the
// given geojson id (a CircuitGeometryIDs value).
func FetchGeometry(client *http.Client, base, geometryID string) ([][]float64, string, error) {
	response, err := client.Get(fmt.Sprintf("%s/%s.geojson", base, geometryID))
	if err != nil {
		return nil, "", err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return nil, "", fmt.Errorf("HTTP %d: %s", response.StatusCode, strings.TrimSpace(string(body)))
	}
	var geo struct {
		Features []struct {
			Geometry struct {
				Coordinates [][]float64 `json:"coordinates"`
			} `json:"geometry"`
			Properties struct{ Name string } `json:"properties"`
		} `json:"features"`
	}
	if err := json.NewDecoder(response.Body).Decode(&geo); err != nil {
		return nil, "", err
	}
	if len(geo.Features) == 0 {
		return nil, "", errors.New("No track coordinates to draw")
	}
	return geo.Features[0].Geometry.Coordinates, geo.Features[0].Properties.Name, nil
}

// RenderSVG projects [lon, lat] coordinates to local meters (equirectangular -
// good enough for a track a few km across) and draws them as a track-outline
// SVG: a black outline with the given colour on top, sized to a 300px-wide
// dashboard tile.
func RenderSVG(coordinates [][]float64, name, colour string) ([]byte, error) {
	if len(coordinates) == 0 {
		return nil, errors.New("No track coordinates to draw")
	}
	mid := 0.0
	for _, point := range coordinates {
		if len(point) < 2 {
			return nil, errors.New("Invalid track coordinates")
		}
		mid += point[1]
	}
	mid = mid / float64(len(coordinates)) * math.Pi / 180
	type point struct{ x, y float64 }
	points := make([]point, len(coordinates))
	minX, maxX, minY, maxY := math.Inf(1), math.Inf(-1), math.Inf(1), math.Inf(-1)
	for i, coordinate := range coordinates {
		x := coordinate[0] * math.Pi / 180 * math.Cos(mid) * 6371000
		y := -coordinate[1] * math.Pi / 180 * 6371000
		points[i] = point{x, y}
		minX = math.Min(minX, x)
		maxX = math.Max(maxX, x)
		minY = math.Min(minY, y)
		maxY = math.Max(maxY, y)
	}
	width, height := maxX-minX, maxY-minY
	if width == 0 || height == 0 {
		return nil, errors.New("Invalid track coordinates")
	}
	padX, padY := width*.01, height*.01
	viewWidth, viewHeight := width+2*padX, height+2*padY
	var path strings.Builder
	for i, point := range points {
		if i > 0 {
			path.WriteByte(' ')
		}
		fmt.Fprintf(&path, "%.3f,%.3f", point.x-minX+padX, point.y-minY+padY)
	}
	line, outline := math.Min(viewWidth, viewHeight)*.012, math.Min(viewWidth, viewHeight)*.018
	displayHeight := int(300 * viewHeight / viewWidth)
	result := fmt.Sprintf(`<svg xmlns="http://www.w3.org/2000/svg" width="300px" height="%dpx" viewBox="0 0 %.3f %.3f" preserveAspectRatio="xMidYMid meet"><title>%s</title><polyline points="%s" fill="none" stroke="black" stroke-width="%.3f" stroke-linecap="round" stroke-linejoin="round"/><polyline points="%s" fill="none" stroke="%s" stroke-width="%.3f" stroke-linecap="round" stroke-linejoin="round"/></svg>`, displayHeight, viewWidth, viewHeight, html.EscapeString(name), path.String(), outline, path.String(), colour, line)
	return []byte(result), nil
}
