package main

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

const scheduleJSON = `{"MRData":{"RaceTable":{"Races":[{"round":"3","raceName":"Test Grand Prix","url":"https://example.test/race","Circuit":{"circuitId":"monaco","circuitName":"Circuit de Monaco","url":"https://example.test/circuit","Location":{"locality":"Monte Carlo","country":"Monaco"}},"date":"2026-03-08","time":"15:00:00Z","FirstPractice":{"date":"2026-03-06","time":"12:00:00Z"},"SecondPractice":{"date":"2026-03-06","time":"16:00:00Z"},"ThirdPractice":{"date":"2026-03-07","time":"11:00:00Z"},"Qualifying":{"date":"2026-03-07","time":"15:00:00Z"}}]}}}`

type upstreamMock struct {
	server *httptest.Server
	mu     sync.Mutex
	hits   map[string]int
	locked bool
}

func newUpstreamMock(t *testing.T) *upstreamMock {
	t.Helper()
	mock := &upstreamMock{hits: make(map[string]int)}
	mock.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mock.mu.Lock()
		mock.hits[r.URL.Path]++
		locked := mock.locked
		mock.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if locked && strings.HasPrefix(r.URL.Path, "/openf1/") {
			w.WriteHeader(http.StatusUnauthorized)
			io.WriteString(w, `{"detail":"Live F1 session in progress."}`)
			return
		}
		switch r.URL.Path {
		case "/ergast/2026/driverStandings.json":
			io.WriteString(w, `{"MRData":{"StandingsTable":{"StandingsLists":[{"DriverStandings":[{"position":"1","points":"100.5","Driver":{"familyName":"Verstappen","nationality":"Dutch"},"Constructors":[{"constructorId":"red_bull"}]}]}]}}}`)
		case "/ergast/2026/constructorStandings.json":
			io.WriteString(w, `{"MRData":{"StandingsTable":{"StandingsLists":[{"ConstructorStandings":[{"position":1,"points":150,"wins":3,"country":"Great Britain","flag":"gb","Constructor":{"name":"McLaren","nationality":"British","url":"https://example.test/mclaren"}}]}]}}}`)
		case "/ergast/current/last/results.json":
			io.WriteString(w, `{"MRData":{"RaceTable":{"Races":[{"season":"2026","round":"2","raceName":"Previous Grand Prix","url":"https://example.test/previous-race","date":"2026-02-22","Results":[{"position":"1","positionText":"1","laps":"57","Time":{"time":"1:30:00.000"},"Driver":{"familyName":"Verstappen","nationality":"Dutch"},"Constructor":{"constructorId":"red_bull"}},{"position":"20","positionText":"R","laps":"12","Driver":{"familyName":"Kimi Antonelli","nationality":"Italian"},"Constructor":{"constructorId":"mercedes"}}]}]}}}`)
		case "/ergast/2026.json":
			io.WriteString(w, scheduleJSON)
		case "/openf1/sessions":
			io.WriteString(w, `[{"session_key":101,"session_name":"Practice 1","date_start":"2026-03-06T12:00:00Z","date_end":"2026-03-06T12:45:00Z"},{"session_key":102,"session_name":"Qualifying","date_start":"2026-03-07T15:00:00Z","date_end":"2026-03-07T15:45:00Z"}]`)
		case "/openf1/drivers":
			io.WriteString(w, `[{"driver_number":1,"name_acronym":"VER","last_name":"Verstappen","team_name":"Red Bull Racing"},{"driver_number":2,"name_acronym":"NOR","last_name":"Norris","team_name":"McLaren"},{"driver_number":3,"name_acronym":"HAM","last_name":"Hamilton","team_name":"Ferrari"}]`)
		case "/openf1/session_result":
			io.WriteString(w, `[{"position":2,"driver_number":2,"duration":77.9,"gap_to_leader":0.162,"number_of_laps":22,"dnf":false,"dns":false,"dsq":false},{"position":1,"driver_number":1,"duration":77.738,"gap_to_leader":0,"number_of_laps":24,"dnf":false,"dns":false,"dsq":false},{"position":3,"driver_number":3,"duration":null,"gap_to_leader":null,"number_of_laps":3,"dnf":true,"dns":false,"dsq":false}]`)
		case "/openf1/stints":
			io.WriteString(w, `[{"driver_number":1,"stint_number":1,"compound":"MEDIUM","lap_start":1,"lap_end":10}]`)
		case "/geometry/mc-1929.geojson":
			io.WriteString(w, `{"features":[{"geometry":{"coordinates":[[7.42,43.73],[7.43,43.73],[7.43,43.74],[7.42,43.73]]},"properties":{"Name":"Monaco"}}]}`)
		default:
			http.Error(w, r.URL.String(), http.StatusNotFound)
		}
	}))
	t.Cleanup(mock.server.Close)
	return mock
}

