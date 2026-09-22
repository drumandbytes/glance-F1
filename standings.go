package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/labstack/echo/v4"
)

var nationalityNames = map[string]string{
	"British": "Great Britain", "Dutch": "Netherlands", "Monegasque": "Monaco", "Thai": "Thailand",
	"Argentine": "Argentina", "New Zealander": "New Zealand", "Australian": "Australia", "French": "France",
	"Spanish": "Spain", "German": "Germany", "Canadian": "Canada", "Italian": "Italy", "Japanese": "Japan",
	"Brazilian": "Brazil", "Mexican": "Mexico", "Chinese": "China", "Finnish": "Finland",
	"American": "United States", "Austrian": "Austria",
}

var countryCodes = map[string]string{
	"Great Britain": "gb", "Netherlands": "nl", "Monaco": "mc", "Thailand": "th", "Argentina": "ar",
	"New Zealand": "nz", "Australia": "au", "France": "fr", "Spain": "es", "Germany": "de",
	"Canada": "ca", "Italy": "it", "Japan": "jp", "Brazil": "br", "Mexico": "mx", "China": "cn",
	"Finland": "fi", "United States": "us", "Austria": "at",
}

func (a *app) drivers(c echo.Context) error {
	if cached, ok := a.cache.get("drivers_championship", a.now()); ok {
		return c.JSON(http.StatusOK, cached)
	}
	year := a.now().In(a.config.timezone).Year()
	var upstream struct {
		MRData struct {
			StandingsTable struct {
				Lists []struct {
					Standings []struct {
						Position     json.Number                              `json:"position"`
						Points       json.Number                              `json:"points"`
						Driver       struct{ FamilyName, Nationality string } `json:"Driver"`
						Constructors []struct {
							ID string `json:"constructorId"`
						} `json:"Constructors"`
					} `json:"DriverStandings"`
				} `json:"StandingsLists"`
			} `json:"StandingsTable"`
		} `json:"MRData"`
	}
	if err := a.fetchJSON(fmt.Sprintf("%s/%d/driverStandings.json", a.config.ergastBase, year), &upstream); err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	results := make([]map[string]any, 0)
	if len(upstream.MRData.StandingsTable.Lists) > 0 {
		for _, standing := range upstream.MRData.StandingsTable.Lists[0].Standings {
			team := ""
			if len(standing.Constructors) > 0 {
				team = formatTeamName(standing.Constructors[0].ID)
			}
			country := normalizeNationality(standing.Driver.Nationality)
			results = append(results, map[string]any{"surname": standing.Driver.FamilyName, "position": numberInt(standing.Position), "points": numberFloat(standing.Points), "teamId": team, "country": country, "flag": countryCodes[country]})
		}
	}
	result := map[string]any{"season": year, "drivers": results}
	a.cache.set("drivers_championship", result, a.now().Add(10*time.Minute))
	return c.JSON(http.StatusOK, result)
}

func (a *app) constructors(c echo.Context) error {
	if cached, ok := a.cache.get("constructors_championship", a.now()); ok {
		return c.JSON(http.StatusOK, cached)
	}
	year := a.now().In(a.config.timezone).Year()
	var upstream struct {
		MRData struct {
			StandingsTable struct {
				Lists []struct {
					Standings []struct {
						Position    json.Number `json:"position"`
						Points      json.Number `json:"points"`
						Wins        json.Number `json:"wins"`
						Constructor struct {
							Name, Nationality string
							URL               string `json:"url"`
						} `json:"Constructor"`
					} `json:"ConstructorStandings"`
				} `json:"StandingsLists"`
			} `json:"StandingsTable"`
		} `json:"MRData"`
	}
	if err := a.fetchJSON(fmt.Sprintf("%s/%d/constructorStandings.json", a.config.ergastBase, year), &upstream); err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	results := make([]map[string]any, 0)
	if len(upstream.MRData.StandingsTable.Lists) > 0 {
		for _, standing := range upstream.MRData.StandingsTable.Lists[0].Standings {
			country := normalizeNationality(standing.Constructor.Nationality)
			results = append(results, map[string]any{"team": standing.Constructor.Name, "position": numberInt(standing.Position), "points": numberFloat(standing.Points), "wins": numberInt(standing.Wins), "country": country, "flag": countryCodes[country], "wiki": standing.Constructor.URL})
		}
	}
	result := map[string]any{"season": year, "constructors": results}
	a.cache.set("constructors_championship", result, a.now().Add(10*time.Minute))
	return c.JSON(http.StatusOK, result)
}

func normalizeNationality(value string) string {
	if country, ok := nationalityNames[value]; ok {
		return country
	}
	return ""
}
func formatTeamName(value string) string {
	if value == "rb" {
		return "RB"
	}
	words := strings.Fields(strings.ReplaceAll(value, "_", " "))
	for i := range words {
		words[i] = strings.ToUpper(words[i][:1]) + strings.ToLower(words[i][1:])
	}
	return strings.Join(words, " ")
}
