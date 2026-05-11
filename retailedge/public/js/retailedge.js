(function () {
	if (typeof window === "undefined") {
		return;
	}

	window.retailedge = window.retailedge || {};
	const RULES_CACHE_VERSION = "v4";
	const COST_FORM_DOCTYPES = [
		"Item",
		"Serial No",
		"Stock Entry",
		"Material Request",
		"Quotation",
		"Sales Order",
		"Purchase Order",
		"Supplier Quotation",
		"Purchase Receipt",
		"Purchase Invoice",
		"Delivery Note",
		"Sales Invoice",
		"Stock Reconciliation",
		"Stock Ledger Entry",
		"Bin",
		"Item Price",
	];
	const STOCK_ENTRY_PARENT_FIELDS = new Set([
		"total_incoming_value",
		"total_outgoing_value",
		"value_difference",
	]);
	const STOCK_ENTRY_ITEM_FIELDS = new Set([
		"basic_rate",
		"basic_amount",
		"amount",
		"additional_cost",
		"landed_cost_voucher_amount",
		"valuation_rate",
	]);
	const DOCTYPE_FIELD_EXCLUSIONS = {
		"Sales Invoice": new Set(["base_net_rate", "net_rate", "base_rate", "basic_rate", "base_price_list_rate", "price_list_rate"]),
		"Delivery Note": new Set(["base_net_rate", "net_rate", "base_rate", "basic_rate", "base_price_list_rate", "price_list_rate"]),
		"Quotation": new Set(["rate", "amount", "base_amount", "base_rate", "basic_rate", "price_list_rate", "base_price_list_rate"]),
		"Sales Order": new Set(["rate", "amount", "base_amount", "base_rate", "basic_rate", "price_list_rate", "base_price_list_rate"]),
	};
	window.retailedge.getCostPriceVisibilityContext = function () {
		if (typeof frappe === "undefined" || !frappe.call) {
			return Promise.resolve(null);
		}

		return frappe.call("retailedge.api.get_cost_price_visibility_context").then(function (response) {
			return response.message || null;
		});
	};
	window.retailedge.getPostingDateContext = async function () {
		if (typeof frappe === "undefined" || !frappe.call) {
			return null;
		}

		const response = await frappe.call({
			method: "retailedge.api.get_posting_date_context",
		});

		window.retailedge.postingDateContext = response.message || null;
		return window.retailedge.postingDateContext;
	};

	window.retailedge.costVisibility = {
		rules: null,
		loaded: false,
		cacheKey: "retailedge.cost_visibility_rules." + RULES_CACHE_VERSION,
		boundForms: new WeakSet(),
		boundGridWrappers: new WeakSet(),
		getBootRules: function () {
			try {
				if (typeof frappe !== "undefined" && frappe.boot && frappe.boot.retailedge) {
					const costVisibility = frappe.boot.retailedge.cost_visibility || {};
					if (typeof costVisibility.hide_cost_price !== "undefined") {
						return {
							hide_cost_price: costVisibility.hide_cost_price ? 1 : 0,
							fieldnames: [],
							label_keywords: [],
						};
					}
				}
			} catch (error) {
				// Ignore boot info errors.
			}

			return null;
		},
		normalizeRules: function (rules) {
			const normalized = rules || {};
			return {
				hide_cost_price: normalized.hide_cost_price ? 1 : 0,
				fieldnames: Array.isArray(normalized.fieldnames) ? normalized.fieldnames : [],
				label_keywords: Array.isArray(normalized.label_keywords) ? normalized.label_keywords : [],
			};
		},
		loadRules: async function () {
			if (this.loaded && this.rules) {
				return this.rules;
			}

			const bootRules = this.getBootRules();
			if (bootRules && bootRules.hide_cost_price === 0) {
				this.rules = bootRules;
				this.loaded = true;
			}

			try {
				if (typeof sessionStorage !== "undefined") {
					const cached = sessionStorage.getItem(this.cacheKey);
					if (cached) {
						this.rules = this.normalizeRules(JSON.parse(cached));
						this.loaded = true;
						return this.rules;
					}
				}
			} catch (error) {
				// Ignore cache errors and continue with live fetch.
			}

			if (typeof frappe === "undefined" || !frappe.call) {
				this.rules = this.normalizeRules();
				this.loaded = true;
				return this.rules;
			}

			try {
				const response = await frappe.call({
					method: "retailedge.api.get_cost_visibility_rules",
				});

				this.rules = this.normalizeRules(response.message);
				this.loaded = true;

				try {
					if (typeof sessionStorage !== "undefined") {
						sessionStorage.setItem(this.cacheKey, JSON.stringify(this.rules));
					}
				} catch (error) {
					// Ignore cache write errors.
				}
			} catch (error) {
				this.rules = this.normalizeRules();
				this.loaded = true;
			}

			return this.rules;
		},
		shouldHide: function () {
			return Boolean(this.rules && this.rules.hide_cost_price);
		},
		isLabelMatch: function (label) {
			if (!label || !this.rules || !Array.isArray(this.rules.label_keywords)) {
				return false;
			}

			const normalized = String(label).toLowerCase();
			return this.rules.label_keywords.some(function (keyword) {
				return normalized.includes(String(keyword).toLowerCase());
			});
		},
		shouldExcludeField: function (frm, fieldname) {
			if (!frm || !fieldname) {
				return false;
			}

			const exclusions = DOCTYPE_FIELD_EXCLUSIONS[frm.doctype];
			return Boolean(exclusions && exclusions.has(fieldname));
		},
		isRestrictedField: function (frm, df) {
			if (!df || !df.fieldname) {
				return false;
			}

			if (this.shouldExcludeField(frm, df.fieldname) && !this.isLabelMatch(df.label)) {
				return false;
			}

			const fieldnames = new Set(this.rules.fieldnames || []);
			return fieldnames.has(df.fieldname) || this.isLabelMatch(df.label);
		},
		hideControlElement: function (element) {
			if (!element) {
				return;
			}

			try {
				const control = element.closest
					? element.closest(".frappe-control, .form-group, .grid-static-col, .control-input, .fields_order")
					: element;
				if (control) {
					control.classList.add("retailedge-hidden-cost-field");
					control.style.display = "none";
				}
			} catch (error) {
				// Ignore direct DOM hide errors.
			}
		},
		hideMatchingControlsInWrapper: function (wrapper, fieldname, label) {
			if (!wrapper || typeof $ === "undefined") {
				return;
			}

			try {
				const $wrapper = wrapper.jquery ? wrapper : $(wrapper);
				const selectors = [
					`.frappe-control[data-fieldname="${fieldname}"]`,
					`.form-group[data-fieldname="${fieldname}"]`,
					`.grid-static-col[data-fieldname="${fieldname}"]`,
					`.control-input[data-fieldname="${fieldname}"]`,
					`.fields_order[data-fieldname="${fieldname}"]`,
					`[data-fieldname="${fieldname}"]`,
				];

				selectors.forEach((selector) => {
					$wrapper.find(selector).each((_, node) => {
						this.hideControlElement(node);
					});
				});

				if (label) {
					$wrapper.find("label").each((_, node) => {
						const text = (node.textContent || "").trim().toLowerCase();
						if (text && text === String(label).trim().toLowerCase()) {
							this.hideControlElement(node);
						}
					});
				}
			} catch (error) {
				// Ignore wrapper selector hide errors.
			}
		},
		hideFieldByDf: function (frm, df, fieldname) {
			if (!df || !fieldname) {
				return;
			}

			try {
				frm.set_df_property(fieldname, "hidden", 1);
			} catch (error) {
				// Ignore field property errors.
			}

			try {
				const field = frm.get_field(fieldname);
				if (field) {
					const wrapper = field.wrapper || field.$wrapper;
					const element =
						wrapper && wrapper.jquery ? wrapper.get(0) : wrapper;
					this.hideControlElement(element);
				}
			} catch (error) {
				// Ignore wrapper hide errors.
			}
		},
		hideCostFieldsOnForm: function (frm) {
			if (!frm || !Array.isArray(frm.meta && frm.meta.fields)) {
				return;
			}

			(frm.meta.fields || []).forEach((df) => {
				if (!df || !df.fieldname) {
					return;
				}

				if (this.isRestrictedField(frm, df)) {
					this.hideFieldByDf(frm, df, df.fieldname);
				}
			});
		},
		filterGridUserSettings: function (frm, grid) {
			if (!frm || !grid || typeof frappe === "undefined" || !frappe.get_user_settings) {
				return;
			}

			try {
				const gridViewSettings = frappe.get_user_settings(frm.doctype, "GridView");
				const configured = gridViewSettings && gridViewSettings[grid.doctype];
				if (!Array.isArray(configured)) {
					return;
				}

				const filtered = configured.filter((column) => {
					const df = frappe.meta.get_docfield(grid.doctype, column.fieldname);
					return !this.isRestrictedField(frm, df);
				});

				if (filtered.length !== configured.length && frappe.model && frappe.model.user_settings) {
					if (!frappe.model.user_settings[frm.doctype]) {
						frappe.model.user_settings[frm.doctype] = {};
					}
					if (!frappe.model.user_settings[frm.doctype].GridView) {
						frappe.model.user_settings[frm.doctype].GridView = {};
					}
					frappe.model.user_settings[frm.doctype].GridView[grid.doctype] = filtered;
				}
			} catch (error) {
				// Ignore user settings filtering errors.
			}
		},
		filterGridVisibleColumns: function (frm, grid) {
			if (!frm || !grid) {
				return;
			}

			try {
				if (Array.isArray(grid.user_defined_columns)) {
					grid.user_defined_columns = grid.user_defined_columns.filter((df) => {
						return !this.isRestrictedField(frm, df);
					});
				}
			} catch (error) {
				// Ignore user-defined column filtering errors.
			}

			try {
				if (Array.isArray(grid.visible_columns)) {
					grid.visible_columns = grid.visible_columns.filter((column) => {
						return !this.isRestrictedField(frm, column && column[0]);
					});
				}
			} catch (error) {
				// Ignore visible column filtering errors.
			}
		},
		hideGridDomColumns: function (frm, grid) {
			if (!frm || !grid || !grid.wrapper || typeof $ === "undefined") {
				return;
			}

			const $gridWrapper = grid.wrapper.jquery ? grid.wrapper : $(grid.wrapper);
			(grid.docfields || []).forEach((childDf) => {
				if (!this.isRestrictedField(frm, childDf)) {
					return;
				}

				this.hideMatchingControlsInWrapper($gridWrapper, childDf.fieldname, childDf.label);
			});

			try {
				$gridWrapper.find(".grid-row, .grid-heading-row, .grid-body, .form-grid").each((_, node) => {
					(grid.docfields || []).forEach((childDf) => {
						if (!this.isRestrictedField(frm, childDf)) {
							return;
						}

						this.hideMatchingControlsInWrapper($(node), childDf.fieldname, childDf.label);
					});
				});
			} catch (error) {
				// Ignore repeated grid DOM hide errors.
			}
		},
		patchGridVisibleColumns: function (frm, grid) {
			if (!frm || !grid || grid.__retailedgeVisibleColumnsPatched) {
				return;
			}

			const self = this;
			const originalSetupVisibleColumns = grid.setup_visible_columns
				? grid.setup_visible_columns.bind(grid)
				: null;
			if (!originalSetupVisibleColumns) {
				return;
			}

			grid.setup_visible_columns = function () {
				this.visible_columns = [];
				originalSetupVisibleColumns();
				self.filterGridUserSettings(frm, this);
				self.filterGridVisibleColumns(frm, this);
			};
			grid.__retailedgeVisibleColumnsPatched = true;
		},
		hideStockEntryParentTotals: function (frm) {
			if (!frm || frm.doctype !== "Stock Entry") {
				return;
			}

			STOCK_ENTRY_PARENT_FIELDS.forEach((fieldname) => {
				try {
					if (frm.toggle_display) {
						frm.toggle_display(fieldname, false);
					}
				} catch (error) {
					// Ignore Stock Entry parent display toggle errors.
				}

				try {
					frm.set_df_property(fieldname, "hidden", 1);
				} catch (error) {
					// Ignore Stock Entry parent property errors.
				}

				try {
					const field = frm.get_field(fieldname);
					if (field) {
						const wrapper = field.wrapper || field.$wrapper;
						const element = wrapper && wrapper.jquery ? wrapper.get(0) : wrapper;
						this.hideControlElement(element);
					}
				} catch (error) {
					// Ignore Stock Entry parent wrapper errors.
				}

				this.hideMatchingControlsInWrapper(frm.wrapper, fieldname);
			});
		},
		hideStockEntryGrid: function (frm) {
			if (!frm || frm.doctype !== "Stock Entry" || !frm.fields_dict || !frm.fields_dict.items) {
				return;
			}

			const grid = frm.fields_dict.items.grid;
			if (!grid) {
				return;
			}

			this.patchGridVisibleColumns(frm, grid);
			this.filterGridUserSettings(frm, grid);

			try {
				if (Array.isArray(grid.user_defined_columns)) {
					grid.user_defined_columns = grid.user_defined_columns.filter((df) => {
						return !STOCK_ENTRY_ITEM_FIELDS.has(df && df.fieldname);
					});
				}
			} catch (error) {
				// Ignore Stock Entry user-defined column filtering errors.
			}

				try {
					(grid.docfields || []).forEach((df) => {
						if (!df || !STOCK_ENTRY_ITEM_FIELDS.has(df.fieldname)) {
							return;
						}

						df.hidden = 1;
						if (grid.toggle_display) {
							grid.toggle_display(df.fieldname, false);
						}
						if (grid.update_docfield_property) {
							grid.update_docfield_property(df.fieldname, "hidden", 1);
						}
					});
			} catch (error) {
				// Ignore Stock Entry docfield property errors.
			}

			try {
				grid.visible_columns = (grid.visible_columns || []).filter((column) => {
					return !STOCK_ENTRY_ITEM_FIELDS.has(column && column[0] && column[0].fieldname);
				});
			} catch (error) {
				// Ignore Stock Entry visible column filtering errors.
			}

			try {
				grid.refresh();
			} catch (error) {
				// Ignore Stock Entry grid refresh errors.
			}

			try {
				const $gridWrapper = grid.wrapper && grid.wrapper.jquery ? grid.wrapper : $(grid.wrapper);
				STOCK_ENTRY_ITEM_FIELDS.forEach((fieldname) => {
					this.hideMatchingControlsInWrapper($gridWrapper, fieldname);
				});
			} catch (error) {
				// Ignore Stock Entry DOM hide errors.
			}

			try {
				(grid.grid_rows || []).forEach((gridRow) => {
					this.hideGridRowFormCostFields(frm, grid, gridRow);
					if (gridRow && gridRow.wrapper) {
						STOCK_ENTRY_ITEM_FIELDS.forEach((fieldname) => {
							this.hideMatchingControlsInWrapper(gridRow.wrapper, fieldname);
						});
					}
				});
			} catch (error) {
				// Ignore Stock Entry row hide errors.
			}

			this.bindGridObserver(frm, grid);
		},
		applyStockEntryProtection: function (frm) {
			if (!frm || frm.doctype !== "Stock Entry" || !this.shouldHide()) {
				return;
			}

			this.hideStockEntryParentTotals(frm);
			this.hideStockEntryGrid(frm);

			setTimeout(() => {
				this.hideStockEntryParentTotals(frm);
				this.hideStockEntryGrid(frm);
			}, 0);
			setTimeout(() => {
				this.hideStockEntryParentTotals(frm);
				this.hideStockEntryGrid(frm);
			}, 150);
			setTimeout(() => {
				this.hideStockEntryParentTotals(frm);
				this.hideStockEntryGrid(frm);
			}, 500);
		},
		bindGridObserver: function (frm, grid) {
			if (!frm || !grid || !grid.wrapper || typeof MutationObserver === "undefined") {
				return;
			}

			const wrapperNode = grid.wrapper.jquery ? grid.wrapper.get(0) : grid.wrapper;
			if (!wrapperNode || this.boundGridWrappers.has(wrapperNode)) {
				return;
			}

			this.boundGridWrappers.add(wrapperNode);
			const self = this;
			const observer = new MutationObserver(function () {
				try {
					if (!self.shouldHide()) {
						return;
					}

					self.filterGridUserSettings(frm, grid);
					self.filterGridVisibleColumns(frm, grid);
					self.hideGridDomColumns(frm, grid);
					self.applyStockEntryProtection(frm);
				} catch (error) {
					// Ignore observer errors.
				}
			});

			observer.observe(wrapperNode, {
				childList: true,
				subtree: true,
			});
		},
		hideGridCostColumns: function (frm) {
			if (!frm || !Array.isArray(frm.meta && frm.meta.fields)) {
				return;
			}

			(frm.meta.fields || []).forEach((df) => {
				if (!df || df.fieldtype !== "Table" || !df.fieldname) {
					return;
				}

				const grid = frm.fields_dict && frm.fields_dict[df.fieldname] && frm.fields_dict[df.fieldname].grid;
				if (!grid) {
					return;
				}

				this.filterGridUserSettings(frm, grid);
				this.filterGridVisibleColumns(frm, grid);
				this.bindGridObserver(frm, grid);

				(grid.docfields || []).forEach((childDf) => {
					if (!childDf || !childDf.fieldname) {
						return;
					}

					if (!this.isRestrictedField(frm, childDf)) {
						return;
					}

					try {
						childDf.hidden = 1;
					} catch (error) {
						// Ignore grid docfield errors.
					}

					try {
						if (grid.update_docfield_property) {
							grid.update_docfield_property(childDf.fieldname, "hidden", 1);
						}
					} catch (error) {
						// Ignore grid property errors.
					}
				});

				try {
					grid.refresh();
				} catch (error) {
					// Ignore grid refresh errors.
				}

				this.hideGridDomColumns(frm, grid);

				try {
					(grid.grid_rows || []).forEach((gridRow) => {
						this.hideGridRowFormCostFields(frm, grid, gridRow);
					});
				} catch (error) {
					// Ignore grid row form errors.
				}
			});
		},
		hideGridRowFormCostFields: function (frm, grid, gridRow) {
			if (!frm || !grid || !gridRow || !gridRow.grid_form || !gridRow.grid_form.fields_dict) {
				return;
			}

			const fieldnames = new Set(this.rules.fieldnames || []);
			const gridFormWrapper =
				gridRow.grid_form.wrapper && gridRow.grid_form.wrapper.jquery
					? gridRow.grid_form.wrapper
					: $(gridRow.grid_form.wrapper);
			Object.keys(gridRow.grid_form.fields_dict).forEach((fieldname) => {
				const field = gridRow.grid_form.fields_dict[fieldname];
				const df = field && field.df;
				if (!df || !fieldname) {
					return;
				}

				if (this.shouldExcludeField(frm, fieldname) && !this.isLabelMatch(df.label)) {
					return;
				}

				if (!(fieldnames.has(fieldname) || this.isLabelMatch(df.label))) {
					return;
				}

				try {
					df.hidden = 1;
				} catch (error) {
					// Ignore grid row df errors.
				}

				try {
					if (gridRow.toggle_display) {
						gridRow.toggle_display(fieldname, false);
					} else if (gridRow.set_field_property) {
						gridRow.set_field_property(fieldname, "hidden", 1);
					}
				} catch (error) {
					// Ignore grid row property errors.
				}

				try {
					if (field.refresh) {
						field.refresh();
					}
				} catch (error) {
					// Ignore field refresh errors.
				}

				try {
					if (field.wrapper) {
						const wrapper = field.wrapper || field.$wrapper;
						const element =
							wrapper && wrapper.jquery ? wrapper.get(0) : wrapper;
						this.hideControlElement(element);
					}
				} catch (error) {
					// Ignore wrapper hide errors.
				}

				this.hideMatchingControlsInWrapper(gridFormWrapper, fieldname, df.label);
			});

			try {
				if (gridRow.grid_form.layout && gridRow.grid_form.layout.refresh_sections) {
					gridRow.grid_form.layout.refresh_sections();
				}
			} catch (error) {
				// Ignore layout refresh errors.
			}
		},
		bindGridEvents: function (frm) {
			if (!frm || !frm.wrapper || this.boundForms.has(frm.wrapper)) {
				return;
			}

			this.boundForms.add(frm.wrapper);
			const self = this;

			if (typeof $ !== "undefined") {
				$(frm.wrapper).on("grid-row-render.retailedge", function (_event, gridRow) {
					try {
						if (!self.shouldHide()) {
							return;
						}

						const parentFieldname = gridRow && gridRow.parentfield;
						const grid =
							parentFieldname &&
							frm.fields_dict &&
							frm.fields_dict[parentFieldname] &&
							frm.fields_dict[parentFieldname].grid;
						if (!grid) {
							return;
						}

						self.hideGridRowFormCostFields(frm, grid, gridRow);
						setTimeout(function () {
							self.hideGridRowFormCostFields(frm, grid, gridRow);
						}, 0);
						setTimeout(function () {
							self.hideGridRowFormCostFields(frm, grid, gridRow);
						}, 100);
						setTimeout(function () {
							self.hideGridRowFormCostFields(frm, grid, gridRow);
						}, 400);
					} catch (error) {
						// Ignore grid-row-render handler errors.
					}
				});
			}
		},
		apply: async function (frm) {
			try {
				await this.loadRules();
				this.bindGridEvents(frm);
				if (!this.shouldHide()) {
					return;
				}

				this.hideCostFieldsOnForm(frm);
				this.hideGridCostColumns(frm);
				this.applyStockEntryProtection(frm);

				try {
					frm.refresh_fields();
				} catch (error) {
					// Ignore field refresh errors.
				}
			} catch (error) {
				// Never let RetailEdge UI protection break a form.
			}
		},
	};

	function registerRetailEdgeFormHandlers(attempt) {
		if (
			typeof frappe === "undefined" ||
			!frappe.ui ||
			!frappe.ui.form ||
			!frappe.ui.form.on
		) {
			if ((attempt || 0) < 20) {
				setTimeout(function () {
					registerRetailEdgeFormHandlers((attempt || 0) + 1);
				}, 500);
			}
			return;
		}

		if (window.retailedge.__formHandlersRegistered) {
			return;
		}

		window.retailedge.__formHandlersRegistered = true;

		COST_FORM_DOCTYPES.forEach(function (doctype) {
			try {
				frappe.ui.form.on(doctype, {
					refresh(frm) {
						window.retailedge.costVisibility.apply(frm);
					},
					onload_post_render(frm) {
						window.retailedge.costVisibility.apply(frm);
					},
				});
			} catch (error) {
				// Ignore DocType registration errors.
			}
		});

		try {
			frappe.ui.form.on("Stock Entry", {
				refresh(frm) {
					window.retailedge.costVisibility.apply(frm);
				},
				onload_post_render(frm) {
					window.retailedge.costVisibility.apply(frm);
				},
				items_on_form_rendered(frm) {
					window.retailedge.costVisibility.applyStockEntryProtection(frm);
				},
				items_add(frm) {
					window.retailedge.costVisibility.applyStockEntryProtection(frm);
				},
			});
		} catch (error) {
			// Ignore Stock Entry parent event registration errors.
		}

		try {
			frappe.ui.form.on("Stock Entry Detail", {
				form_render(frm) {
					const targetFrm = frm && frm.doctype === "Stock Entry" ? frm : cur_frm;
					window.retailedge.costVisibility.applyStockEntryProtection(targetFrm);
				},
			});
		} catch (error) {
			// Ignore Stock Entry Detail event registration errors.
		}
	}

	registerRetailEdgeFormHandlers(0);
})();
