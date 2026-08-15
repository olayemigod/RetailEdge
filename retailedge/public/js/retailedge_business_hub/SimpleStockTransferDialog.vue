<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Simple Stock Transfer'"
		:subtitle="formContext.subtitle || 'Create a standard ERPNext Material Transfer draft.'"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-stock-state">
			<EdgeLoadingState message="Preparing Stock Transfer..." :skeleton="true" />
		</div>

		<div v-else-if="loadError" class="guided-stock-state">
			<EdgeErrorState
				title="Stock Transfer unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>

		<form v-else class="guided-stock-form" @submit.prevent="saveDraft">
			<div class="guided-stock-context">
				<div>
					<span>Company</span>
					<strong>{{ values.company || 'Not set' }}</strong>
				</div>
				<div>
					<span>Transfer Type</span>
					<strong>Material Transfer</strong>
				</div>
			</div>

			<div v-if="saveError" class="guided-stock-error" role="alert">
				{{ saveError }}
			</div>

			<div class="guided-stock-grid">
				<label class="guided-field">
					<span>Posting Date <b>*</b></span>
					<input v-model="values.posting_date" class="form-control" type="date" required />
				</label>

				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.source_branch"
					label="Source Branch"
					placeholder="Search source branch"
					:searcher="searchSourceBranch"
					:context="searchContext"
					@update:modelValue="setSourceBranch"
				/>

				<EdgeLinkField
					:modelValue="values.source_warehouse"
					label="Source Warehouse"
					placeholder="Search source warehouse"
					:required="true"
					:searcher="searchSourceWarehouse"
					:context="searchContext"
					@update:modelValue="setSourceWarehouse"
				/>

				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.target_branch"
					label="Target Branch"
					placeholder="Search target branch"
					:searcher="searchTargetBranch"
					:context="searchContext"
					@update:modelValue="setTargetBranch"
				/>

				<EdgeLinkField
					:modelValue="values.target_warehouse"
					label="Target Warehouse"
					placeholder="Search target warehouse"
					:required="true"
					:searcher="searchTargetWarehouse"
					:context="searchContext"
					@update:modelValue="setTargetWarehouse"
				/>
			</div>

			<div v-if="sameWarehouse" class="guided-stock-error" role="alert">
				Source Warehouse and Target Warehouse must be different.
			</div>

			<EdgeChildTable
				:field="itemTableField"
				:rows="values.items"
				:columns="itemColumns"
				:addLabel="'Add Item'"
				:linkSearcher="searchLineLink"
				@update:rows="updateItems"
			/>

			<p class="guided-stock-hint">
				This fast flow is for ordinary stock items. Serial-numbered or batch-managed items require the
				full ERPNext Stock Entry so the correct serial/batch allocations can be selected.
			</p>

			<label class="guided-field guided-field--wide">
				<span>Remarks</span>
				<textarea
					v-model="values.remarks"
					class="form-control"
					rows="3"
					placeholder="Optional transfer note"
				></textarea>
			</label>
		</form>

		<template #footer>
			<div class="guided-stock-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">
					Open Full Form
				</button>
				<div class="guided-stock-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">
						Cancel
					</button>
					<button
						type="button"
						class="edge-button edge-button--primary"
						:disabled="saving || loading || sameWarehouse"
						@click="saveDraft"
					>
						{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft' }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const CONTEXT_METHOD = "retailedge.guided_stock_transfer.get_simple_stock_transfer_context";
const SEARCH_METHOD = "retailedge.guided_stock_transfer.search_simple_stock_transfer_options";
const CREATE_METHOD = "retailedge.guided_stock_transfer.create_simple_stock_transfer_draft";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		company: "",
		posting_date: "",
		source_branch: "",
		target_branch: "",
		source_warehouse: "",
		target_warehouse: "",
		remarks: "",
		items: [{ item_code: "", qty: 1 }],
	};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	if (error?.message) return error.message;
	if (error?.exc_type) return error.exc_type;
	return fallback;
}

