package main

import (
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"time"

	"github.com/labstack/echo/v4"
)

func (a *app) tyreUsage(c echo.Context) error {
	if cached, ok := a.cache.get("f1:tyre_usage", a.now()); ok {
		return c.JSON(http.StatusOK, cached)
	}
	year := a.now().In(a.config.timezone).Year()
	races, err := a.fetchSchedule(year)
	if err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	var selected *race
	for i := range races {
		at := rawSessionDateTime(races[i].Schedule["race"])
		if !at.IsZero() && !at.Before(a.now()) {
			selected = &races[i]
			break
		}
	}
	if selected == nil {
		return c.JSON(http.StatusOK, map[string]string{"message": "No current race weekend found"})
	}
	var openSessions []struct {
		Key   int    `json:"session_key"`
		Name  string `json:"session_name"`
		Start string `json:"date_start"`
	}
	if err := a.fetchJSON(fmt.Sprintf("%s/sessions?year=%d", a.config.openF1Base, year), &openSessions); err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	names := map[string]string{"fp1": "Practice 1", "fp2": "Practice 2", "fp3": "Practice 3", "qualy": "Qualifying", "sprintQualy": "Sprint Qualifying", "sprintRace": "Sprint", "race": "Race"}
	sessions := make(map[string]any, 7)
	for _, key := range sessionKeys {
		sessions[key] = nil
		at := rawSessionDateTime(selected.Schedule[key])
		if at.IsZero() || at.After(a.now()) {
			continue
		}
		openKey := 0
		best := 48 * time.Hour
		for _, candidate := range openSessions {
			start, parseErr := time.Parse(time.RFC3339, candidate.Start)
			delta := start.Sub(at)
			if delta < 0 {
				delta = -delta
			}
			if parseErr == nil && candidate.Name == names[key] && delta < best {
				openKey, best = candidate.Key, delta
			}
		}
		if openKey == 0 {
			continue
		}
		usage, fetchErr := a.fetchStints(openKey)
		if fetchErr == nil {
			sessions[key] = usage
		}
	}
	result := map[string]any{"season": year, "round": selected.Round, "raceName": selected.RaceName, "sessions": sessions}
	a.cache.set("f1:tyre_usage", result, a.now().Add(defaultExpire))
	return c.JSON(http.StatusOK, result)
}

func (a *app) fetchStints(sessionKey int) ([]map[string]any, error) {
	var drivers []struct {
		Number  int    `json:"driver_number"`
		Acronym string `json:"name_acronym"`
	}
	if err := a.fetchJSON(fmt.Sprintf("%s/drivers?session_key=%d", a.config.openF1Base, sessionKey), &drivers); err != nil {
		return nil, err
	}
	var stints []struct {
		Number   int     `json:"driver_number"`
		Stint    int     `json:"stint_number"`
		Compound *string `json:"compound"`
		Start    *int    `json:"lap_start"`
		End      *int    `json:"lap_end"`
	}
	if err := a.fetchJSON(fmt.Sprintf("%s/stints?session_key=%d", a.config.openF1Base, sessionKey), &stints); err != nil {
		return nil, err
	}
	acronyms := make(map[int]string)
	for _, driver := range drivers {
		acronyms[driver.Number] = driver.Acronym
	}
	type stintData struct {
		order    int
		compound string
		laps     int
	}
	grouped := make(map[string][]stintData)
	for _, stint := range stints {
		if stint.Compound == nil || stint.Start == nil || stint.End == nil {
			continue
		}
		driver := acronyms[stint.Number]
		if driver == "" {
			driver = strconv.Itoa(stint.Number)
		}
		laps := *stint.End - *stint.Start + 1
		if laps < 0 {
			continue
		}
		grouped[driver] = append(grouped[driver], stintData{order: stint.Stint, compound: *stint.Compound, laps: laps})
	}
	driverNames := make([]string, 0, len(grouped))
	for driver := range grouped {
		driverNames = append(driverNames, driver)
	}
	sort.Strings(driverNames)
	result := make([]map[string]any, 0, len(driverNames))
	for _, driver := range driverNames {
		items := grouped[driver]
		sort.Slice(items, func(i, j int) bool { return items[i].order < items[j].order })
		output := make([]map[string]any, 0, len(items))
		for _, item := range items {
			output = append(output, map[string]any{"compound": item.compound, "laps": item.laps})
		}
		result = append(result, map[string]any{"driver": driver, "stints": output})
	}
	return result, nil
}
