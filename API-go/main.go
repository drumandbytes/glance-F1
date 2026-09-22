package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
)

const (
	ErgastBase = "https://ergast.com/api/f1"
	OpenF1Base = "https://api.openf1.org/v1"
)

type CacheEntry struct {
	Data      interface{}
	ExpiresAt time.Time
}

type Cache struct {
	mu    sync.RWMutex
	store map[string]CacheEntry
}

func NewCache() *Cache {
	return &Cache{
		store: make(map[string]CacheEntry),
	}
}

func (c *Cache) Get(key string) (interface{}, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.store[key]
	if !exists {
		return nil, false
	}

	if time.Now().After(entry.ExpiresAt) {
		return nil, false
	}

	return entry.Data, true
}

func (c *Cache) Set(key string, value interface{}, ttl int) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.store[key] = CacheEntry{
		Data:      value,
		ExpiresAt: time.Now().Add(time.Duration(ttl) * time.Second),
	}
}

var cache = NewCache()

func fetchJSON(url string, v interface{}) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	return json.NewDecoder(resp.Body).Decode(v)
}

func getDriverStandings(c echo.Context) error {
	cacheKey := "drivers_championship"
	if cached, ok := cache.Get(cacheKey); ok {
		return c.JSON(http.StatusOK, cached)
	}

	season := time.Now().Year()
	url := fmt.Sprintf("%s/%d/driverStandings.json", ErgastBase, season)

	var ergastResp struct {
		MRData struct {
			StandingsTable struct {
				StandingsList []struct {
					DriverStandings []struct {
						Position  string `json:"position"`
						Points    string `json:"points"`
						Driver    struct {
							FamilyName  string `json:"familyName"`
							Nationality string `json:"nationality"`
						} `json:"Driver"`
						Constructors []struct {
							ConstructorId string `json:"constructorId"`
						} `json:"Constructors"`
					} `json:"DriverStandings"`
				} `json:"StandingsList"`
			} `json:"StandingsTable"`
		} `json:"MRData"`
	}

	if err := fetchJSON(url, &ergastResp); err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
	}

	if len(ergastResp.MRData.StandingsTable.StandingsList) == 0 {
		return c.JSON(http.StatusOK, map[string]interface{}{"drivers": []interface{}{}})
	}

	standings := ergastResp.MRData.StandingsTable.StandingsList[0].DriverStandings
	results := make([]map[string]interface{}, 0, len(standings))

	for _, standing := range standings {
		constructor := ""
		if len(standing.Constructors) > 0 {
			constructor = standing.Constructors[0].ConstructorId
		}

		results = append(results, map[string]interface{}{
			"surname":   standing.Driver.FamilyName,
			"position":  standing.Position,
			"points":    standing.Points,
			"teamId":    constructor,
			"country":   standing.Driver.Nationality,
			"flag":      countryToCode(standing.Driver.Nationality),
		})
	}

	response := map[string]interface{}{
		"season":  season,
		"drivers": results,
	}

	cache.Set(cacheKey, response, 600)
	return c.JSON(http.StatusOK, response)
}

func getConstructorStandings(c echo.Context) error {
	cacheKey := "constructors_championship"
	if cached, ok := cache.Get(cacheKey); ok {
		return c.JSON(http.StatusOK, cached)
	}

	season := time.Now().Year()
	url := fmt.Sprintf("%s/%d/constructorStandings.json", ErgastBase, season)

	var ergastResp struct {
		MRData struct {
			StandingsTable struct {
				StandingsList []struct {
					ConstructorStandings []struct {
						Position   string `json:"position"`
						Points     string `json:"points"`
						Wins       string `json:"wins"`
						Constructor struct {
							Name        string `json:"name"`
							Nationality string `json:"nationality"`
							Url         string `json:"url"`
						} `json:"Constructor"`
					} `json:"ConstructorStandings"`
				} `json:"StandingsList"`
			} `json:"StandingsTable"`
		} `json:"MRData"`
	}

	if err := fetchJSON(url, &ergastResp); err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
	}

	if len(ergastResp.MRData.StandingsTable.StandingsList) == 0 {
		return c.JSON(http.StatusOK, map[string]interface{}{"constructors": []interface{}{}})
	}

	standings := ergastResp.MRData.StandingsTable.StandingsList[0].ConstructorStandings
	results := make([]map[string]interface{}, 0, len(standings))

	for _, standing := range standings {
		results = append(results, map[string]interface{}{
			"team":     standing.Constructor.Name,
			"position": standing.Position,
			"points":   standing.Points,
			"wins":     standing.Wins,
			"country":  standing.Constructor.Nationality,
			"flag":     countryToCode(standing.Constructor.Nationality),
			"wiki":     standing.Constructor.Url,
		})
	}

	response := map[string]interface{}{
		"season":        season,
		"constructors":  results,
	}

	cache.Set(cacheKey, response, 600)
	return c.JSON(http.StatusOK, response)
}

