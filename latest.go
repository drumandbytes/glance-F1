package main

import (
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"sort"
	"time"

	"github.com/labstack/echo/v4"
)

// raceWindow is how long after its start a race is still treated as running -
// F1 races are capped at 3h including stoppages, but almost all finish inside 2.
const raceWindow = 2 * time.Hour

var sessionLabels = map[string]string{"fp1": "Free Practice 1", "fp2": "Free Practice 2", "fp3": "Free Practice 3", "sprintQualy": "Sprint Qualifying", "sprintRace": "Sprint Race", "qualy": "Qualifying", "race": "Race"}

var openF1SessionNames = map[string]string{"fp1": "Practice 1", "fp2": "Practice 2", "fp3": "Practice 3", "sprintQualy": "Sprint Qualifying", "sprintRace": "Sprint", "qualy": "Qualifying", "race": "Race"}

// sessionWindows is how long after its scheduled start a session counts as
// still running, so it isn't picked as the "latest" one before it's over.
var sessionWindows = map[string]time.Duration{"fp1": time.Hour, "fp2": time.Hour, "fp3": time.Hour, "sprintQualy": 45 * time.Minute, "sprintRace": 45 * time.Minute, "qualy": time.Hour}

func matchOpenF1Session(sessions []openF1Session, key string, at time.Time) *openF1Session {
	var match *openF1Session
	best := 48 * time.Hour
	for i := range sessions {
		start, err := time.Parse(time.RFC3339, sessions[i].Start)
		delta := start.Sub(at)
		if delta < 0 {
			delta = -delta
		}
		if err == nil && sessions[i].Name == openF1SessionNames[key] && delta < best {
			match, best = &sessions[i], delta
		}
	}
	return match
}

func latestFinishedSession(races []race, now time.Time) (*race, string, time.Time) {
	var found *race
	var foundKey string
	var foundAt time.Time
	for i := range races {
		for _, key := range sessionKeys {
			if key == "race" {
				continue // covered by /f1/last_race/
			}
			at := rawSessionDateTime(races[i].Schedule[key])
			if at.IsZero() || at.Add(sessionWindows[key]).After(now) {
				continue
			}
			if foundAt.IsZero() || at.After(foundAt) {
				found, foundKey, foundAt = &races[i], key, at
			}
		}
	}
	return found, foundKey, foundAt
}

func (a *app) latestSession(c echo.Context) error {
	if cached, ok := a.cache.get("f1:latest_session", a.now()); ok {
		return c.JSON(http.StatusOK, cached)
	}
	now := a.now()
	year := now.In(a.config.timezone).Year()
	races, err := a.fetchSchedule(year)
	if err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	r, key, at := latestFinishedSession(races, now)
	if r == nil {
		return c.JSON(http.StatusOK, map[string]string{"message": "No completed session yet"})
	}
	result := map[string]any{"season": year, "round": r.Round, "raceName": r.RaceName, "url": r.URL, "session": sessionLabels[key], "key": key, "date": formatRFC3339(at.In(a.config.timezone)), "results": []any{}}
	ttl := 2 * time.Minute
	// A finished session's classification never changes, so it's kept for
	// good - OpenF1's free tier locks out all access while any session is live.
	cacheKey := fmt.Sprintf("session_results:%d:%d:%s", year, r.Round, key)
	if cached, ok := a.cache.get(cacheKey, now); ok {
		result["results"], ttl = cached, 5*time.Minute
	} else if rows, ended, fetchErr := a.fetchSessionResults(key, at, now); fetchErr != nil {
		result["upstream_error"] = fetchErr.Error()
	} else {
		result["results"], ttl = rows, 5*time.Minute
		if ended && len(rows) > 0 {
			a.cache.set(cacheKey, rows, now.Add(30*24*time.Hour))
		}
	}
	a.cache.set("f1:latest_session", result, now.Add(ttl))
	return c.JSON(http.StatusOK, result)
}

