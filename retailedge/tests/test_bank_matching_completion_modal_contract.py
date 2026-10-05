from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = APP_ROOT / "public/js/bank_matching_edgesuite_completion_adapter.js"


def source() -> str:
	return ADAPTER.read_text(encoding="utf-8")


def test_bank_review_completion_keeps_comparison_first():
	text = source()

	for expected in (
		'function placeCompletionSections(body, context, evidenceGrid, guidance)',
		'const compareGrid = body.querySelector(".retailedge-bank-compare-grid");',
		'const anchor = compareGrid?.nextSibling || recordLinks || null;',
		'body.insertBefore(context, anchor);',
		'body.insertBefore(evidenceGrid, anchor);',
		'body.insertBefore(guidance, anchor);',
	):
		assert expected in text

	assert text.index('placeCompletionSections(body, context, evidenceGrid, guidance);') < text.index(
		'modal.dataset.retailedgeCompletion = "1";'
	)


def test_bank_review_completion_waits_for_real_vue_review_body_on_reopen():
	text = source()

	for expected in (
		'const compareGrid = body.querySelector(".retailedge-bank-compare-grid");',
		'const recordLinks = body.querySelector(".retailedge-bank-record-links");',
		'if (!compareGrid || !recordLinks)',
		'Never inject completion sections into the temporary loading body.',
	):
		assert expected in text

	guard = text.index('if (!compareGrid || !recordLinks)')
	hydration = text.index('await hydrateOperational(matchName);')
	placement = text.index('placeCompletionSections(body, context, evidenceGrid, guidance);')
	assert guard < hydration < placement


def test_bank_review_viewport_resets_after_async_completion_only():
	text = source()

	for expected in (
		'function resetReviewViewportAfterEnhancement(modal)',
		'body.scrollTop = 0;',
		'body.scrollLeft = 0;',
		'raf(() => raf(reset));',
		'resetReviewViewportAfterEnhancement(modal);',
	):
		assert expected in text

	completion_call = text.rindex('resetReviewViewportAfterEnhancement(modal);')
	placement_call = text.index('placeCompletionSections(body, context, evidenceGrid, guidance);')
	assert placement_call < completion_call


def test_bank_review_completion_still_runs_once_per_modal_instance():
	text = source()

	assert 'modal.dataset.retailedgeCompletion === "1"' in text
	assert 'modal.dataset.retailedgeCompletion = "1";' in text