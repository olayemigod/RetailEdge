(function installRetailEdgeBusinessHubRouteBridge(global) {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const MAX_ATTEMPTS = 40;
	const RETRY_MS = 150;
	const GUIDED_CREATE_EVENT = "retailedge-open-guided-create";
	const SIMPLE_MASTER_DOCTYPES = new Set(["Customer", "Supplier", "Item"]);
	const state = {
		attempts: 0,
		booted: false,
		lastError: null,
		lastWrapperSource: "",
	};

	function isActiveRoute() {
		const route = global.frappe?.get_route?.();
		return Array.isArray(route) && route[0] === PAGE_NAME;
	}

	function resolveWrapper() {
		const definition = global.frappe?.pages?.[PAGE_NAME];
		if (definition instanceof global.HTMLElement && definition.isConnected) {
			state.lastWrapperSource = "frappe.pages page container";
			return definition;
		}

		const selectors = [
			`.page-container[data-page-route="${PAGE_NAME}"]`,
			`.page-container[data-page-name="${PAGE_NAME}"]`,
			`[data-page-route="${PAGE_NAME}"]`,
			`[data-page-name="${PAGE_NAME}"]`,
			`.page-container[data-route="${PAGE_NAME}"]`,
		];
		for (const selector of selectors) {
			const matchedNode = global.document?.querySelector(selector);
			if (matchedNode?.isConnected) {
				state.lastWrapperSource = selector;
				return matchedNode;
			}
		}
		return null;
	}

	function getMountedProxy(wrapper) {
		return wrapper?._retailedgeBusinessHub?._instance?.proxy || null;
	}

	function normalizeSearchText(value) {
		return String(value || "")
			.normalize?.("NFKD")
			.replace(/[\u0300-\u036f]/g, "")
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, " ")
			.trim();
	}

	function editDistance(left, right) {
		const a = normalizeSearchText(left);
		const b = normalizeSearchText(right);
		if (a === b) return 0;
		if (!a.length) return b.length;
		if (!b.length) return a.length;
		let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
		for (let i = 1; i <= a.length; i += 1) {
			const current = [i];
			for (let j = 1; j <= b.length; j += 1) {
				const substitution = previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1);
				current[j] = Math.min(previous[j] + 1, current[j - 1] + 1, substitution);
			}
			previous = current;
		}
		return previous[b.length];
	}

	function isSubsequence(needle, haystack) {
		let index = 0;
		for (const character of haystack) {
			if (character === needle[index]) index += 1;
			if (index === needle.length) return true;
		}
		return false;
	}

	function tokenScore(token, haystack, words) {
		if (!token) return 0;
		if (words.includes(token)) return 140;
		if (words.some((word) => word.startsWith(token))) return 120;
		if (haystack.includes(token)) return 100;
		const tolerance = token.length >= 8 ? 2 : token.length >= 4 ? 1 : 0;
		if (tolerance && words.some((word) => Math.abs(word.length - token.length) <= tolerance && editDistance(token, word) <= tolerance)) {
			return 80;
		}
		if (token.length >= 3 && words.some((word) => isSubsequence(token, word))) return 55;
		return 0;
	}

	function fuzzyActionScore(query, action) {
		const normalizedQuery = normalizeSearchText(query);
		if (!normalizedQuery) return 1;
		const haystack = normalizeSearchText([
			action?.label,
			action?.description,
			action?.key,
			action?.doctype,
			action?.mode,
			action?.experience,
		].filter(Boolean).join(" "));
		if (!haystack) return 0;
		if (haystack.includes(normalizedQuery)) return 1000 - Math.min(500, haystack.indexOf(normalizedQuery));
		const words = haystack.split(/\s+/).filter(Boolean);
		const tokens = normalizedQuery.split(/\s+/).filter(Boolean);
		let score = 0;
		for (const token of tokens) {
			const current = tokenScore(token, haystack, words);
			if (!current) return 0;
			score += current;
		}
		return score;
	}

	function applyGuidedCreateSearch(list, proxy, query) {
		const actions = Array.isArray(proxy?.quickActions) ? proxy.quickActions : [];
		const buttons = Array.from(list.querySelectorAll(":scope > .create-picker-item"));
		let visibleCount = 0;
		buttons.forEach((button, index) => {
			const action = actions[index] || {
				label: button.querySelector("strong")?.textContent || button.textContent,
				description: button.querySelector("small")?.textContent || "",
			};
			const score = fuzzyActionScore(query, action);
			button.hidden = score <= 0;
			button.style.order = query && score > 0 ? String(-score) : "";
			if (score > 0) visibleCount += 1;
		});
		const empty = list.querySelector(":scope > .guided-create-search-empty");
		if (empty) {
			empty.hidden = !query || visibleCount > 0;
			empty.textContent = query ? `No guided entries match “${query}”. Try another word.` : "";
		}
		const count = list.querySelector(":scope > .guided-create-search-count");
		if (count) count.textContent = query ? `${visibleCount} of ${buttons.length}` : `${buttons.length} entries`;
	}

	function enhanceGuidedCreateList(list, wrapper) {
		if (!list || list.dataset.retailedgeFuzzySearch === "1") return false;
		const proxy = getMountedProxy(wrapper);
		if (!proxy) return false;
		list.dataset.retailedgeFuzzySearch = "1";

		const search = global.document.createElement("div");
		search.className = "guided-create-search";
		search.style.order = "-1000000";
		search.innerHTML = `
			<label class="edge-field guided-create-search-field">
				<span class="edge-field-label">Find an entry</span>
				<input type="search" class="edge-input guided-create-search-input" placeholder="Search sales, payment, stock, customer…" autocomplete="off" aria-label="Search guided entries" />
			</label>
			<small class="guided-create-search-count" aria-live="polite"></small>`;
		list.prepend(search);

		const empty = global.document.createElement("div");
		empty.className = "guided-create-search-empty";
		empty.hidden = true;
		empty.style.order = "1000000";
		empty.setAttribute("role", "status");
		list.appendChild(empty);

		const input = search.querySelector(".guided-create-search-input");
		input?.addEventListener("input", () => applyGuidedCreateSearch(list, proxy, input.value));
		input?.addEventListener("keydown", (event) => {
			if (event.key !== "Enter") return;
			const visible = Array.from(list.querySelectorAll(":scope > .create-picker-item:not([hidden])"));
			if (visible.length === 1) {
				event.preventDefault();
				visible[0].click();
			}
		});
		applyGuidedCreateSearch(list, proxy, "");
		global.setTimeout(() => input?.focus(), 0);
		return true;
	}

	function installGuidedCreateSearch(wrapper) {
		const root = wrapper?._retailedgeBusinessHubRoot?.[0];
		if (!root) return false;
		const enhance = () => {
			root.querySelectorAll(".create-picker-list").forEach((list) => enhanceGuidedCreateList(list, wrapper));
		};
		enhance();
		if (root.__retailedgeGuidedCreateSearchObserver) return true;
		const observer = new MutationObserver(enhance);
		observer.observe(root, { childList: true, subtree: true });
		root.__retailedgeGuidedCreateSearchObserver = observer;
		return true;
	}

	function launchMasterQuickEntry(action) {
		const doctype = action?.doctype;
		if (!SIMPLE_MASTER_DOCTYPES.has(doctype)) return false;
		if (!global.frappe?.ui?.form?.make_quick_entry || !global.frappe?.model?.get_new_doc) {
			global.frappe?.new_doc?.(doctype);
			return true;
		}
		const doc = global.frappe.model.get_new_doc(doctype, null, null, true);
		global.frappe.ui.form.make_quick_entry(
			doctype,
			(created) => {
				if (created?.name) {
					global.frappe.show_alert?.({
						message: `${action.label || doctype} ${created.name} created`,
						indicator: "green",
					});
				}
			},
			null,
			doc,
			true
		);
		return true;
	}

	function installMasterQuickEntryBridge(wrapper) {
		const proxy = getMountedProxy(wrapper);
		if (!proxy || proxy.__retailedgeMasterQuickEntryBridge) return Boolean(proxy);
		const originalRunQuickAction = proxy.runQuickAction?.bind(proxy);
		const originalActionModeLabel = proxy.actionModeLabel?.bind(proxy);
		if (typeof originalRunQuickAction !== "function") return false;

		proxy.runQuickAction = (action) => {
			if (action?.master_entry && SIMPLE_MASTER_DOCTYPES.has(action.doctype)) {
				proxy.closeCreatePicker?.();
				return launchMasterQuickEntry(action);
			}
			return originalRunQuickAction(action);
		};
		proxy.actionModeLabel = (action) => {
			if (action?.master_entry && SIMPLE_MASTER_DOCTYPES.has(action.doctype)) return "Quick entry";
			return typeof originalActionModeLabel === "function" ? originalActionModeLabel(action) : "Full form";
		};
		proxy.__retailedgeMasterQuickEntryBridge = true;
		return true;
	}

	function openPendingGuidedCreate(wrapper, attempt = 0) {
		if (!global.__retailedgeOpenGuidedCreate || !isActiveRoute()) return false;
		const proxy = getMountedProxy(wrapper);
		if (proxy && typeof proxy.openCreatePicker === "function") {
			global.__retailedgeOpenGuidedCreate = false;
			proxy.openCreatePicker();
			installGuidedCreateSearch(wrapper);
			return true;
		}
		if (attempt < MAX_ATTEMPTS) {
			global.setTimeout(() => openPendingGuidedCreate(wrapper, attempt + 1), RETRY_MS);
		}
		return false;
	}

	function requestGuidedCreate() {
		global.__retailedgeOpenGuidedCreate = true;
		if (!isActiveRoute()) return false;
		const wrapper = resolveWrapper();
		if (!wrapper) return false;
		return openPendingGuidedCreate(wrapper);
	}

	function bootActiveRoute() {
		if (!isActiveRoute()) {
			state.attempts = 0;
			state.booted = false;
			state.lastWrapperSource = "";
			global.retailedgeTeardownBusinessHubPage?.();
			return false;
		}

		state.attempts += 1;
		try {
			global.retailedgeRegisterBusinessHubPage?.();
			const wrapper = resolveWrapper();
			if (!wrapper) {
				if (state.attempts < MAX_ATTEMPTS) {
					global.setTimeout(bootActiveRoute, RETRY_MS);
				}
				return false;
			}

			global.retailedgeBootProductMenu?.();
			const pending = global.retailedgeBootBusinessHubPage?.(wrapper);
			Promise.resolve(pending).finally(() => {
				installMasterQuickEntryBridge(wrapper);
				installGuidedCreateSearch(wrapper);
				openPendingGuidedCreate(wrapper);
			});
			state.booted = true;
			state.lastError = null;
			return pending || true;
		} catch (error) {
			state.booted = false;
			state.lastError = error;
			console.error("[RetailEdge Business Hub Route Bridge] boot failed", error);
			if (state.attempts < MAX_ATTEMPTS) {
				global.setTimeout(bootActiveRoute, RETRY_MS);
			}
			return false;
		}
	}

	function scheduleBoot() {
		global.requestAnimationFrame?.(bootActiveRoute) || global.setTimeout(bootActiveRoute, 0);
	}

	["DOMContentLoaded", "page-change", "desktop_screen", "sidebar_setup"].forEach((eventName) => {
		global.document?.addEventListener(eventName, scheduleBoot);
	});
	global.document?.addEventListener(GUIDED_CREATE_EVENT, requestGuidedCreate);
	global.frappe?.router?.on?.("change", scheduleBoot);

	global.retailedgeBusinessHubRouteBridge = {
		boot: bootActiveRoute,
		openGuidedCreate: requestGuidedCreate,
		state,
	};

	scheduleBoot();
})(window);