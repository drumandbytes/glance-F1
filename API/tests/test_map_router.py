from API_Endpoints.map.router import historical_event_matches, normalize_name


def test_normalize_name_strips_accents_and_case():
    assert normalize_name("Montréal") == normalize_name("montreal")
    assert normalize_name(" São Paulo ") == "sao paulo"
    assert normalize_name(None) == ""


def _event(**overrides):
    event = {"Location": "Spa-Francorchamps", "Country": "Belgium", "EventName": "Belgian Grand Prix"}
    event.update(overrides)
    return event


def test_matches_on_location_and_country():
    assert historical_event_matches(_event(), "Spa-Francorchamps", "Belgium", "Something Else")


def test_matches_on_event_name_alone():
    assert historical_event_matches(_event(Location="Different", Country="Different"), None, None, "Belgian Grand Prix")


def test_no_match_when_nothing_lines_up():
    assert not historical_event_matches(_event(), "Nowhere", "Nowhere", "Not This Race")


def test_location_alone_is_not_enough_without_matching_country():
    assert not historical_event_matches(_event(), "Spa-Francorchamps", "Wrong Country", None)


def test_accent_and_case_insensitive_matching():
    assert historical_event_matches(_event(Location="Montréal"), "montreal", "Belgium", None)