func (a *app) fetchSessionResults(key string, at, now time.Time) ([]map[string]any, bool, error) {
	var sessions []openF1Session
	if err := a.fetchOpenF1(fmt.Sprintf("%s/sessions?year=%d", a.config.openF1Base, at.Year()), &sessions); err != nil {
		return nil, false, err
	}
	match := matchOpenF1Session(sessions, key, at)
	if match == nil {
		return nil, false, fmt.Errorf("session not on OpenF1 yet")
	}
	var results []struct {
		Position     *int            `json:"position"`
		DriverNumber int             `json:"driver_number"`
		Duration     json.RawMessage `json:"duration"`
		Gap          json.RawMessage `json:"gap_to_leader"`
		Laps         int             `json:"number_of_laps"`
		DNF          bool            `json:"dnf"`
		DNS          bool            `json:"dns"`
		DSQ          bool            `json:"dsq"`
	}
	if err := a.fetchOpenF1(fmt.Sprintf("%s/session_result?session_key=%d", a.config.openF1Base, match.Key), &results); err != nil {
		return nil, false, err
	}
	var drivers []struct {
		Number   int    `json:"driver_number"`
		Acronym  string `json:"name_acronym"`
		LastName string `json:"last_name"`
		Team     string `json:"team_name"`
	}
	if err := a.fetchOpenF1(fmt.Sprintf("%s/drivers?session_key=%d", a.config.openF1Base, match.Key), &drivers); err != nil {
		return nil, false, err
	}
	byNumber := make(map[int]int, len(drivers))
	for i, d := range drivers {
		byNumber[d.Number] = i
	}
	sort.SliceStable(results, func(i, j int) bool {
		if results[i].Position == nil || results[j].Position == nil {
			return results[i].Position != nil
		}
		return *results[i].Position < *results[j].Position
	})
	rows := make([]map[string]any, 0, len(results))
	for _, r := range results {
		driver := fmt.Sprint(r.DriverNumber)
		row := map[string]any{"position": nil, "driver": driver, "surname": driver, "team": "", "laps": r.Laps}
		if i, ok := byNumber[r.DriverNumber]; ok {
			row["driver"], row["surname"], row["team"] = drivers[i].Acronym, drivers[i].LastName, shortTeamName(drivers[i].Team)
		}
		if r.Position != nil {
			row["position"] = *r.Position
		}
		row["time"] = sessionTimeCell(r.Duration, r.Gap, r.DNF, r.DNS, r.DSQ, r.Position != nil && *r.Position == 1)
		rows = append(rows, row)
	}
	end, err := time.Parse(time.RFC3339, match.End)
	return rows, err == nil && end.Before(now), nil
}

func sessionTimeCell(duration, gap json.RawMessage, dnf, dns, dsq, leader bool) string {
	switch {
	case dsq:
		return "DSQ"
	case dns:
		return "DNS"
	case dnf:
		return "DNF"
	}
	if leader {
		if v, ok := lastNumber(duration); ok {
			return formatSessionDuration(v)
		}
	}
	var text string
	if json.Unmarshal(gap, &text) == nil && text != "" {
		return text
	}
	if v, ok := lastNumber(gap); ok {
		return fmt.Sprintf("+%.3f", v)
	}
	if v, ok := lastNumber(duration); ok {
		return formatSessionDuration(v)
	}
	return ""
}

// lastNumber reads a JSON number, or the last non-null entry of an array of
// them (OpenF1 returns per-phase values for qualifying, e.g. [Q1, Q2, Q3]).
func lastNumber(raw json.RawMessage) (float64, bool) {
	if len(raw) == 0 || string(raw) == "null" {
		return 0, false
	}
	var one float64
	if json.Unmarshal(raw, &one) == nil {
		return one, true
	}
	var many []*float64
	if json.Unmarshal(raw, &many) == nil {
		for i := len(many) - 1; i >= 0; i-- {
			if many[i] != nil {
				return *many[i], true
			}
		}
	}
	return 0, false
}

func formatSessionDuration(seconds float64) string {
	total := int(math.Round(seconds * 1000))
	ms, s := total%1000, total/1000
	h, m, s := s/3600, (s%3600)/60, s%60
	if h > 0 {
		return fmt.Sprintf("%d:%02d:%02d.%03d", h, m, s, ms)
	}
	return fmt.Sprintf("%d:%02d.%03d", m, s, ms)
}

// shortTeamName maps OpenF1's team names onto the short names the rest of
// the API uses (from Ergast constructor ids), so tiles read consistently.
func shortTeamName(name string) string {
	switch name {
	case "Red Bull Racing":
		return "Red Bull"
	case "Racing Bulls":
		return "RB"
	case "Haas F1 Team":
		return "Haas"
	}
	return name
}
