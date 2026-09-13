from retailedge.action_prioritization import prioritise_action_items


def test_prioritisation_orders_severity_then_due_then_age():
	items = [
		{"label": "Warning old", "severity": "warning", "age_days": 90, "source": "bank", "follow_up": {}},
		{"label": "Critical new", "severity": "danger", "age_days": 2, "source": "stock", "follow_up": {}},
		{"label": "Critical due", "severity": "danger", "age_days": 1, "source": "cash", "follow_up": {"is_due": True}},
		{"label": "Critical older", "severity": "danger", "age_days": 30, "source": "bank", "follow_up": {}},
	]

	result = prioritise_action_items(items)
	assert [row["label"] for row in result] == ["Critical due", "Critical older", "Critical new", "Warning old"]
	assert result[0]["priority_reason"] == "Critical exception; follow-up due or overdue; 1 days old"


def test_financial_exposure_only_breaks_ties_for_comparable_financial_kinds():
	items = [
		{"label": "Receivables small", "severity": "warning", "kind": "overdue_receivables", "exposure": 1000, "age_days": 20, "source": "receivables"},
		{"label": "Receivables large", "severity": "warning", "kind": "overdue_receivables", "exposure": 5000, "age_days": 20, "source": "receivables"},
		{"label": "Five stock exceptions", "severity": "warning", "kind": "out_of_stock", "value": 5, "age_days": 20, "source": "stock"},
	]

	result = prioritise_action_items(items)
	assert [row["label"] for row in result[:2]] == ["Receivables large", "Receivables small"]
	assert "financial exposure present" in result[0]["priority_reason"]
	assert "financial exposure" not in result[2]["priority_reason"]


def test_prioritisation_does_not_mutate_input_rows_or_emit_numeric_score():
	items = [{"label": "Item", "severity": "warning", "source": "x", "follow_up": {}}]
	result = prioritise_action_items(items)
	assert "priority_reason" not in items[0]
	assert "priority_score" not in result[0]
