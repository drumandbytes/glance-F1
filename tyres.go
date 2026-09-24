package main

import (
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"time"

	"github.com/labstack/echo/v4"
)

type openF1Session struct {
	Key   int    `json:"session_key"`
	Name  string `json:"session_name"`
	Start string `json:"date_start"`
	End   string `json:"date_end"`
}

// currentWeekend is the latest race weekend whose first session has started -
// it stays current until the next weekend's first session starts, so a
// finished race's tyre usage keeps showing through the week.
func currentWeekend(races []race, now time.Time) *race {
	var current *race
	for i := range races {
		var first time.Time
		for _, key := range sessionKeys {
			if at := rawSessionDateTime(races[i].Schedule[key]); !at.IsZero() && (first.IsZero() || at.Before(first)) {
				first = at
			}
		}
		if !first.IsZero() && !first.After(now) {
			current = &races[i]
		}
	}
	return current
}

func (a *app) tyreUsage(c echo.Context) error {
	if cached, ok := a.cache.get("f1:tyre_usage", a.now()); ok {
		return c.JSON(http.StatusOK, cached)
	}
	now := a.now()
	year := now.In(a.config.timezone).Year()
	races, err := a.fetchSchedule(year)
	if err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	selected := currentWeekend(races, now)
	if selected == nil {
		return c.JSON(http.StatusOK, map[string]string{"message": "No current race weekend found"})
	}
	var openSessions []openF1Session
	var openErr error
	loaded := false
	sessions := make(map[string]any, 7)
	missing := 0
	for _, key := range sessionKeys {
		sessions[key] = nil
		at := rawSessionDateTime(selected.Schedule[key])
		if at.IsZero() || at.After(now) {
			continue
		}
		// A finished session's stints never change, so once fetched they're
		// kept for good - OpenF1's free tier locks out all access (even past
		// sessions) while any session is live, which would otherwise blank
		// data we already had.
		sessionCacheKey := fmt.Sprintf("tyre_session:%d:%d:%s", year, selected.Round, key)
		if cached, ok := a.cache.get(sessionCacheKey, now); ok {
			sessions[key] = cached
			continue
		}
		if !loaded {
			loaded = true
			openErr = a.fetchOpenF1(fmt.Sprintf("%s/sessions?year=%d", a.config.openF1Base, year), &openSessions)
		}
		if openErr != nil {
			missing++
			continue
		}
		match := matchOpenF1Session(openSessions, key, at)
		if match == nil {
			missing++
			continue
		}
		usage, fetchErr := a.fetchStints(match.Key)
		if fetchErr != nil {
			missing++
			continue
		}
		sessions[key] = usage
		if end, parseErr := time.Parse(time.RFC3339, match.End); parseErr == nil && end.Before(now) {
			a.cache.set(sessionCacheKey, usage, now.Add(30*24*time.Hour))
		}
	}
	result := map[string]any{"season": year, "round": selected.Round, "raceName": selected.RaceName, "sessions": sessions}
	if openErr != nil {
		result["upstream_error"] = openErr.Error()
	}
	ttl := defaultExpire
	if missing > 0 {
		ttl = 2 * time.Minute
	}
	a.cache.set("f1:tyre_usage", result, now.Add(ttl))
	return c.JSON(http.StatusOK, result)
}

func (a *app) fetchStints(sessionKey int) ([]map[string]any, error) {
	var drivers []struct {
		Number  int    `json:"driver_number"`
		Acronym string `json:"name_acronym"`
	}
	if err := a.fetchOpenF1(fmt.Sprintf("%s/drivers?session_key=%d", a.config.openF1Base, sessionKey), &drivers); err != nil {
		return nil, err
	}
	var stints []struct {
		Number   int     `json:"driver_number"`
		Stint    int     `json:"stint_number"`
		Compound *string `json:"compound"`
		Start    *int    `json:"lap_start"`
		End      *int    `json:"lap_end"`
	}
	if err := a.fetchOpenF1(fmt.Sprintf("%s/stints?session_key=%d", a.config.openF1Base, sessionKey), &stints); err != nil {
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