func testApp(t *testing.T, mock *upstreamMock) *app {
	t.Helper()
	staticDir := t.TempDir()
	return &app{
		config: config{timezone: time.FixedZone("Test", -7*60*60), timezoneID: "America/Edmonton", eventDetail: "main", trackColour: "#e5d486", ergastBase: mock.server.URL + "/ergast", openF1Base: mock.server.URL + "/openf1", geometryBase: mock.server.URL + "/geometry", staticMapDir: staticDir},
		client: mock.server.Client(), cache: newCache(), now: func() time.Time { return time.Date(2026, 3, 6, 13, 0, 0, 0, time.UTC) }, log: slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
}

func request(t *testing.T, server http.Handler, path string) *httptest.ResponseRecorder {
	t.Helper()
	recorder := httptest.NewRecorder()
	server.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, path, nil))
	if recorder.Code != http.StatusOK {
		t.Fatalf("GET %s = %d: %s", path, recorder.Code, recorder.Body.String())
	}
	return recorder
}

func decode(t *testing.T, recorder *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var result map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	return result
}

func TestDriversContractAndCache(t *testing.T) {
	mock := newUpstreamMock(t)
	server := newServer(testApp(t, mock))
	result := decode(t, request(t, server, "/f1/drivers_standings/"))
	driver := result["drivers"].([]any)[0].(map[string]any)
	if result["season"] != float64(2026) || driver["position"] != float64(1) || driver["points"] != 100.5 || driver["teamId"] != "Red Bull" || driver["country"] != "Netherlands" || driver["flag"] != "nl" {
		t.Fatalf("unexpected response: %#v", result)
	}
	request(t, server, "/f1/drivers_standings")
	if mock.hits["/ergast/2026/driverStandings.json"] != 1 {
		t.Fatal("cache miss on second request")
	}
}

func TestConstructorsContract(t *testing.T) {
	mock := newUpstreamMock(t)
	result := decode(t, request(t, newServer(testApp(t, mock)), "/f1/constructors_standings/"))
	item := result["constructors"].([]any)[0].(map[string]any)
	if item["position"] != float64(1) || item["points"] != float64(150) || item["wins"] != float64(3) || item["country"] != "Great Britain" || item["flag"] != "gb" {
		t.Fatalf("unexpected response: %#v", result)
	}
}

func TestLastRaceContract(t *testing.T) {
	mock := newUpstreamMock(t)
	result := decode(t, request(t, newServer(testApp(t, mock)), "/f1/last_race/"))
	items := result["results"].([]any)
	winner, retired := items[0].(map[string]any), items[1].(map[string]any)
	if result["season"] != float64(2026) || result["round"] != float64(2) || result["url"] != "https://example.test/previous-race" || winner["time"] != "1:30:00.000" || winner["country"] != "Netherlands" || winner["dnf_laps"] != nil || retired["surname"] != "Antonelli" || retired["time"] != "DNF (12)" || retired["dnf_laps"] != float64(12) {
		t.Fatalf("unexpected response: %#v", result)
	}
}

