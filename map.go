package main

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/labstack/echo/v4"
	"github.com/maris/paddock-api/internal/trackmap"
)

func (a *app) nextMap(c echo.Context) error {
	next, err := a.getNextRace()
	if err != nil {
		return c.String(http.StatusBadGateway, "Failed to fetch race info: "+err.Error())
	}
	if next == nil || len(next.Race) == 0 || next.Race[0].Circuit.CircuitID == nil {
		return c.String(http.StatusNotFound, "No track geometry known for circuit <nil>")
	}
	id := *next.Race[0].Circuit.CircuitID
	path := filepath.Join(a.config.staticMapDir, id+".svg")
	if data, readErr := os.ReadFile(path); readErr == nil {
		data = []byte(strings.ReplaceAll(string(data), "#e5d486", a.config.trackColour))
		return c.Blob(http.StatusOK, "image/svg+xml", data)
	}
	geometryID, ok := trackmap.CircuitGeometryIDs[id]
	if !ok {
		return c.String(http.StatusNotFound, fmt.Sprintf("No track geometry known for circuit %q", id))
	}
	cacheKey := "track_map_svg:" + id + ":" + a.config.trackColour
	if cached, found := a.cache.get(cacheKey, a.now()); found {
		return c.Blob(http.StatusOK, "image/svg+xml", cached.([]byte))
	}
	coordinates, geoName, err := trackmap.FetchGeometry(a.client, a.config.geometryBase, geometryID)
	if err != nil {
		return c.String(http.StatusInternalServerError, err.Error())
	}
	name := next.Race[0].Circuit.CircuitName
	if name == "" {
		name = geoName
	}
	svg, err := trackmap.RenderSVG(coordinates, name, a.config.trackColour)
	if err != nil {
		return c.String(http.StatusInternalServerError, err.Error())
	}
	a.cache.set(cacheKey, svg, a.now().Add(defaultExpire))
	return c.Blob(http.StatusOK, "image/svg+xml", svg)
}
