from retailedge.financial_dashboard import _period_comparison


def test_previous_zero_is_not_reported_as_fabricated_growth():
    result = _period_comparison(
        125000,
        {
            "available": True,
            "availability": "available",
            "reason": "",
            "payload": {"summary": [{"label": "Net Sales", "value": 0}]},
        },
        "Net Sales",
    )
    assert result["availability"] == "unavailable"
    assert result["label"] == "No comparable baseline"
    assert result["previous_value"] == 0


def test_previous_period_percentage_uses_absolute_previous_denominator():
    result = _period_comparison(
        120,
        {
            "available": True,
            "availability": "available",
            "reason": "",
            "payload": {"summary": [{"label": "Posted Expenses", "value": 100}]},
        },
        "Posted Expenses",
    )
    assert result["availability"] == "available"
    assert result["unit"] == "percent"
    assert result["value"] == 20