func TestNextRaceContract(t *testing.T) {
	mock := newUpstreamMock(t)
	result := decode(t, request(t, newServer(testApp(t, mock)), "/f1/next_race/"))
	event := result["next_event"].(map[string]any)
	race := result["race"].([]any)[0].(map[string]any)
	schedule := race["schedule"].(map[string]any)
	circuit := race["circuit"].(map[string]any)
	if result["round"] != float64(3) || result["timezone"] != "America/Edmonton" || event["session"] != "Qualifying" || event["time"] != "8:00AM" || schedule["sprintQualy"].(map[string]any)["date"] != nil || race["url"] != "https://example.test/race" || circuit["url"] != "https://example.test/circuit" {
		t.Fatalf("unexpected response: %#v", result)
	}
}

func TestTyreUsageContractAllSevenKeys(t *testing.T) {
	mock := newUpstreamMock(t)
	a := testApp(t, mock)
	a.now = func() time.Time { return time.Date(2026, 3, 6, 13, 0, 0, 0, time.UTC) }
	result := decode(t, request(t, newServer(a), "/f1/tyre_usage/"))
	sessions := result["sessions"].(map[string]any)
	if len(sessions) != 7 || sessions["fp1"] == nil || sessions["fp2"] != nil || sessions["fp3"] != nil || sessions["qualy"] != nil || sessions["sprintQualy"] != nil || sessions["sprintRace"] != nil || sessions["race"] != nil {
		t.Fatalf("unexpected sessions: %#v", sessions)
	}
	stint := sessions["fp1"].([]any)[0].(map[string]any)["stints"].([]any)[0].(map[string]any)
	if stint["compound"] != "MEDIUM" || stint["laps"] != float64(10) {
		t.Fatalf("unexpected stint: %#v", stint)
	}
}

func TestNextMapStaticAndDynamicContract(t *testing.T) {
	mock := newUpstreamMock(t)
	a := testApp(t, mock)
	server := newServer(a)
	dynamic := request(t, server, "/f1/next_map/")
	if dynamic.Header().Get("Content-Type") != "image/svg+xml" || !strings.Contains(dynamic.Body.String(), `xmlns="http://www.w3.org/2000/svg"`) || !strings.Contains(dynamic.Body.String(), "#e5d486") || !strings.Contains(dynamic.Body.String(), "Circuit de Monaco") {
		t.Fatalf("unexpected dynamic SVG: %s", dynamic.Body.String())
	}
	if err := os.WriteFile(filepath.Join(a.config.staticMapDir, "monaco.svg"), []byte(`<svg stroke="#e5d486">static</svg>`), 0o644); err != nil {
		t.Fatal(err)
	}
	a.config.trackColour = "#123456"
	static := request(t, server, "/f1/next_map")
	if !strings.Contains(static.Body.String(), "#123456") || !strings.Contains(static.Body.String(), "static") {
		t.Fatalf("unexpected static SVG: %s", static.Body.String())
	}
}

func TestLoadConfigValidation(t *testing.T) {
	t.Setenv("TIMEZONE", "UTC")
	t.Setenv("TRACK_COLOUR", "#abc")
	t.Setenv("EVENT_DETAIL", "")
	cfg, err := loadConfig()
	if err != nil || cfg.eventDetail != "main" {
		t.Fatalf("loadConfig() = %#v, %v", cfg, err)
	}
	t.Setenv("EVENT_DETAIL", "bad")
	if _, err := loadConfig(); err == nil {
		t.Fatal("invalid EVENT_DETAIL accepted")
	}
}

