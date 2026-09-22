package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/maris/paddock-api/internal/trackmap"
	_ "time/tzdata"
)

const (
	defaultErgastBase   = "https://api.jolpi.ca/ergast/f1"
	defaultOpenF1Base   = "https://api.openf1.org/v1"
	defaultGeometryBase = trackmap.DefaultGeometryBase
	defaultExpire       = time.Hour
)

type config struct {
	timezone     *time.Location
	timezoneID   string
	eventDetail  string
	trackColour  string
	ergastBase   string
	openF1Base   string
	geometryBase string
	staticMapDir string
}

type app struct {
	config config
	client *http.Client
	cache  *cacheStore
	now    func() time.Time
	log    *slog.Logger
}

func loadConfig() (config, error) {
	tz := strings.TrimSpace(os.Getenv("TIMEZONE"))
	if tz == "" {
		return config{}, errors.New("TIMEZONE is required")
	}
	loc, err := time.LoadLocation(tz)
	if err != nil {
		return config{}, errors.New("invalid TIMEZONE")
	}
	detail := strings.TrimSpace(os.Getenv("EVENT_DETAIL"))
	if detail == "" {
		detail = "main"
	}
	if detail != "main" && detail != "race" && detail != "detailed" {
		return config{}, errors.New("EVENT_DETAIL must be main, race, or detailed")
	}
	colour := strings.TrimSpace(os.Getenv("TRACK_COLOUR"))
	if !regexp.MustCompile(`^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$`).MatchString(colour) {
		return config{}, errors.New("TRACK_COLOUR must be a hex colour")
	}
	return config{
		timezone: loc, timezoneID: tz, eventDetail: detail, trackColour: colour,
		ergastBase: envOr("ERGAST_BASE_URL", defaultErgastBase), openF1Base: envOr("OPENF1_BASE_URL", defaultOpenF1Base),
		geometryBase: envOr("GEOMETRY_BASE_URL", defaultGeometryBase), staticMapDir: envOr("STATIC_MAP_DIR", "static/track_maps"),
	}, nil
}

func envOr(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return strings.TrimRight(value, "/")
	}
	return fallback
}

func (a *app) fetchJSON(url string, target any) error {
	response, err := a.client.Get(url)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return fmt.Errorf("HTTP %d: %s", response.StatusCode, strings.TrimSpace(string(body)))
	}
	decoder := json.NewDecoder(response.Body)
	decoder.UseNumber()
	return decoder.Decode(target)
}

func newServer(a *app) *echo.Echo {
	e := echo.New()
	e.HideBanner, e.HidePort = true, true
	e.HTTPErrorHandler = func(err error, c echo.Context) {
		if !c.Response().Committed {
			_ = c.JSON(http.StatusInternalServerError, map[string]string{"error": "Internal Server Error"})
		}
		a.log.Error("request failed", "error", err)
	}
	routes := []struct {
		path    string
		handler echo.HandlerFunc
	}{{"/f1/drivers_standings", a.drivers}, {"/f1/constructors_standings", a.constructors}, {"/f1/last_race", a.lastRace}, {"/f1/next_race", a.nextRace}, {"/f1/tyre_usage", a.tyreUsage}, {"/f1/next_map", a.nextMap}}
	for _, route := range routes {
		e.GET(route.path, route.handler)
		e.GET(route.path+"/", route.handler)
	}
	return e
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	cfg, err := loadConfig()
	if err != nil {
		logger.Error("invalid configuration", "error", err)
		os.Exit(1)
	}
	a := &app{config: cfg, client: &http.Client{Timeout: 15 * time.Second}, cache: newCache(), now: time.Now, log: logger}
	port := envOr("PORT", "4463")
	logger.Info("server starting", "port", port)
	if err := newServer(a).Start(":" + port); err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("server stopped", "error", err)
		os.Exit(1)
	}
}
