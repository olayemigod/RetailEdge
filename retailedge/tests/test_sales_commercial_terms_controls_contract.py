from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CONTROLS = (
	APP_ROOT
	/ "public"
	/ "js"
	/ "selling"
	/ "SalesCommercialTermsControls.vue"
)


def test_manual_discount_mode_remains_selectable_before_value_entry():
	source = CONTROLS.read_text(encoding="utf-8")

	# The selected mode must have local UI state. Deriving it only from a
	# non-zero discount makes Percentage / Fixed amount immediately collapse
	# back to No manual discount before the operator can enter a value.
	assert "selectedDiscountMode" in source
	assert "discountModeFromValues" in source
	assert 'this.selectedDiscountMode = next' in source
	assert 'this.selectedDiscountMode = "percentage"' in source
	assert 'this.selectedDiscountMode = "amount"' in source

	# Zero-value mode selection is only editing intent; it is not an applied
	# discount until a real percentage or amount is entered.
	assert 'Number(this.values.additional_discount_percentage || 0) > 0' in source
	assert 'Number(this.values.discount_amount || 0) > 0' in source