export default {
	name: "SimpleStockTransferDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeChildTable: runtimeComponents.EdgeChildTable,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			values: emptyValues(),
			itemTableField: {
				label: "Items",
				description: "Add the stock items and quantities to move.",
			},
			itemColumns: [
				{
					fieldname: "item_code",
					label: "Item",
					fieldtype: "Link",
					placeholder: "Search stock item",
				},
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
			],
		};
	},
	computed: {
		branchEnabled() {
			return Boolean(this.formContext.capabilities?.branch_enabled);
		},
		searchContext() {
			return {
				company: this.values.company,
				source_branch: this.values.source_branch,
				target_branch: this.values.target_branch,
			};
		},
		sameWarehouse() {
			return Boolean(
				this.values.source_warehouse &&
					this.values.target_warehouse &&
					this.values.source_warehouse === this.values.target_warehouse
			);
		},
	},
	watch: {
		open(next) {
			if (next) this.loadContext();
		},
	},
	mounted() {
		if (this.open) this.loadContext();
	},
	methods: {
		async loadContext() {
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			try {
				const data = await callMethod(CONTEXT_METHOD);
				this.formContext = data || {};
				this.values = {
					...emptyValues(),
					...(data.defaults || {}),
					items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })),
				};
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Simple Stock Transfer.");
			} finally {
				this.loading = false;
			}
		},
		requestClose() {
			if (this.saving) return;
			this.$emit("close");
		},
		openFullForm() {
			if (this.saving) return;
			this.$emit("open-native", "Stock Entry");
		},
		async searchOptions(fieldname, query) {
			const results = await callMethod(SEARCH_METHOD, {
				fieldname,
				txt: query || "",
				values: this.searchContext,
			});
			return Array.isArray(results) ? results : [];
		},
		searchSourceBranch(query) {
			return this.searchOptions("source_branch", query);
		},
		searchTargetBranch(query) {
			return this.searchOptions("target_branch", query);
		},
		searchSourceWarehouse(query) {
			return this.searchOptions("source_warehouse", query);
		},
		searchTargetWarehouse(query) {
			return this.searchOptions("target_warehouse", query);
		},
		searchLineLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve([]);
			return this.searchOptions("item_code", query);
		},
		setSourceBranch(next) {
			if (this.values.source_branch !== (next || "")) {
				this.values.source_branch = next || "";
				this.values.source_warehouse = "";
			}
		},
		setTargetBranch(next) {
			if (this.values.target_branch !== (next || "")) {
				this.values.target_branch = next || "";
				this.values.target_warehouse = "";
			}
		},
		setSourceWarehouse(next) {
			this.values.source_warehouse = next || "";
		},
		setTargetWarehouse(next) {
			this.values.target_warehouse = next || "";
		},
		updateItems(nextRows) {
			this.values.items = (nextRows || []).map((row) => ({ ...row }));
		},
		async saveDraft() {
			if (this.saving || this.loading || this.sameWarehouse) return;
			this.saveError = "";
			this.saving = true;
			try {
				const result = await callMethod(CREATE_METHOD, { values: this.values });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Stock Transfer draft.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.guided-stock-state {
	min-height: 220px;
	padding: 18px 0;
}
.guided-stock-form {
	display: grid;
	gap: 18px;
}
.guided-stock-context {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
}
.guided-stock-context > div {
	display: grid;
	gap: 3px;
	min-width: 180px;
	padding: 9px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
	background: var(--edge-surface-muted, #f8fafc);
}
.guided-stock-context span,
.guided-field > span {
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}
.guided-stock-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 14px;
}
.guided-field {
	display: grid;
	gap: 6px;
}
.guided-field > span {
	font-weight: 600;
	color: var(--edge-text, #344054);
}
.guided-field--wide {
	grid-column: 1 / -1;
}
.guided-stock-error {
	padding: 10px 12px;
	border: 1px solid var(--edge-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-danger, #b42318);
	background: var(--edge-danger-subtle, #fef3f2);
}
.guided-stock-hint {
	margin: -8px 0 0;
	font-size: 0.8rem;
	color: var(--edge-text-muted, #667085);
}
.guided-stock-footer,
.guided-stock-footer-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}
.guided-stock-footer {
	width: 100%;
	justify-content: space-between;
}
@media (max-width: 720px) {
	.guided-stock-grid {
		grid-template-columns: 1fr;
	}
	.guided-stock-footer {
		align-items: stretch;
		flex-direction: column-reverse;
	}
	.guided-stock-footer-actions {
		justify-content: flex-end;
	}
}
</style>
