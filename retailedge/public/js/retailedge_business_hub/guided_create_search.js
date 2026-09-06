const LIST_SELECTOR = ".create-picker-list";
const ITEM_SELECTOR = ".create-picker-item";
const SEARCH_MARKER = "data-retailedge-guided-create-search";
const EMPTY_MARKER = "data-retailedge-guided-create-empty";

function normalized(value) {
	return String(value || "")
		.trim()
		.toLowerCase()
		.replace(/\s+/g, " ");
}

function actionButtons(list) {
	return Array.from(list?.querySelectorAll?.(ITEM_SELECTOR) || []);
}

function actionMatches(button, query) {
	if (!query) return true;
	return normalized(button?.textContent).includes(query);
}

function createSearchUi(document, list) {
	let search = list.querySelector(`[${SEARCH_MARKER}]`);
	let empty = list.querySelector(`[${EMPTY_MARKER}]`);
	if (search && empty) return { search, empty };

	search?.remove();
	empty?.remove();

	search = document.createElement("div");
	search.className = "guided-create-search";
	search.setAttribute(SEARCH_MARKER, "1");
	search.innerHTML = `
		<label class="guided-create-search-field">
			<span class="edge-field-label">Search Create</span>
			<input
				type="search"
				class="guided-create-search-input"
				placeholder="Search permitted entries"
				aria-label="Search permitted Create entries"
				autocomplete="off"
			/>
		</label>
		<span class="guided-create-search-count" aria-live="polite"></span>
	`;

	empty = document.createElement("div");
	empty.className = "guided-create-search-empty";
	empty.setAttribute(EMPTY_MARKER, "1");
	empty.hidden = true;
	empty.textContent = "No permitted Create entry matches your search.";

	list.prepend(search);
	list.append(empty);
	return { search, empty };
}

function enhanceCreateList(target, list) {
	if (!list?.isConnected) return;
	const document = target.document;
	const { search, empty } = createSearchUi(document, list);
	const input = search.querySelector(".guided-create-search-input");
	const count = search.querySelector(".guided-create-search-count");
	if (!input || !count) return;

	const applyFilter = () => {
		const query = normalized(input.value);
		const buttons = actionButtons(list);
		let visibleCount = 0;
		for (const button of buttons) {
			const visible = actionMatches(button, query);
			button.hidden = !visible;
			if (visible) visibleCount += 1;
		}
		count.textContent = query
			? `${visibleCount} of ${buttons.length} entries`
			: `${buttons.length} permitted entr${buttons.length === 1 ? "y" : "ies"}`;
		empty.hidden = !query || visibleCount > 0;
	};

	if (input.dataset.retailedgeGuidedCreateBound !== "1") {
		input.dataset.retailedgeGuidedCreateBound = "1";
		input.addEventListener("input", applyFilter);
		input.addEventListener("keydown", (event) => {
			if (event.key !== "Escape" || !input.value) return;
			event.preventDefault();
			event.stopPropagation();
			input.value = "";
			applyFilter();
		});
	}

	applyFilter();
	if (!search.dataset.retailedgeGuidedCreateFocused) {
		search.dataset.retailedgeGuidedCreateFocused = "1";
		const schedule = target.requestAnimationFrame || ((callback) => target.setTimeout?.(callback, 0));
		schedule?.(() => {
			if (!list.isConnected || document.activeElement === input) return;
			input.focus?.({ preventScroll: true });
		});
	}
}

export function installGuidedCreateSearch(target = globalThis) {
	const document = target?.document;
	if (!document?.body || typeof target.MutationObserver !== "function") return () => {};

	let destroyed = false;
	const scan = () => {
		if (destroyed) return;
		for (const list of document.querySelectorAll(LIST_SELECTOR)) {
			enhanceCreateList(target, list);
		}
	};

	const observer = new target.MutationObserver(scan);
	observer.observe(document.body, { childList: true, subtree: true });
	scan();

	return () => {
		destroyed = true;
		observer.disconnect();
		for (const list of document.querySelectorAll(LIST_SELECTOR)) {
			for (const button of actionButtons(list)) button.hidden = false;
			list.querySelector(`[${SEARCH_MARKER}]`)?.remove();
			list.querySelector(`[${EMPTY_MARKER}]`)?.remove();
		}
	};
}

export { actionMatches, normalized };
