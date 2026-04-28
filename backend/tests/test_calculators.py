import math

import pytest

from app.services.analytics.calculators import (
    calculate_frost_hours,
    calculate_gdd,
    calculate_vpd,
)


class TestCalculateVPD:
    def test_known_value_at_25c_50rh(self) -> None:
        # es(25°C) = 0.6108 * exp(17.27 * 25 / (25 + 237.3)) ≈ 3.1690 kPa
        # VPD = es * (1 - 0.5) ≈ 1.5845 kPa
        result = calculate_vpd(25.0, 50.0)
        assert result is not None
        assert math.isclose(result, 1.5845, abs_tol=1e-3)

    def test_saturated_air_returns_zero(self) -> None:
        assert calculate_vpd(20.0, 100.0) == 0.0

    def test_dry_air_equals_es(self) -> None:
        es = 0.6108 * math.exp(17.27 * 20 / (20 + 237.3))
        result = calculate_vpd(20.0, 0.0)
        assert result is not None
        assert math.isclose(result, round(es, 4), abs_tol=1e-4)

    def test_returns_none_if_temp_missing(self) -> None:
        assert calculate_vpd(None, 60.0) is None

    def test_returns_none_if_humidity_missing(self) -> None:
        assert calculate_vpd(15.0, None) is None

    def test_result_rounded_to_4_decimals(self) -> None:
        result = calculate_vpd(25.0, 50.0)
        assert result is not None
        # No more than 4 decimals
        assert round(result, 4) == result


class TestCalculateGDD:
    def test_tomato_base_10(self) -> None:
        # mean = (15 + 25) / 2 = 20; GDD = 20 - 10 = 10
        assert calculate_gdd(15.0, 25.0, base_temp=10.0) == 10.0

    def test_cucumber_base_15(self) -> None:
        # mean = (10 + 30) / 2 = 20; GDD = 20 - 15 = 5
        assert calculate_gdd(10.0, 30.0, base_temp=15.0) == 5.0

    def test_cabbage_base_4(self) -> None:
        # mean = (2 + 12) / 2 = 7; GDD = 7 - 4 = 3
        assert calculate_gdd(2.0, 12.0, base_temp=4.0) == 3.0

    def test_clamped_to_zero_when_below_base(self) -> None:
        # mean = 5, base = 10 → -5 clamped to 0
        assert calculate_gdd(0.0, 10.0, base_temp=10.0) == 0.0
        assert calculate_gdd(-5.0, 5.0, base_temp=10.0) == 0.0

    def test_returns_none_if_temp_min_missing(self) -> None:
        assert calculate_gdd(None, 20.0, base_temp=10.0) is None

    def test_returns_none_if_temp_max_missing(self) -> None:
        assert calculate_gdd(5.0, None, base_temp=10.0) is None

    def test_returns_float(self) -> None:
        result = calculate_gdd(10.0, 20.0, base_temp=5.0)
        assert isinstance(result, float)


class TestCalculateFrostHours:
    def test_no_frost(self) -> None:
        assert calculate_frost_hours([1.0, 5.0, 10.0, 0.0]) == 0

    def test_all_frost(self) -> None:
        assert calculate_frost_hours([-1.0, -5.0, -0.1]) == 3

    def test_mixed(self) -> None:
        assert calculate_frost_hours([-2.0, 0.0, 3.0, -1.0, -0.5]) == 3

    def test_zero_is_not_frost(self) -> None:
        # Strict `< 0` threshold
        assert calculate_frost_hours([0.0, 0.0, 0.0]) == 0

    def test_skips_none_values(self) -> None:
        assert calculate_frost_hours([-1.0, None, -2.0, None]) == 2

    def test_empty_iterable(self) -> None:
        assert calculate_frost_hours([]) == 0

    def test_accepts_generator(self) -> None:
        gen = (t for t in [-1.0, 2.0, -3.0])
        assert calculate_frost_hours(gen) == 2


class TestCrossConsistencyWithOpenMeteoClient:
    """Ensure calculators match the inline implementations used in
    `services/weather/open_meteo.py` so we can later migrate the client
    to delegate to these without behavior change."""

    @pytest.mark.parametrize(
        ("temp", "rh"),
        [(25.0, 50.0), (10.0, 80.0), (-5.0, 90.0), (35.0, 20.0)],
    )
    def test_vpd_matches_tetens_inline(self, temp: float, rh: float) -> None:
        es = 0.6108 * math.exp(17.27 * temp / (temp + 237.3))
        expected = round(es * (1 - rh / 100), 4)
        assert calculate_vpd(temp, rh) == expected

    def test_frost_hours_matches_strict_lt_zero(self) -> None:
        samples = [-2.0, 8.0, -3.0, 5.0, 0.0, None]
        expected = sum(1 for t in samples if t is not None and t < 0)
        assert calculate_frost_hours(samples) == expected
