import pytest

from scrape import normalize_city, parse_profile_url


class TestNormalizeCity:
    @pytest.mark.parametrize("input_city, expected", [
        ("Seattle", "Seattle"),
        ("Seattle, WA", "Seattle"),
        ("Seattle WA", "Seattle"),
        ("Las Vegas, NV 89101", "Las Vegas"),
        ("Paris", "Paris"),
        ("New York, NY", "New York"),
        ("Portland OR", "Portland"),
        ("Seattle, Washington", "Seattle"),
        ("Kent WA", "Kent"),
        ("Lyon, Auvergne-Rhône-Alpes", "Lyon"),
        ("Paris, Île-de-France", "Paris"),
        ("West Valley City, UT", "West Valley City"),
        ("Tacoma, WA", "Tacoma"),
        ("Auburn, WA", "Auburn"),
    ])
    def test_normalize_city(self, input_city, expected):
        assert normalize_city(input_city) == expected

    def test_plain_city_unchanged(self):
        assert normalize_city("London") == "London"

    def test_non_us_state_abbreviation_preserved(self):
        """Two-letter suffix that isn't a US state should be kept (no comma case)."""
        assert normalize_city("Some Place ZZ") == "Some Place ZZ"


class TestParseProfileUrl:
    def test_events_url(self):
        assert parse_profile_url("https://www.last.fm/user/mazman159/events") == "mazman159"

    def test_profile_url(self):
        assert parse_profile_url("https://www.last.fm/user/mazman159") == "mazman159"

    def test_no_www(self):
        assert parse_profile_url("https://last.fm/user/testuser") == "testuser"

    def test_invalid_url(self):
        with pytest.raises(ValueError):
            parse_profile_url("https://example.com/user/test")
