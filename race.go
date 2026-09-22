package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"time"

	"github.com/labstack/echo/v4"
)

type sessionTime struct {
	Date     *string `json:"date"`
	Time     *string `json:"time"`
	DateTime *string `json:"datetime_rfc3339,omitempty"`
}

type circuit struct {
	CircuitID   *string `json:"circuitId"`
	CircuitName string  `json:"circuitName"`
	URL         *string `json:"url"`
	Country     string  `json:"country"`
	City        string  `json:"city"`
}

type race struct {
	Round    int                    `json:"round"`
	RaceName string                 `json:"raceName"`
	URL      *string                `json:"url"`
	Schedule map[string]sessionTime `json:"schedule"`
	Circuit  circuit                `json:"circuit"`
}

type nextEvent struct {
	Session  string `json:"session"`
	Date     string `json:"date"`
	Time     string `json:"time"`
	DateTime string `json:"datetime"`
}

type nextRaceResponse struct {
	Season       int        `json:"season"`
	Round        int        `json:"round"`
	Timezone     string     `json:"timezone"`
	NextEvent    *nextEvent `json:"next_event"`
	CacheExpires string     `json:"cache_expires"`
	Race         []race     `json:"race"`
}

var sessionKeys = []string{"fp1", "fp2", "fp3", "sprintQualy", "sprintRace", "qualy", "race"}

func (a *app) lastRace(c echo.Context) error {
	if cached, ok := a.cache.get("f1:last_race", a.now()); ok {
		return c.JSON(http.StatusOK, cached)
	}
	var upstream struct {
		MRData struct {
			RaceTable struct {
				Races []struct {
					Season              json.Number `json:"season"`
					Round               json.Number `json:"round"`
					RaceName, URL, Date string
					Results             []struct {
						Position     json.Number `json:"position"`
						PositionText string      `json:"positionText"`
						Laps         json.Number `json:"laps"`
						Time         *struct {
							Time string `json:"time"`
						} `json:"Time"`
						Driver      struct{ FamilyName, Nationality string } `json:"Driver"`
						Constructor struct {
							ID string `json:"constructorId"`
						} `json:"Constructor"`
					} `json:"Results"`
				} `json:"Races"`
			} `json:"RaceTable"`
		} `json:"MRData"`
	}
	if err := a.fetchJSON(a.config.ergastBase+"/current/last/results.json", &upstream); err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	if len(upstream.MRData.RaceTable.Races) == 0 {
		return c.JSON(http.StatusOK, map[string]any{"results": []any{}})
	}
	raceData := upstream.MRData.RaceTable.Races[0]
	results := make([]map[string]any, 0, len(raceData.Results))
	for _, item := range raceData.Results {
		dnf := item.PositionText == "" || !allDigits(item.PositionText)
		var raceTime any
		var dnfLaps any
		if dnf {
			laps := numberInt(item.Laps)
			raceTime = "DNF"
			if laps > 0 {
				raceTime = fmt.Sprintf("DNF (%d)", laps)
				dnfLaps = laps
			}
		} else if item.Time != nil {
			raceTime = item.Time.Time
		}
		surname := item.Driver.FamilyName
		if surname == "Kimi Antonelli" {
			surname = "Antonelli"
		}
		country := normalizeNationality(item.Driver.Nationality)
		results = append(results, map[string]any{"position": numberInt(item.Position), "surname": surname, "country": country, "flag": countryCodes[country], "teamId": item.Constructor.ID, "time": raceTime, "dnf_laps": dnfLaps})
	}
	expires := a.now().Add(24 * time.Hour)
	result := map[string]any{"season": numberInt(raceData.Season), "round": numberInt(raceData.Round), "raceName": raceData.RaceName, "url": nullableString(raceData.URL), "date": nullableString(raceData.Date), "cache_expires": formatRFC3339(expires), "results": results}
	a.cache.set("f1:last_race", result, expires)
	return c.JSON(http.StatusOK, result)
}

func (a *app) nextRace(c echo.Context) error {
	result, err := a.getNextRace()
	if err != nil {
		return c.JSON(http.StatusOK, map[string]string{"error": "Exception while fetching: " + err.Error()})
	}
	if result == nil {
		return c.JSON(http.StatusOK, map[string]string{"message": "No upcoming race found"})
	}
	return c.JSON(http.StatusOK, result)
}

