(function installRetailEdgeBankingPageEnhancements(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const IMPORT_DOCTYPE = "Bank Statement Import";
	const CREATE_IMPORT_METHOD = "retailedge.bank_statement_import.create_bank_statement_import";
	const PREVIEW_METHOD = "erpnext.accounts.doctype.bank_statement_import.bank_statement_import.get_preview_from_template";
	const START_IMPORT_METHOD = "erpnext.accounts.doctype.bank_statement_import.bank_statement_import.form_start_import";
	const IMPORT_STATUS_METHOD = "erpnext.accounts.doctype.bank_statement_import.bank_statement_import.get_import_status";
	const MT940_CONVERT_METHOD = "erpnext.accounts.doctype.bank_statement_import.bank_statement_import.convert_mt940_to_csv";
	const ALLOWED_FILE_EXTENSIONS = [".csv", ".xls", ".xlsx", ".txt"];
	let scheduled = false;

	if (global.retailedgeBankingPageEnhancementsInstalled) return;

	function clean(value) {
		return String(value ?? "").trim().replace(/\s+/g, " ");
	}

	function t(text, args) {
		return typeof global.__ === "function" ? global.__(text, args) : text;
	}

	function isBankingPage() {
		const route = global.frappe?.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function edgeRuntime() {
		return global.EdgeSuiteUI || global.EdgeUI || null;
	}

	function pageRoot() {
		return document.querySelector(".retailedge-bank-layout");
	}

	function findButton(root, labels) {
		const wanted = new Set(labels.map((label) => clean(t(label))));
		return Array.from(root?.querySelectorAll("button") || []).find((button) => wanted.has(clean(button.textContent))) || null;
	}

	function fieldInputByLabel(filterBar, wantedLabel) {
		const wanted = clean(t(wantedLabel));
		const labelNodes = Array.from(filterBar?.querySelectorAll("label, [class*='label']") || [])
			.filter((element) => clean(element.textContent) === wanted);
		for (const label of labelNodes) {
			let node = label;
			for (let depth = 0; depth < 6 && node; depth += 1, node = node.parentElement) {
				const input = node.querySelector?.("input");
				if (input) return input;
			}
		}
		return null;
	}

	function fieldValueByLabel(filterBar, wantedLabel) {
		return clean(fieldInputByLabel(filterBar, wantedLabel)?.value);
	}

	function setInputValue(input, value) {
		if (!input) return;
		const setter = Object.getOwnPropertyDescriptor(global.HTMLInputElement.prototype, "value")?.set;
		if (setter) setter.call(input, value || "");
		else input.value = value || "";
		input.dispatchEvent(new Event("input", { bubbles: true }));
		input.dispatchEvent(new Event("change", { bubbles: true }));
	}

	function removeFilterHeading(filterBar) {
		Array.from(filterBar?.querySelectorAll("*") || [])
			.filter((element) => element.children.length === 0 && clean(element.textContent) === clean(t("Filters")))
			.forEach((element) => element.remove());
	}

	function restyleReset(filterBar) {
		const reset = findButton(filterBar, ["Clear Filters", "Reset filters", "Reset Filters"]);
		if (!reset) return null;
		reset.textContent = t("Reset filters");
		reset.classList.add("retailedge-bank-reset-link");
		return reset;
	}

	async function permissionAwareLinkSearch(doctype, query, filters = {}) {
		const response = await global.frappe.call({
			method: "frappe.desk.search.search_link",
			args: {
				doctype,
				txt: clean(query),
				filters,
				page_length: 20,
			},
		});
		return (response?.message || []).map((row) => ({
			value: row.value || row.name,
			label: row.label || row.value || row.name,
			description: row.description || "",
		}));
	}

	function mountSmartDateRange(filterBar, resetButton) {
		if (filterBar.querySelector(".retailedge-bank-smart-date")) return;
		const runtime = edgeRuntime();
		const EdgeSmartDateRange = runtime?.getComponent?.("EdgeSmartDateRange");
		const host = document.createElement("div");
		host.className = "retailedge-bank-smart-date";
		const actionHost = resetButton?.parentElement || filterBar;
		if (resetButton && resetButton.parentElement === actionHost) actionHost.insertBefore(host, resetButton);
		else actionHost.appendChild(host);

		if (!EdgeSmartDateRange || !runtime?.Vue?.createApp) {
			host.classList.add("is-unavailable");
			host.textContent = t("Smart date requires the EdgeSuite Reporting Standard component.");
			return;
		}

		const { createApp, h, ref } = runtime.Vue;
		let applyingSmartDate = false;
		const app = createApp({
			setup() {
				const componentKey = ref(0);
				const resolvedValue = ref({});
				const reset = () => {
					resolvedValue.value = {};
					componentKey.value += 1;
				};
				host.__retailedgeResetSmartDate = reset;

				const applyResolvedDate = (value) => {
					if (!value?.from_date || !value?.to_date) return;
					resolvedValue.value = value;
					applyingSmartDate = true;
					try {
						setInputValue(fieldInputByLabel(filterBar, "From Date"), value.from_date);
						setInputValue(fieldInputByLabel(filterBar, "To Date"), value.to_date);
					} finally {
						setTimeout(() => { applyingSmartDate = false; }, 0);
					}
				};

				return () => h(EdgeSmartDateRange, {
					key: componentKey.value,
					modelValue: resolvedValue.value,
					label: t("Smart Date"),
					placeholder: t("e.g. last 7 days, last 90 days, YTD"),
					dateOrder: "DMY",
					"onUpdate:modelValue": (value) => { resolvedValue.value = value || {}; },
					onResolved: applyResolvedDate,
				});
			},
		});
		app.mount(host);

		for (const label of ["From Date", "To Date"]) {
			const input = fieldInputByLabel(filterBar, label);
			input?.addEventListener("change", () => {
				if (!applyingSmartDate) host.__retailedgeResetSmartDate?.();
			});
		}
		resetButton?.addEventListener("click", () => host.__retailedgeResetSmartDate?.());
	}

	function downloadTemplate() {
		if (typeof global.open_url_post !== "function") {
			global.frappe?.msgprint?.(t("The ERPNext template download service is unavailable."));
			return;
		}
		global.open_url_post("/api/method/frappe.core.doctype.data_import.data_import.download_template", {
			doctype: "Bank Transaction",
			export_records: "blank_template",
			export_fields: {
				"Bank Transaction": [
					"date",
					"deposit",
					"withdrawal",
					"description",
					"reference_number",
					"bank_account",
					"currency",
				],
			},
		});
	}

	function uploadFile(file, importName) {
		return new Promise((resolve, reject) => {
			const form = new FormData();
			form.append("file", file, file.name);
			form.append("is_private", "1");
			form.append("doctype", IMPORT_DOCTYPE);
			form.append("docname", importName);
			form.append("fieldname", "import_file");

			const xhr = new XMLHttpRequest();
			xhr.open("POST", "/api/method/upload_file", true);
			if (global.frappe?.csrf_token) xhr.setRequestHeader("X-Frappe-CSRF-Token", global.frappe.csrf_token);
			xhr.onload = () => {
				let payload = {};
				try {
					payload = JSON.parse(xhr.responseText || "{}");
				} catch (_error) {
					payload = {};
				}
				if (xhr.status >= 200 && xhr.status < 300 && payload.message?.file_url) {
					resolve(payload.message.file_url);
					return;
				}
				reject(new Error(payload.exception || payload.message || t("Unable to upload the bank statement file.")));
			};
			xhr.onerror = () => reject(new Error(t("Unable to upload the bank statement file.")));
			xhr.send(form);
		});
	}

	async function setImportField(importName, fieldname, value) {
		return global.frappe.call({
			method: "frappe.client.set_value",
			args: { doctype: IMPORT_DOCTYPE, name: importName, fieldname, value },
		});
	}

	function fileExtension(fileName) {
		const lower = String(fileName || "").toLowerCase();
		return ALLOWED_FILE_EXTENSIONS.find((extension) => lower.endsWith(extension)) || "";
	}

	function previewColumns(preview) {
		return (preview?.columns || []).map((column) => clean(column?.header_title || column?.label || column?.fieldname || column?.name || column)).filter(Boolean);
	}

	function previewRows(preview) {
		return (preview?.data || []).slice(0, 10).map((row) => {
			const data = Array.isArray(row) ? row : Array.isArray(row?.data) ? row.data : [];
			return data.map((cell) => clean(cell?.value ?? cell?.data ?? cell));
		});
	}

	function previewWarnings(preview) {
		const warnings = [];
		for (const warning of preview?.warnings || []) warnings.push(clean(warning?.message || warning));
		for (const column of preview?.columns || []) {
			for (const warning of column?.warnings || []) warnings.push(clean(warning?.message || warning));
		}
		return warnings.filter(Boolean);
	}

	function mountStatementImportModal(root) {
		let host = root.querySelector(".retailedge-bank-import-modal-host");
		if (host?.__retailedgeOpenStatementImport) return host;
		const runtime = edgeRuntime();
		const EdgeModal = runtime?.getComponent?.("EdgeModal");
		const EdgeLinkField = runtime?.getComponent?.("EdgeLinkField");
		const EdgeStatusBadge = runtime?.getComponent?.("EdgeStatusBadge");
		if (!runtime?.Vue?.createApp || !EdgeModal || !EdgeLinkField) return null;

		host = document.createElement("div");
		host.className = "retailedge-bank-import-modal-host";
		root.appendChild(host);
		const { createApp, h, reactive } = runtime.Vue;

		createApp({
			setup() {
				const state = reactive({
					open: false,
					busy: false,
					company: "",
					bankAccount: "",
					file: null,
					fileName: "",
					importName: "",
					importContextKey: "",
					preview: null,
					status: "",
					statusDetail: "",
					error: "",
					importStarted: false,
				});

				function resetState(context = {}) {
					state.company = clean(context.company);
					state.bankAccount = clean(context.bankAccount);
					state.file = null;
					state.fileName = "";
					state.importName = "";
					state.importContextKey = "";
					state.preview = null;
					state.status = "";
					state.statusDetail = "";
					state.error = "";
					state.importStarted = false;
					state.busy = false;
					state.open = true;
				}
				host.__retailedgeOpenStatementImport = resetState;

				function close() {
					if (!state.busy) state.open = false;
				}

				function onFileChange(event) {
					const file = event.target.files?.[0] || null;
					state.error = "";
					state.preview = null;
					state.importStarted = false;
					state.status = "";
					state.file = file;
					state.fileName = file?.name || "";
					if (file && !fileExtension(file.name)) {
						state.error = t("Use a CSV, XLS, XLSX, or TXT (MT940) bank statement file.");
					}
				}

				async function ensureImportDraft() {
					const contextKey = `${state.company}::${state.bankAccount}`;
					if (state.importName && state.importContextKey === contextKey) return state.importName;
					const response = await global.frappe.call({
						method: CREATE_IMPORT_METHOD,
						args: { company: state.company, bank_account: state.bankAccount },
					});
					state.importName = response?.message?.name || "";
					state.importContextKey = contextKey;
					if (!state.importName) throw new Error(t("ERPNext did not create a Bank Statement Import draft."));
					return state.importName;
				}

				async function preparePreview() {
					state.error = "";
					if (!state.company || !state.bankAccount || !state.file) {
						state.error = t("Select Company, Bank Account, and a statement file before previewing.");
						return;
					}
					if (!fileExtension(state.file.name)) {
						state.error = t("Use a CSV, XLS, XLSX, or TXT (MT940) bank statement file.");
						return;
					}
					state.busy = true;
					try {
						const importName = await ensureImportDraft();
						let fileUrl = await uploadFile(state.file, importName);
						if (fileExtension(state.file.name) === ".txt") {
							await setImportField(importName, "import_mt940_fromat", 1);
							await setImportField(importName, "import_file", fileUrl);
							const converted = await global.frappe.call({
								method: MT940_CONVERT_METHOD,
								args: { data_import: importName, mt940_file_path: fileUrl },
							});
							fileUrl = converted?.message || fileUrl;
						}
						await setImportField(importName, "import_file", fileUrl);
						const previewResponse = await global.frappe.call({
							method: PREVIEW_METHOD,
							args: { data_import: importName, import_file: fileUrl },
						});
						state.preview = previewResponse?.message || {};
						state.status = t("Ready to import");
						state.statusDetail = t("ERPNext validated the statement preview. Review it before starting import.");
					} catch (error) {
						state.error = error?.message || t("Unable to prepare the bank statement preview.");
					} finally {
						state.busy = false;
					}
				}

				async function checkImportStatus() {
					if (!state.importName) return;
					try {
						const response = await global.frappe.call({
							method: IMPORT_STATUS_METHOD,
							args: { docname: state.importName },
						});
						const result = response?.message || {};
						state.status = result.status || state.status || t("Import queued");
						const success = Number(result.success || 0);
						const failed = Number(result.failed || 0);
						const total = Number(result.total_records || 0);
						state.statusDetail = total
							? t("{0} of {1} imported; {2} failed.", [success, total, failed])
							: t("ERPNext is processing the statement import.");
						if (["Success", "Partial Success", "Error"].includes(result.status)) {
							findButton(root, ["Refresh"])?.click();
							return;
						}
						setTimeout(checkImportStatus, 2000);
					} catch (_error) {
						state.statusDetail = t("Import started. Use Check Status to refresh the ERPNext import result.");
					}
				}

				async function startImport() {
					if (!state.preview || !state.importName) return;
					state.busy = true;
					state.error = "";
					try {
						await global.frappe.call({ method: START_IMPORT_METHOD, args: { data_import: state.importName } });
						state.importStarted = true;
						state.status = t("Import queued");
						state.statusDetail = t("ERPNext is importing Bank Transactions. Matching and reconciliation remain separate actions.");
						setTimeout(checkImportStatus, 700);
					} catch (error) {
						state.error = error?.message || t("Unable to start the ERPNext bank statement import.");
					} finally {
						state.busy = false;
					}
				}

				function renderPreview() {
					if (!state.preview) return null;
					const columns = previewColumns(state.preview);
					const rows = previewRows(state.preview);
					const warnings = previewWarnings(state.preview);
					return h("section", { class: "retailedge-bank-import-preview" }, [
						h("div", { class: "retailedge-bank-import-preview__heading" }, [
							h("h3", t("Statement Preview")),
							EdgeStatusBadge ? h(EdgeStatusBadge, { status: warnings.length ? "Warning" : "Ready" }) : null,
						]),
						columns.length ? h("p", { class: "retailedge-bank-import-columns" }, `${t("Detected columns")}: ${columns.join(" · ")}`) : null,
						warnings.length ? h("div", { class: "retailedge-bank-import-warning" }, [
							h("strong", t("Preview warnings")),
							h("ul", warnings.slice(0, 8).map((warning) => h("li", warning))),
						]) : null,
						rows.length ? h("div", { class: "retailedge-bank-import-table-wrap" }, [
							h("table", { class: "retailedge-bank-import-table" }, [
								h("thead", [h("tr", columns.map((column) => h("th", column)))]),
								h("tbody", rows.map((row) => h("tr", row.map((value) => h("td", value))))),
							]),
						]) : h("p", { class: "text-muted" }, t("ERPNext validated the file. No preview rows were returned for display.")),
					]);
				}

				return () => h(EdgeModal, {
					open: state.open,
					title: t("Upload Bank Statement"),
					subtitle: t("Preview and import through ERPNext Banking without leaving Bank Matching."),
					size: "xl",
					busy: state.busy,
					closeOnBackdrop: false,
					onClose: close,
				}, {
					default: () => [
						h("div", { class: "retailedge-bank-import-context" }, [
							h(EdgeLinkField, {
								label: t("Company"),
								modelValue: state.company,
								searcher: (query) => permissionAwareLinkSearch("Company", query),
								"onUpdate:modelValue": (value) => {
									state.company = value || "";
									state.bankAccount = "";
									state.importName = "";
									state.preview = null;
								},
							}),
							h(EdgeLinkField, {
								label: t("Bank Account"),
								modelValue: state.bankAccount,
								disabled: !state.company,
								description: !state.company ? t("Select a company first.") : t("Only bank accounts available to you for the selected company are shown."),
								searcher: (query) => permissionAwareLinkSearch("Bank Account", query, state.company ? { company: state.company } : {}),
								"onUpdate:modelValue": (value) => {
									state.bankAccount = value || "";
									state.importName = "";
									state.preview = null;
								},
							}),
						]),
						h("div", { class: "retailedge-bank-import-file-row" }, [
							h("label", { class: "retailedge-bank-import-file" }, [
								h("span", t("Statement File")),
								h("input", {
									type: "file",
									accept: ".csv,.xls,.xlsx,.txt,.TXT",
									disabled: state.busy || state.importStarted,
									onChange: onFileChange,
								}),
								state.fileName ? h("small", state.fileName) : h("small", t("CSV, XLS, XLSX, or MT940 TXT")),
							]),
							h("button", {
								type: "button",
								class: "edge-button edge-button--secondary",
								disabled: state.busy,
								onClick: downloadTemplate,
							}, t("Download Template")),
						]),
						state.error ? h("div", { class: "retailedge-bank-import-error", role: "alert" }, state.error) : null,
						state.status ? h("div", { class: "retailedge-bank-import-status", role: "status" }, [
							h("strong", state.status),
							h("span", state.statusDetail),
						]) : null,
						renderPreview(),
						h("p", { class: "retailedge-bank-import-safety" }, t("Import creates Bank Transactions only. It does not confirm matches, approve reconciliation, or mutate submitted accounting documents.")),
					],
					footer: () => [
						h("button", { type: "button", class: "edge-button edge-button--secondary", disabled: state.busy, onClick: close }, t("Close")),
						state.importStarted
							? h("button", { type: "button", class: "edge-button edge-button--secondary", disabled: state.busy, onClick: checkImportStatus }, t("Check Status"))
							: h("button", { type: "button", class: "edge-button edge-button--secondary", disabled: state.busy || !state.company || !state.bankAccount || !state.file, onClick: preparePreview }, t("Preview Statement")),
						!state.importStarted && state.preview
							? h("button", { type: "button", class: "edge-button edge-button--primary", disabled: state.busy, onClick: startImport }, t("Start Import"))
							: null,
					],
				});
			},
		}).mount(host);
		return host;
	}

	function openStatementImport(root) {
		const filterBar = root.querySelector(".edge-filter-bar");
		const modalHost = mountStatementImportModal(root);
		if (!modalHost?.__retailedgeOpenStatementImport) {
			global.frappe?.throw?.(t("EdgeSuite modal components are unavailable. Rebuild EdgeSuite UI assets before importing a bank statement."));
			return;
		}
		modalHost.__retailedgeOpenStatementImport({
			company: fieldValueByLabel(filterBar, "Company"),
			bankAccount: fieldValueByLabel(filterBar, "Bank Account"),
		});
	}

	function addUploadStatementAction(root) {
		if (root.querySelector(".retailedge-bank-upload-statement")) return;
		const refresh = findButton(root, ["Refresh"]);
		if (!refresh?.parentElement) return;
		const button = document.createElement("button");
		button.type = "button";
		button.className = "edge-button edge-button--secondary retailedge-bank-upload-statement";
		button.textContent = t("Upload Statement");
		button.title = t("Upload, preview, and import a statement through ERPNext Banking in an EdgeSuite modal.");
		button.addEventListener("click", () => openStatementImport(root));
		refresh.parentElement.insertBefore(button, refresh);
	}

	function enhancePage() {
		scheduled = false;
		if (!isBankingPage()) return;
		const root = pageRoot();
		if (!root) return;
		const filterBar = root.querySelector(".edge-filter-bar");
		if (filterBar) {
			removeFilterHeading(filterBar);
			const reset = restyleReset(filterBar);
			mountSmartDateRange(filterBar, reset);
		}
		mountStatementImportModal(root);
		addUploadStatementAction(root);
	}

	function scheduleEnhancement() {
		if (scheduled) return;
		scheduled = true;
		setTimeout(enhancePage, 0);
	}

	const observer = new MutationObserver(scheduleEnhancement);
	observer.observe(document.documentElement, { childList: true, subtree: true });
	global.retailedgeBankingPageEnhancementsInstalled = true;
	scheduleEnhancement();
})(window);