func TestTyreUsageKeepsFinishedSessionsThroughOpenF1Lockout(t *testing.T) {
	mock := newUpstreamMock(t)
	a := testApp(t, mock)
	server := newServer(a)
	first := decode(t, request(t, server, "/f1/tyre_usage/"))
	if first["sessions"].(map[string]any)["fp1"] == nil {
		t.Fatalf("expected fp1 before lockout: %#v", first)
	}
	mock.mu.Lock()
	mock.locked = true
	mock.mu.Unlock()
	a.now = func() time.Time { return time.Date(2026, 3, 6, 15, 0, 0, 0, time.UTC) }
	second := decode(t, request(t, server, "/f1/tyre_usage/"))
	if second["sessions"].(map[string]any)["fp1"] == nil || second["upstream_error"] != nil {
		t.Fatalf("finished session should survive the lockout: %#v", second)
	}
}

func TestTyreUsageSurfacesLockoutWhenNothingCached(t *testing.T) {
	mock := newUpstreamMock(t)
	mock.locked = true
	result := decode(t, request(t, newServer(testApp(t, mock)), "/f1/tyre_usage/"))
	if result["upstream_error"] == nil || result["sessions"].(map[string]any)["fp1"] != nil {
		t.Fatalf("expected upstream_error and no data: %#v", result)
	}
}

func TestTyreUsageStaysOnWeekendAfterRaceStarts(t *testing.T) {
	mock := newUpstreamMock(t)
	a := testApp(t, mock)
	a.now = func() time.Time { return time.Date(2026, 3, 8, 16, 0, 0, 0, time.UTC) }
	result := decode(t, request(t, newServer(a), "/f1/tyre_usage/"))
	if result["raceName"] != "Test Grand Prix" || result["sessions"].(map[string]any)["fp1"] == nil {
		t.Fatalf("expected the finished weekend to stay current: %#v", result)
	}
}

func TestLatestSessionContract(t *testing.T) {
	mock := newUpstreamMock(t)
	result := decode(t, request(t, newServer(testApp(t, mock)), "/f1/latest_session/"))
	rows := result["results"].([]any)
	first, second, third := rows[0].(map[string]any), rows[1].(map[string]any), rows[2].(map[string]any)
	if result["session"] != "Free Practice 1" || result["raceName"] != "Test Grand Prix" || first["surname"] != "Verstappen" || first["team"] != "Red Bull Racing" || first["time"] != "1:17.738" || second["time"] != "+0.162" || third["time"] != "DNF" {
		t.Fatalf("unexpected response: %#v", result)
	}
}

func TestLatestSessionExcludesRaceAndSurvivesLockout(t *testing.T) {
	mock := newUpstreamMock(t)
	a := testApp(t, mock)
	server := newServer(a)
	a.now = func() time.Time { return time.Date(2026, 3, 7, 17, 0, 0, 0, time.UTC) }
	request(t, server, "/f1/latest_session/")
	mock.mu.Lock()
	mock.locked = true
	mock.mu.Unlock()
	// Well after the race: the race itself must not become the latest session.
	a.now = func() time.Time { return time.Date(2026, 3, 9, 12, 0, 0, 0, time.UTC) }
	result := decode(t, request(t, server, "/f1/latest_session/"))
	if result["key"] == "race" || result["upstream_error"] != nil || len(result["results"].([]any)) != 3 {
		t.Fatalf("expected qualifying/practice data from cache, not the race: %#v", result)
	}
}

func TestNextRaceHandsOverWhenRaceEnds(t *testing.T) {
	mock := newUpstreamMock(t)
	a := testApp(t, mock)
	a.now = func() time.Time { return time.Date(2026, 3, 8, 16, 0, 0, 0, time.UTC) }
	during := decode(t, request(t, newServer(a), "/f1/next_race/"))
	if during["next_event"].(map[string]any)["session"] != "Race" {
		t.Fatalf("race in progress should still be the current event: %#v", during)
	}
	b := testApp(t, mock)
	b.now = func() time.Time { return time.Date(2026, 3, 8, 17, 30, 0, 0, time.UTC) }
	after := decode(t, request(t, newServer(b), "/f1/next_race/"))
	if after["message"] != "No upcoming race found" {
		t.Fatalf("finished race should hand over: %#v", after)
	}
}
