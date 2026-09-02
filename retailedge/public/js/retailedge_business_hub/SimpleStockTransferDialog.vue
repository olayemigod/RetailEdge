<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Simple Stock Transfer'"
		:subtitle="formContext.subtitle || 'Create a stock transfer draft using ERPNext stock controls.'"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-stock-state">
			<EdgeLoadingState message="Preparing Stock Transfer..." :skeleton="true" />
		</div>

		<div v-else-if="loadError" class="guided-stock-state">
			<EdgeErrorState
				title="Stock Transfer entry unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>

		<form v-else class="guided-stock-form" @submit.prevent="saveDraft">
			<div class="guided-stock-context" aria-label="Transfer context">
				<div>
					<span>Company</span>
					<strong>{{ values.company || 'Not set' }}</strong>
				</div>
				<div>
					<span>Purpose</span>
					<strong>{{ formContext.purpose || 'Material Transfer' }}</strong>
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
					description="Loads the branch's assigned source stock location when available."
					:searcher="searchSourceBranch"
					:context="searchContext"
					@update:modelValue="setSourceBranch"
				/>

				<EdgeLinkField
					:modelValue="values.source_warehouse"
					label="Source Stock Location"
					placeholder="Search source stock location"
					description="Selecting an assigned stock location resolves its Branch automatically."
					:required="true"
					:searcher="searchSourceWarehouse"
					:context="searchContext"
					@update:modelValue="setSourceWarehouse"
				/>

				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.target_branch"
					label="Destination Branch"
					placeholder="Search destination branch"
					description="Loads the branch's assigned destination stock location when available."
					:searcher="searchTargetBranch"
					:context="searchContext"
					@update:modelValue="setTargetBranch"
				/>

				<EdgeLinkField
					:modelValue="values.target_warehouse"
					label="Destination Stock Location"
					placeholder="Search destination stock location"
					description="Selecting an assigned stock location resolves its Branch automatically."
					:required="true"
					:searcher="searchTargetWarehouse"
					:context="searchContext"
					@update:modelValue="setTargetWarehouse"
				/>
			</div>

			<div v-if="sameWarehouse" class="guided-stock-warning" role="alert">
				Source and Destination Stock Location must be different.
			</div>

			<EdgeChildTable
				:field="itemTableField"
				:rows="values.items"
				:columns="itemColumns"
				:addLabel="'Add Item'"
				:linkSearcher="searchLineLink"
				:linkCanCreate="canCreateItemLink"
				:linkCreator="createItemLink"
				:linkCreateLabel="itemCreateLabel"
				:newRowsFirst="true"
				@update:rows="updateItems"
			/>

			<p class="guided-stock-hint">
				Serial-numbered or batch-managed items require the full Stock Entry form so ERPNext can
				capture the exact Serial No or Batch allocations. Item creation remains native ERPNext
				Quick Entry and is shown only when the server confirms your session can create Items.
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
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="saving" @click="openFullForm">
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
import {
	callMethod,
	errorMessage,
	quickCreateItem,
	resolveBranchWarehouse,
} from "./guidedEntryUtils";

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
		nativeFallbackEnabled: { type: Boolean, default: true },
		open: { type: Boolean, default: false },
		prefill: { type: Object, default: () => ({}) },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			sourceCascadeToken: 0,
			targetCascadeToken: 0,
			formContext: {},
			values: emptyValues(),
			itemTableField: {
				label: "Items",
				description: "Newest item rows stay at the top for faster multi-item entry.",
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
		canCreateItem() {
			return Boolean(this.formContext.capabilities?.can_create_item);
		},
		searchContext() {
			return {
				company: this.values.company,
				source_branch: this.values.source_branch,
				target_branch: this.values.target_branch,
				source_warehouse: this.values.source_warehouse,
				target_warehouse: this.values.target_warehouse,
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
				const args = {};
				if (this.prefill?.company) args.company = this.prefill.company;
				const data = await callMethod(CONTEXT_METHOD, args);
				this.formContext = data || {};
				this.values = {
					...emptyValues(),
					...(data.defaults || {}),
					items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })),
				};
				await this.applyPrefill();
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Stock Transfer.");
			} finally {
				this.loading = false;
			}
		},
		async applyPrefill() {
			const prefill = this.prefill || {};
			const sourceWarehouse = String(prefill.source_warehouse || "").trim();
			const targetWarehouse = String(prefill.target_warehouse || "").trim();
			const itemCode = String(prefill.item_code || "").trim();
			const qty = Number(prefill.qty || 0);
			if (!sourceWarehouse && !targetWarehouse && !itemCode) return;

			// A recommendation is warehouse-specific. Clear generic branch defaults and
			// let the existing warehouse cascade resolve the permitted branch for each end.
			this.values.source_branch = "";
			this.values.target_branch = "";
			this.values.source_warehouse = "";
			this.values.target_warehouse = "";
			if (itemCode && Number.isFinite(qty) && qty > 0) {
				this.values.items = [{ item_code: itemCode, qty }];
			}
			if (sourceWarehouse) await this.setSourceWarehouse(sourceWarehouse);
			if (targetWarehouse) await this.setTargetWarehouse(targetWarehouse);
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
				values: { ...this.values, items: undefined },
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
		canCreateItemLink(column) {
			return this.canCreateItem && column?.fieldname === "item_code";
		},
		createItemLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve(null);
			return quickCreateItem(query, { stockItem: true });
		},
		itemCreateLabel(column) {
			return column?.fieldname === "item_code" ? "Create Stock Item" : "Create new";
		},
		async setSourceBranch(next) {
			const branch = next || "";
			this.values.source_branch = branch;
			this.values.source_warehouse = "";
			if (!branch || !this.values.company) return;
			const token = ++this.sourceCascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch,
					preference: "source",
				});
				if (token !== this.sourceCascadeToken) return;
				this.values.source_branch = resolved.branch || branch;
				this.values.source_warehouse = resolved.warehouse || "";
				if (this.sameWarehouse) this.values.target_warehouse = "";
			} catch (error) {
				if (token === this.sourceCascadeToken) {
					this.saveError = errorMessage(error, "Unable to resolve the Source Branch stock location.");
				}
			}
		},
		async setTargetBranch(next) {
			const branch = next || "";
			this.values.target_branch = branch;
			this.values.target_warehouse = "";
			if (!branch || !this.values.company) return;
			const token = ++this.targetCascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch,
					preference: "target",
				});
				if (token !== this.targetCascadeToken) return;
				this.values.target_branch = resolved.branch || branch;
				this.values.target_warehouse =
					resolved.warehouse && resolved.warehouse !== this.values.source_warehouse
						? resolved.warehouse
						: "";
			} catch (error) {
				if (token === this.targetCascadeToken) {
					this.saveError = errorMessage(error, "Unable to resolve the Destination Branch stock location.");
				}
			}
		},
		async setSourceWarehouse(next) {
			const warehouse = next || "";
			this.values.source_warehouse = warehouse;
			if (!warehouse || !this.values.company) return;
			const token = ++this.sourceCascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch: this.values.source_branch,
					warehouse,
					preference: "source",
				});
				if (token !== this.sourceCascadeToken) return;
				this.values.source_branch = resolved.branch || this.values.source_branch;
				this.values.source_warehouse = resolved.warehouse || warehouse;
				if (this.sameWarehouse) this.values.target_warehouse = "";
			} catch (error) {
				if (token === this.sourceCascadeToken) {
					this.values.source_warehouse = "";
					this.saveError = errorMessage(error, "Unable to use the selected Source Stock Location.");
				}
			}
		},
		async setTargetWarehouse(next) {
			const warehouse = next || "";
			this.values.target_warehouse = warehouse;
			if (!warehouse || !this.values.company) return;
			if (warehouse === this.values.source_warehouse) {
				this.values.target_warehouse = "";
				this.saveError = "Source and Destination Stock Location must be different.";
				return;
			}
			const token = ++this.targetCascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch: this.values.target_branch,
					warehouse,
					preference: "target",
				});
				if (token !== this.targetCascadeToken) return;
				this.values.target_branch = resolved.branch || this.values.target_branch;
				this.values.target_warehouse = resolved.warehouse || warehouse;
			} catch (error) {
				if (token === this.targetCascadeToken) {
					this.values.target_warehouse = "";
					this.saveError = errorMessage(error, "Unable to use the selected Destination Stock Location.");
				}
			}
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
	gap: 2px;
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
.guided-stock-hint {
	margin: -8px 0 0;
	font-size: 0.8rem;
	color: var(--edge-text-muted, #667085);
}
.guided-stock-error,
.guided-stock-warning {
	padding: 10px 12px;
	border-radius: 8px;
}
.guided-stock-error {
	border: 1px solid var(--edge-danger, #d92d20);
	color: var(--edge-danger, #b42318);
	background: var(--edge-danger-subtle, #fef3f2);
}
.guided-stock-warning {
	border: 1px solid var(--edge-warning, #f79009);
	color: var(--edge-warning-text, #7a2e0e);
	background: var(--edge-warning-subtle, #fffaeb);
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