func getLastRace(c echo.Context) error {
	cacheKey := "f1:last_race"
	if cached, ok := cache.Get(cacheKey); ok {
		return c.JSON(http.StatusOK, cached)
	}

	season := time.Now().Year()
	url := fmt.Sprintf("%s/%d/last/results.json", ErgastBase, season)

	var ergastResp struct {
		MRData struct {
			RaceTable struct {
				Races []struct {
					Season   string `json:"season"`
					Round    string `json:"round"`
					RaceName string `json:"raceName"`
					Date     string `json:"date"`
					Results  []struct {
						Position   string `json:"position"`
						Laps       string `json:"laps"`
						Time       struct {
							Time string `json:"time"`
						} `json:"Time"`
						Driver struct {
							FamilyName  string `json:"familyName"`
							Nationality string `json:"nationality"`
						} `json:"Driver"`
						Constructor struct {
							ConstructorId string `json:"constructorId"`
						} `json:"Constructor"`
					} `json:"Results"`
				} `json:"Races"`
			} `json:"RaceTable"`
		} `json:"MRData"`
	}

	if err := fetchJSON(url, &ergastResp); err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
	}

	if len(ergastResp.MRData.RaceTable.Races) == 0 {
		return c.JSON(http.StatusOK, map[string]interface{}{"results": []interface{}{}})
	}

	race := ergastResp.MRData.RaceTable.Races[0]
	results := make([]map[string]interface{}, 0, len(race.Results))

	for _, result := range race.Results {
		results = append(results, map[string]interface{}{
			"position": result.Position,
			"surname":  result.Driver.FamilyName,
			"flag":     countryToCode(result.Driver.Nationality),
			"teamId":   result.Constructor.ConstructorId,
			"time":     result.Time.Time,
		})
	}

	response := map[string]interface{}{
		"season":    race.Season,
		"round":     race.Round,
		"raceName":  race.RaceName,
		"date":      race.Date,
		"results":   results,
	}

	cache.Set(cacheKey, response, 86400)
	return c.JSON(http.StatusOK, response)
}

func getNextRace(c echo.Context) error {
	cacheKey := "f1:next_race"
	if cached, ok := cache.Get(cacheKey); ok {
		return c.JSON(http.StatusOK, cached)
	}

	season := time.Now().Year()
	url := fmt.Sprintf("%s/%d.json", ErgastBase, season)

	var ergastResp struct {
		MRData struct {
			RaceTable struct {
				Races []struct {
					Round    string `json:"round"`
					RaceName string `json:"raceName"`
					Date     string `json:"date"`
					Time     string `json:"time"`
				} `json:"Races"`
			} `json:"RaceTable"`
		} `json:"MRData"`
	}

	if err := fetchJSON(url, &ergastResp); err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
	}

	response := map[string]interface{}{
		"season": season,
		"races":  ergastResp.MRData.RaceTable.Races,
	}

	cache.Set(cacheKey, response, 3600)
	return c.JSON(http.StatusOK, response)
}

func getTyreUsage(c echo.Context) error {
	cacheKey := "f1:tyre_usage"
	if cached, ok := cache.Get(cacheKey); ok {
		return c.JSON(http.StatusOK, cached)
	}

	response := map[string]interface{}{
		"message": "Tyre usage requires OpenF1 data - not yet implemented",
	}

	return c.JSON(http.StatusOK, response)
}

func countryToCode(country string) string {
	countryMap := map[string]string{
		"British":       "gb",
		"Dutch":         "nl",
		"Monegasque":    "mc",
		"Thai":          "th",
		"Argentine":     "ar",
		"New Zealander": "nz",
		"Australian":    "au",
		"French":        "fr",
		"Spanish":       "es",
		"German":        "de",
		"Canadian":      "ca",
		"Italian":       "it",
		"Japanese":      "jp",
		"Brazilian":     "br",
		"Mexican":       "mx",
		"Chinese":       "cn",
		"Finnish":       "fi",
		"American":      "us",
		"Austrian":      "at",
	}

	if code, ok := countryMap[country]; ok {
		return code
	}
	return ""
}

func main() {
	e := echo.New()

	e.Use(middleware.Logger())
	e.Use(middleware.Recover())

	e.GET("/f1/drivers_standings/", getDriverStandings)
	e.GET("/f1/constructors_standings/", getConstructorStandings)
	e.GET("/f1/last_race/", getLastRace)
	e.GET("/f1/next_race/", getNextRace)
	e.GET("/f1/tyre_usage/", getTyreUsage)

	port := os.Getenv("PORT")
	if port == "" {
		port = "4463"
	}

	log.Printf("Starting F1 API on port %s", port)
	e.Logger.Fatal(e.Start(":" + port))
}
