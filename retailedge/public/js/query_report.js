(function () {
	if (typeof window === "undefined") {
		return;
	}

	window.retailedge = window.retailedge || {};
	const RETAILEDGE_CARD_REPORTS = new Set([
		"RetailEdge Bank Transaction Matching",
		"RetailEdge Bank Match Review",
		"RetailEdge Branch Performance Summary",
		"RetailEdge Invoice Payment Audit",
		"RetailEdge Payment Evidence Matching",
		"RetailEdge Daily Sales Audit Register",
		"RetailEdge Cashier Expense Review",
		"POS Closing Variance vs Expenses",
		"RetailEdge Cash Shift Verification",
	]);

	const REPORT_HIDDEN_FIELDS = {
		"Stock Ledger": new Set([
			"incoming_rate",
			"valuation_rate",
			"in_out_rate",
			"stock_value",
			"stock_value_difference",
		]),
	};

	function shouldHideCostFields() {
		try {
			if (frappe.boot?.retailedge?.cost_visibility) {
				return Boolean(frappe.boot.retailedge.cost_visibility.hide_cost_price);
			}
		} catch (error) {
			// Ignore boot info errors.
		}

		try {
			const raw = sessionStorage.getItem("retailedge.cost_visibility_rules.v4");
			if (raw) {
				const parsed = JSON.parse(raw);
				return Boolean(parsed && parsed.hide_cost_price);
			}
		} catch (error) {
			// Ignore session storage errors.
		}

		return false;
	}

	function getHiddenFields(reportName) {
		return REPORT_HIDDEN_FIELDS[reportName] || null;
	}

	function patchReportSettings(queryReport) {
		if (!queryReport || !queryReport.report_settings || queryReport.report_settings.__retailedgePatched) {
			return;
		}

		const hiddenFields = getHiddenFields(queryReport.report_name);
		if (!hiddenFields) {
			return;
		}

		const settings = queryReport.report_settings;
		const originalAfterDatatableRender = settings.after_datatable_render;
		const originalGetDatatableOptions = settings.get_datatable_options;

		settings.get_datatable_options = function (options) {
			let nextOptions = options;
			if (originalGetDatatableOptions) {
				nextOptions = originalGetDatatableOptions.call(this, options) || options;
			}

			try {
				if (Array.isArray(nextOptions.columns)) {
					nextOptions.columns = nextOptions.columns.filter((column) => {
						return !hiddenFields.has(column?.fieldname || column?.id);
					});
				}
			} catch (error) {
				// Ignore datatable options patch errors.
			}

			return nextOptions;
		};

		settings.after_datatable_render = function (datatable) {
			hideRenderedColumns(queryReport, datatable);
			if (originalAfterDatatableRender) {
				originalAfterDatatableRender.call(this, datatable);
			}
		};

		settings.__retailedgePatched = true;
	}

	function hideRenderedColumns(queryReport, datatable) {
		if (!queryReport || !shouldHideCostFields()) {
			return;
		}

		const hiddenFields = getHiddenFields(queryReport.report_name);
		if (!hiddenFields) {
			return;
		}

		try {
			if (Array.isArray(queryReport.columns)) {
				queryReport.columns = queryReport.columns.map((column) => {
					if (column && hiddenFields.has(column.fieldname || column.id)) {
						return Object.assign({}, column, { hidden: 1 });
					}
					return column;
				});
			}
		} catch (error) {
			// Ignore column patch errors.
		}

		try {
			if (datatable?.options?.columns) {
				datatable.options.columns = datatable.options.columns.filter((column) => {
					return !hiddenFields.has(column?.fieldname || column?.id);
				});
			}
		} catch (error) {
			// Ignore datatable option filtering errors.
		}

		try {
			if (datatable?.datamanager?.columns) {
				datatable.datamanager.columns = datatable.datamanager.columns.filter((column) => {
					return !hiddenFields.has(column?.fieldname || column?.id);
				});
			}
		} catch (error) {
			// Ignore datamanager filtering errors.
		}

		try {
			if (queryReport.$report) {
				hiddenFields.forEach((fieldname) => {
					queryReport.$report.find(`[data-fieldname="${fieldname}"]`).hide();
					queryReport.$report.find(`.${fieldname}`).hide();
				});
			}
		} catch (error) {
			// Ignore DOM hide errors.
		}
	}

	function escapeHtml(value) {
		return frappe.utils.escape_html(String(value == null ? "" : value));
	}

	function inferTone(label) {
		const text = String(label || "").toLowerCase();
		if (
			text.includes("confirmed") ||
			text.includes("matched") ||
			text.includes("strong") ||
			text.includes("verified") ||
			text.includes("balanced")
		) {
			return "success";
		}
		if (
			text.includes("needs review") ||
			text.includes("possible") ||
			text.includes("pending") ||
			text.includes("duplicate")
		) {
			return "warning";
		}
		if (
			text.includes("blocked") ||
			text.includes("unsafe") ||
			text.includes("high risk") ||
			text.includes("variance") ||
			text.includes("exception")
		) {
			return "danger";
		}
		if (text.includes("minimum") || text.includes("already reviewed")) {
			return "neutral";
		}
		return "info";
	}

	function getMetricValueClass(valueText) {
		const text = String(valueText || "").trim();
		if (!text) {
			return "";
		}
		if (text.includes("%")) {
			return "retailedge-value-percent";
		}
		if (/[₦$€£,]/.test(text) || /\d+\.\d{2}\b/.test(text)) {
			return "retailedge-value-currency";
		}
		return "retailedge-value-count";
	}

	function formatSummaryTitle(label) {
		return String(label || "")
			.toLowerCase()
			.split(/\s+/)
			.filter(Boolean)
			.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
			.join(" ");
	}

	function formatSummaryValueMarkup(valueText) {
		const text = String(valueText || "").trim();
		if (!text) {
			return "";
		}

		return escapeHtml(text).replace(/^([₦$€£])\s*/, '<span class="retailedge-currency-symbol">$1</span>');
	}

	function getHintText(label, tone) {
		const text = String(label || "").toLowerCase();
		if (text.includes("needs review")) return __("Needs reviewer action");
		if (text.includes("duplicate")) return __("Duplicate candidate flagged");
		if (text.includes("confirmed") || text.includes("matched")) return __("Already reviewed");
		if (text.includes("exception") || text.includes("variance")) return __("Investigate this item");
		if (tone === "success") return __("Operationally healthy");
		if (tone === "warning") return __("Needs attention");
		if (tone === "danger") return __("Requires action");
		return __("RetailEdge summary");
	}

	function renderStatusBadge(text, tone) {
		return `<span class="retailedge-status-badge retailedge-tone-${tone}">${escapeHtml(text)}</span>`;
	}

	function getTonePalette(tone) {
		const palettes = {
			success: {
				accent: "#16A34A",
				bg: "#EAF8F0",
				text: "#15803D",
			},
			warning: {
				accent: "#D97706",
				bg: "#FFF7E6",
				text: "#D97706",
			},
			danger: {
				accent: "#DC2626",
				bg: "#FEF2F2",
				text: "#DC2626",
			},
			neutral: {
				accent: "#6B7280",
				bg: "#F3F4F6",
				text: "#4B5563",
			},
			info: {
				accent: "#0B5CAB",
				bg: "#EFF6FF",
				text: "#0B5CAB",
			},
		};
		return palettes[tone] || palettes.info;
	}

	function decorateRetailEdgeReport(queryReport) {
		if (!queryReport) {
			return;
		}

		if (window.retailedge?.isRetailEdgeCardReport && !window.retailedge.isRetailEdgeCardReport(queryReport)) {
			window.retailedge.cleanupRetailEdgeCardClasses?.(queryReport);
			return;
		}

		try {
			if (window.retailedge?.decorateReportSummary) {
				window.retailedge.decorateReportSummary(queryReport);
				return;
			}

			const $summary = queryReport.$summary;
			const $pageMain = queryReport.page?.main;
			if ($pageMain && $pageMain.addClass) {
				$pageMain.addClass("retailedge-report-page retailedge-query-report");
			}
			if (!$summary || !$summary.find) {
				return;
			}

			$summary.addClass("retailedge-report-summary retailedge-card-grid retailedge-report-summary-grid").show();
			$summary.css({
				display: "grid",
				gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
				gap: "16px",
				marginBottom: "20px",
			});
			$summary.find(".summary-item").each(function () {
				const $item = $(this);
				const label = ($item.find(".summary-label").text() || "").trim();
				const $value = $item.find(".summary-value").first();
				const valueText = ($value.text() || "").trim();
				const tone = inferTone(label);
				const palette = getTonePalette(tone);

				$item.removeClass(
					"retailedge-tone-info retailedge-tone-success retailedge-tone-warning retailedge-tone-danger retailedge-tone-neutral"
				);
				$item.addClass(`retailedge-number-card retailedge-tone-${tone}`);
				$item.css({
					position: "relative",
					display: "flex",
					flexDirection: "column",
					justifyContent: "space-between",
					alignItems: "flex-start",
					isolation: "isolate",
					minHeight: "160px",
					padding: "22px 20px 18px",
					background: "linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%)",
					border: "1px solid #E5E7EB",
					borderRadius: "18px",
					boxShadow: "0 12px 30px rgba(11, 45, 91, 0.08)",
					overflow: "hidden",
					textAlign: "left",
				});
				$item.get(0)?.style.setProperty("--retailedge-inline-accent", palette.accent);

				if (!$item.children(".retailedge-accent-bar").length) {
					$item.prepend(
						`<span class="retailedge-accent-bar" style="position:absolute;left:0;top:0;width:100%;height:4px;background:${palette.accent};z-index:0;pointer-events:none;"></span>`
					);
				}

				if (!$item.children(".retailedge-orb").length) {
					$item.append(
						`<span class="retailedge-orb" style="position:absolute;right:-44px;top:-42px;width:130px;height:130px;border-radius:999px;background:radial-gradient(circle, rgba(11, 92, 171, 0.06), rgba(11, 92, 171, 0));z-index:0;pointer-events:none;"></span>`
					);
				}

				$item.find(".summary-label").css({
					position: "relative",
					zIndex: "2",
					margin: "0",
					maxWidth: "16ch",
					fontSize: "11px",
					fontWeight: "700",
					lineHeight: "1.45",
					letterSpacing: "0.08em",
					textTransform: "uppercase",
					color: "#374151",
				});
				$item.find(".summary-label").text(formatSummaryTitle(label));
				$value.removeClass("retailedge-value-currency retailedge-value-percent retailedge-value-count");
				$value.addClass(getMetricValueClass(valueText));
				$value.html(formatSummaryValueMarkup(valueText));
				$value.css({
					position: "relative",
					zIndex: "3",
					display: "block",
					paddingTop: "16px",
					margin: "6px 0 12px",
					fontSize: valueText.includes("%") ? "34px" : /[₦$€£,]/.test(valueText) ? "30px" : "32px",
					fontWeight: "800",
					lineHeight: "1.15",
					letterSpacing: "-0.03em",
					color: "#111827",
					fontVariantNumeric: "tabular-nums lining-nums",
					overflow: "visible",
				});

				$item.find(".retailedge-status-badge, .retailedge-card-footer").remove();
			});
		} catch (error) {
			// Ignore RetailEdge summary decoration errors.
		}
	}

	function patchQueryReportPrototype() {
		if (
			typeof frappe === "undefined" ||
			!frappe.views ||
			!frappe.views.QueryReport ||
			frappe.views.QueryReport.prototype.__retailedgePatched
		) {
			return Boolean(frappe?.views?.QueryReport?.prototype?.__retailedgePatched);
		}

		const QueryReport = frappe.views.QueryReport;
		const originalGetReportSettings = QueryReport.prototype.get_report_settings;
		const originalPrepareReportData = QueryReport.prototype.prepare_report_data;
		const originalRenderDatatable = QueryReport.prototype.render_datatable;

		QueryReport.prototype.get_report_settings = function () {
			return originalGetReportSettings.call(this).then(() => {
				patchReportSettings(this);
			});
		};

		QueryReport.prototype.prepare_report_data = function (data) {
			const result = originalPrepareReportData.call(this, data);
			hideRenderedColumns(this, this.datatable);
			if (window.retailedge?.cleanupRetailEdgeCardClasses && !(window.retailedge?.isRetailEdgeCardReport?.(this))) {
				window.retailedge.cleanupRetailEdgeCardClasses(this);
			}
			setTimeout(() => decorateRetailEdgeReport(this), 0);
			return result;
		};

		QueryReport.prototype.render_datatable = function () {
			patchReportSettings(this);
			hideRenderedColumns(this, this.datatable);
			const result = originalRenderDatatable.call(this);
			hideRenderedColumns(this, this.datatable);
			if (window.retailedge?.cleanupRetailEdgeCardClasses && !(window.retailedge?.isRetailEdgeCardReport?.(this))) {
				window.retailedge.cleanupRetailEdgeCardClasses(this);
			}
			decorateRetailEdgeReport(this);
			setTimeout(() => decorateRetailEdgeReport(this), 0);
			setTimeout(() => decorateRetailEdgeReport(this), 150);
			setTimeout(() => hideRenderedColumns(this, this.datatable), 0);
			setTimeout(() => hideRenderedColumns(this, this.datatable), 150);
			setTimeout(() => hideRenderedColumns(this, this.datatable), 500);
			return result;
		};

		QueryReport.prototype.__retailedgePatched = true;
		return true;
	}

	function registerQueryReportPatch(attempt) {
		if (patchQueryReportPrototype()) {
			return;
		}

		if ((attempt || 0) >= 20) {
			return;
		}

		setTimeout(function () {
			registerQueryReportPatch((attempt || 0) + 1);
		}, 500);
	}

	registerQueryReportPatch(0);
})();