func (a *app) getNextRace() (*nextRaceResponse, error) {
	if cached, ok := a.cache.get("f1:next_race", a.now()); ok {
		return cached.(*nextRaceResponse), nil
	}
	year := a.now().In(a.config.timezone).Year()
	races, err := a.fetchSchedule(year)
	if err != nil {
		return nil, err
	}
	now := a.now()
	var selected *race
	for i := range races {
		dt := rawSessionDateTime(races[i].Schedule["race"])
		if !dt.IsZero() && !dt.Before(now) {
			selected = &races[i]
			break
		}
	}
	if selected == nil {
		return nil, nil
	}
	readable := map[string]string{"fp1": "Free Practice 1", "fp2": "Free Practice 2", "fp3": "Free Practice 3", "qualy": "Qualifying", "sprintQualy": "Sprint Qualifying", "sprintRace": "Sprint Race", "race": "Race"}
	type candidate struct {
		key string
		at  time.Time
	}
	candidates := make([]candidate, 0, 7)
	for _, key := range sessionKeys {
		raw := selected.Schedule[key]
		dt := rawSessionDateTime(raw)
		if dt.IsZero() {
			continue
		}
		local := dt.In(a.config.timezone)
		date, clock, stamp := local.Format("2006-01-02"), local.Format("3:04PM"), formatRFC3339(local)
		raw.Date, raw.Time, raw.DateTime = &date, &clock, &stamp
		selected.Schedule[key] = raw
		if dt.After(now) && sessionAllowed(a.config.eventDetail, key) {
			candidates = append(candidates, candidate{key: key, at: dt})
		}
	}
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].at.Before(candidates[j].at) })
	var event *nextEvent
	if len(candidates) > 0 {
		data := selected.Schedule[candidates[0].key]
		event = &nextEvent{Session: readable[candidates[0].key], Date: *data.Date, Time: *data.Time, DateTime: *data.DateTime}
	}
	expires := now.Add(defaultExpire)
	if event != nil {
		expires = candidates[0].at
	} else if raceAt := rawSessionDateTimeFromConverted(selected.Schedule["race"]); !raceAt.IsZero() && now.Before(raceAt.Add(time.Hour)) {
		expires = raceAt.Add(time.Hour)
	}
	result := &nextRaceResponse{Season: year, Round: selected.Round, Timezone: a.config.timezoneID, NextEvent: event, CacheExpires: formatRFC3339(expires.In(a.config.timezone)), Race: []race{*selected}}
	a.cache.set("f1:next_race", result, expires)
	return result, nil
}

func (a *app) fetchSchedule(year int) ([]race, error) {
	var upstream struct {
		MRData struct {
			RaceTable struct {
				Races []struct {
					Round                     json.Number `json:"round"`
					RaceName, URL, Date, Time string
					Circuit                   struct {
						ID       string `json:"circuitId"`
						Name     string `json:"circuitName"`
						URL      string `json:"url"`
						Location struct{ Locality, Country string }
					} `json:"Circuit"`
					FirstPractice    *struct{ Date, Time string } `json:"FirstPractice"`
					SecondPractice   *struct{ Date, Time string } `json:"SecondPractice"`
					ThirdPractice    *struct{ Date, Time string } `json:"ThirdPractice"`
					Qualifying       *struct{ Date, Time string } `json:"Qualifying"`
					SprintQualifying *struct{ Date, Time string } `json:"SprintQualifying"`
					Sprint           *struct{ Date, Time string } `json:"Sprint"`
				} `json:"Races"`
			} `json:"RaceTable"`
		} `json:"MRData"`
	}
	if err := a.fetchJSON(fmt.Sprintf("%s/%d.json", a.config.ergastBase, year), &upstream); err != nil {
		return nil, err
	}
	result := make([]race, 0, len(upstream.MRData.RaceTable.Races))
	for _, item := range upstream.MRData.RaceTable.Races {
		schedule := map[string]sessionTime{}
		for _, key := range sessionKeys {
			schedule[key] = sessionTime{}
		}
		set := func(key string, value *struct{ Date, Time string }) {
			if value != nil {
				schedule[key] = makeSession(value.Date, value.Time)
			}
		}
		set("fp1", item.FirstPractice)
		set("fp2", item.SecondPractice)
		set("fp3", item.ThirdPractice)
		set("qualy", item.Qualifying)
		set("sprintQualy", item.SprintQualifying)
		set("sprintRace", item.Sprint)
		schedule["race"] = makeSession(item.Date, item.Time)
		id, name := item.Circuit.ID, item.Circuit.Name
		result = append(result, race{Round: numberInt(item.Round), RaceName: item.RaceName, URL: nullableString(item.URL), Schedule: schedule, Circuit: circuit{CircuitID: nullableString(id), CircuitName: name, URL: nullableString(item.Circuit.URL), Country: item.Circuit.Location.Country, City: item.Circuit.Location.Locality}})
	}
	sort.Slice(result, func(i, j int) bool {
		return rawSessionDateTime(result[i].Schedule["race"]).Before(rawSessionDateTime(result[j].Schedule["race"]))
	})
	return result, nil
}

func numberInt(value json.Number) int { result, _ := strconv.Atoi(value.String()); return result }
func numberFloat(value json.Number) float64 {
	result, _ := strconv.ParseFloat(value.String(), 64)
	return result
}
func nullableString(value string) *string {
	if value == "" {
		return nil
	}
	return &value
}
func allDigits(value string) bool {
	for _, char := range value {
		if char < '0' || char > '9' {
			return false
		}
	}
	return value != ""
}
func makeSession(date, clock string) sessionTime {
	return sessionTime{Date: nullableString(date), Time: nullableString(clock)}
}
func rawSessionDateTime(value sessionTime) time.Time {
	if value.Date == nil || value.Time == nil {
		return time.Time{}
	}
	parsed, _ := time.Parse("2006-01-02T15:04:05Z", *value.Date+"T"+*value.Time)
	return parsed
}
func rawSessionDateTimeFromConverted(value sessionTime) time.Time {
	if value.DateTime == nil {
		return time.Time{}
	}
	parsed, _ := time.Parse(time.RFC3339, *value.DateTime)
	return parsed
}
func formatRFC3339(value time.Time) string { return value.Format("2006-01-02T15:04:05-07:00") }
func sessionAllowed(detail, key string) bool {
	if detail == "detailed" {
		return true
	}
	if detail == "race" {
		return key == "race" || key == "sprintRace"
	}
	return key != "fp1" && key != "fp2" && key != "fp3"
}
