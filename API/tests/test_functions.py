from API_Endpoints.helpers.functions import country_to_code, format_team_name


def test_format_team_name_rb_exception():
    assert format_team_name("rb") == "RB"


def test_format_team_name_generic():
    assert format_team_name("red_bull") == "Red Bull"


def test_format_team_name_empty():
    assert format_team_name("") == ""
    assert format_team_name(None) == ""


def test_country_to_code_replacements():
    assert country_to_code("Great Britain") == "gb"
    assert country_to_code("United States") == "us"


def test_country_to_code_direct_lookup():
    assert country_to_code("Germany") == "de"


def test_country_to_code_unknown_falls_back_to_empty_string():
    assert country_to_code("Not A Real Country") == ""
