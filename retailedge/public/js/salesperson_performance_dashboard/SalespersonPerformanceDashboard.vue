<template>
	<EdgeAppShell
		product="retailedge"
		:menu-items="menuItems"
		active-route="/app/salesperson-performance-dashboard"
		title="RetailEdge"
		:tenant-name="tenantName"
		:branch-name="workingBranchLabel"
		:user-name="userName"
		@navigate="handleNavigation"
		data-edge-product="retailedge"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					title="Salesperson Performance"
					subtitle="Review proportional salesperson allocations from submitted invoices without changing ERPNext sales or accounting records."
					:with-back-button="false"
				/>
			</template>

			<EdgeBranchContextSwitcher
				v-model="filters.branch"
				:options="branchOptions"
				:current-label="workingBranchLabel"
				:current-company="filters.company"
				:can-switch="branchOptions.length > 0"
				:busy="metadataLoading || loading"
				label="Reporting branch"
				helper="The selected branch limits dashboard results. Leaving it blank includes only branches you are permitted to access."
				placeholder="All permitted branches"
				@switch="onBranchSwitch"
			/>

			<EdgeFilterBar title="Filter performance">
				<div class="salesperson-filter-grid">
					<div class="salesperson-filter-field">
						<label for="salesperson-date-preset">Date range</label>
						<select
							id="salesperson-date-preset"
							v-model="filters.date_range_preset"
							class="form-control"
							:disabled="metadataLoading"
							@change="onPresetChange"
						>
							<option v-for="preset in datePresets" :key="preset" :value="preset">{{ preset }}</option>
						</select>
					</div>

					<div class="salesperson-filter-field">
						<label for="salesperson-from-date">From date</label>
						<input
							id="salesperson-from-date"
							v-model="filters.from_date"
							type="date"
							class="form-control"
							:disabled="metadataLoading"
							@change="onDateChange"
						/>
					</div>

					<div class="salesperson-filter-field">
						<label for="salesperson-to-date">To date</label>
						<input
							id="salesperson-to-date"
							v-model="filters.to_date"
							type="date"
							class="form-control"
							:disabled="metadataLoading"
							@change="onDateChange"
						/>
					</div>

					<EdgeLinkField
						v-model="filters.salesperson"
						:selected-label="selectedLabels.salesperson || filters.salesperson"
						label="Salesperson"
						placeholder="Search enabled salespeople"
						description="Results load as you search; the dashboard does not preload every salesperson."
						:searcher="searchSalespeople"
						:context="linkContext"
						:disabled="metadataLoading"
						:min-chars="0"
						@select="onLinkSelect('salesperson', $event)"
						@clear="onLinkClear('salesperson')"
						@search-error="onLinkSearchError"
					/>

					<EdgeLinkField
						v-model="filters.customer"
						:selected-label="selectedLabels.customer || filters.customer"
						label="Customer"
						placeholder="Search permitted customers"
						description="Only active customers readable by the current user are returned."
						:searcher="searchCustomers"
						:context="linkContext"
						:disabled="metadataLoading"
						:min-chars="0"
						@select="onLinkSelect('customer', $event)"
						@clear="onLinkClear('customer')"
						@search-error="onLinkSearchError"
					/>

					<EdgeLinkField
						v-model="filters.item"
						:selected-label="selectedLabels.item || filters.item"
						label="Item"
						placeholder="Search active sales items"
						description="The selected Item Code filters submitted invoice items exactly."
						:searcher="searchItems"
						:context="linkContext"
						:disabled="metadataLoading"
						:min-chars="0"
						@select="onLinkSelect('item', $event)"
						@clear="onLinkClear('item')"
						@search-error="onLinkSearchError"
					/>

					<div class="salesperson-filter-action">
						<button
							type="button"
							class="edge-button edge-button--primary"
							:disabled="metadataLoading || loading"
							@click="applyFilters"
						>
							{{ loading ? "Refreshing…" : "Apply / Refresh" }}
						</button>
					</div>
				</div>
			</EdgeFilterBar>

			<div v-if="error" class="salesperson-dashboard-state">
				<EdgeErrorState title="Performance dashboard could not load" :message="error" @retry="fetchMetadata" />
			</div>
			<div v-else-if="loading && !rows.length" class="salesperson-dashboard-state">
				<EdgeLoadingState message="Calculating proportional salesperson performance…" :skeleton="true" />
			</div>
			<template v-else>
				<div class="edge-stat-grid salesperson-summary-grid">
					<EdgeStatCard label="Gross sales" :value="formatCurrency(summary.gross_sales)" tooltip="Allocated grand total using the Sales Team percentage.">
						<template #icon><EdgeIcon name="wallet" size="md" /></template>
					</EdgeStatCard>
					<EdgeStatCard label="Net sales" :value="formatCurrency(summary.net_sales)" tooltip="Allocated net total excluding taxes.">
						<template #icon><EdgeIcon name="chart" size="md" /></template>
					</EdgeStatCard>
					<EdgeStatCard label="Sales invoices" :value="summary.total_invoices || 0" tooltip="Unique submitted invoices represented in the selected scope.">
						<template #icon><EdgeIcon name="report" size="md" /></template>
					</EdgeStatCard>
					<EdgeStatCard label="Average invoice value" :value="formatCurrency(summary.avg_invoice_value)" tooltip="Gross allocated value divided by unique invoices.">
						<template #icon><EdgeIcon name="assessment" size="md" /></template>
					</EdgeStatCard>
					<EdgeStatCard label="Total discount" :value="formatCurrency(summary.total_discount)" tooltip="Allocated discount value.">
						<template #icon><EdgeIcon name="activity" size="md" /></template>
					</EdgeStatCard>
					<EdgeStatCard label="Outstanding" :value="formatCurrency(summary.total_outstanding)" tone="warning" tooltip="Allocated outstanding invoice amount.">
						<template #icon><EdgeIcon name="bell" size="md" /></template>
					</EdgeStatCard>
				</div>

				<section v-if="rows.length" class="salesperson-table-card">
					<div class="salesperson-table-scroll">
						<table class="salesperson-dashboard-table">
							<thead>
								<tr>
									<th>Salesperson</th>
									<th>Sales invoice</th>
									<th>Date</th>
									<th>Customer</th>
									<th>Items sold</th>
									<th class="is-number">Qty</th>
									<th class="is-number">Gross split</th>
									<th class="is-number">Discount split</th>
									<th class="is-number">Net split</th>
									<th class="is-number">Outstanding split</th>
									<th>Status</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in rows" :key="`${row.salesperson}-${row.sales_invoice}`">
									<td><button type="button" class="salesperson-doc-link" @click="openDoc('Sales Person', row.salesperson)">{{ row.salesperson }}</button></td>
									<td><button type="button" class="salesperson-doc-link" @click="openDoc('Sales Invoice', row.sales_invoice)">{{ row.sales_invoice }}</button></td>
									<td>{{ formatDate(row.posting_date) }}</td>
									<td><button type="button" class="salesperson-doc-link" @click="openDoc('Customer', row.customer)">{{ row.customer }}</button></td>
									<td class="salesperson-items-cell" :title="row.items">{{ row.items || "—" }}</td>
									<td class="is-number">{{ row.total_qty || 0 }}</td>
									<td class="is-number">{{ formatCurrency(row.gross_amount) }}</td>
									<td class="is-number is-muted">{{ formatCurrency(row.discount) }}</td>
									<td class="is-number is-strong">{{ formatCurrency(row.net_amount) }}</td>
									<td class="is-number" :class="{ 'is-danger': Number(row.outstanding_amount || 0) > 0 }">{{ formatCurrency(row.outstanding_amount) }}</td>
									<td><EdgeStatusBadge :label="row.payment_status" :status="row.payment_status" :tone="paymentTone(row.payment_status)" /></td>
								</tr>
							</tbody>
						</table>
					</div>
					<footer class="salesperson-pagination">
						<span>Page {{ currentPage }} · {{ rows.length }} row(s)</span>
						<div>
							<button type="button" class="edge-button edge-button--compact" :disabled="currentPage === 1 || loading" @click="changePage(-1)">Previous</button>
							<button type="button" class="edge-button edge-button--compact" :disabled="rows.length < filters.limit || loading" @click="changePage(1)">Next</button>
						</div>
					</footer>
				</section>
				<div v-else class="salesperson-dashboard-state">
					<EdgeEmptyState title="No salesperson attribution found" description="No submitted invoice allocation matched the selected company, branch, date and Link filters." icon="search" />
				</div>
			</template>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
export default {
	name: "SalespersonPerformanceDashboard",
	data() {
		return {
			metadataLoading: true,
			loading: true,
			error: "",
			summary: {},
			rows: [],
			branchOptions: [],
			currentPage: 1,
			tenantName: "",
			userName: "",
			requestToken: 0,
			selectedLabels: { salesperson: "", customer: "", item: "" },
			filters: {
				company: "",
				date_range_preset: "This Month",
				from_date: "",
				to_date: "",
				branch: "",
				salesperson: "",
				customer: "",
				item: "",
				limit: 50,
				offset: 0,
			},
			datePresets: [
				"This Month", "Today", "Yesterday", "This Week", "This Quarter", "This Year",
				"Last Week", "Last Month", "Last Quarter", "Last Year", "Custom Period", "Full History",
			],
			menuItems: [
				{ label: "RetailEdge Home", route: "/app/retailedge-home" },
				{ label: "Salesperson Performance", route: "/app/salesperson-performance-dashboard" },
				{ label: "Sales Invoices", route: "/app/sales-invoice" },
				{ label: "Salespeople", route: "/app/sales-person" },
				{ label: "Customers", route: "/app/customer" },
			],
		};
	},
	computed: {
		workingBranchLabel() {
			return this.filters.branch || "All permitted branches";
		},
		linkContext() {
			return {
				company: this.filters.company,
				branch: this.filters.branch,
				from_date: this.filters.from_date,
				to_date: this.filters.to_date,
				salesperson: this.filters.salesperson,
				customer: this.filters.customer,
			};
		},
	},
	mounted() {
		this.fetchMetadata();
	},
	methods: {
		normalizeError(error, fallback) {
			return error?.message || error?.exc_type || error?._server_messages || fallback;
		},
		async call(method, args = {}) {
			const response = await window.frappe.call(method, args);
			return response?.message;
		},
		async fetchMetadata() {
			this.metadataLoading = true;
			this.loading = true;
			this.error = "";
			try {
				const payload = await this.call("retailedge.salesperson_performance.get_salesperson_dashboard_options");
				this.branchOptions = payload?.branch_options || (payload?.branches || []).map((value) => ({ value, label: value }));
				this.tenantName = payload?.tenant_name || payload?.company || "Retail Business";
				this.userName = payload?.user_name || window.frappe?.session?.user || "RetailEdge User";
				this.filters = { ...this.filters, ...(payload?.default_filters || {}) };
				this.currentPage = 1;
				await this.fetchData();
			} catch (error) {
				this.error = this.normalizeError(error, "Failed to load dashboard context.");
				this.loading = false;
			} finally {
				this.metadataLoading = false;
			}
		},
		async searchLink(fieldname, query) {
			return (await this.call("retailedge.salesperson_performance.search_salesperson_dashboard_link", {
				fieldname,
				txt: query || "",
				context: this.linkContext,
				limit: 20,
			})) || [];
		},
		searchSalespeople(query) {
			return this.searchLink("salesperson", query);
		},
		searchCustomers(query) {
			return this.searchLink("customer", query);
		},
		searchItems(query) {
			return this.searchLink("item", query);
		},
		onLinkSearchError(error) {
			window.frappe?.show_alert?.({ message: this.normalizeError(error, "Link search failed."), indicator: "orange" });
		},
		onLinkSelect(fieldname, option) {
			this.selectedLabels[fieldname] = option?.label || option?.value || "";
			if (fieldname === "customer") {
				this.filters.item = "";
				this.selectedLabels.item = "";
			}
			this.applyFilters();
		},
		onLinkClear(fieldname) {
			this.selectedLabels[fieldname] = "";
			if (fieldname === "customer") {
				this.filters.item = "";
				this.selectedLabels.item = "";
			}
			this.applyFilters();
		},
		onBranchSwitch(option) {
			this.filters.branch = option?.value || "";
			this.filters.customer = "";
			this.filters.item = "";
			this.selectedLabels.customer = "";
			this.selectedLabels.item = "";
			this.applyFilters();
		},
		async onPresetChange() {
			const preset = this.filters.date_range_preset;
			if (preset && preset !== "Custom Period") {
				const dates = window.retailedge?.getPresetDates?.(preset);
				if (dates) {
					this.__applyingPreset = true;
					this.filters.from_date = dates.from_date || "";
					this.filters.to_date = dates.to_date || "";
					await this.$nextTick();
					this.__applyingPreset = false;
				}
			}
			this.applyFilters();
		},
		onDateChange() {
			if (!this.__applyingPreset && this.filters.date_range_preset !== "Custom Period") {
				const dates = window.retailedge?.getPresetDates?.(this.filters.date_range_preset);
				if (!dates || (this.filters.from_date || "") !== (dates.from_date || "") || (this.filters.to_date || "") !== (dates.to_date || "")) {
					this.filters.date_range_preset = "Custom Period";
				}
			}
			this.applyFilters();
		},
		applyFilters() {
			this.currentPage = 1;
			this.fetchData();
		},
		async fetchData() {
			if (this.filters.from_date && this.filters.to_date && this.filters.from_date > this.filters.to_date) {
				this.error = "From Date cannot be after To Date.";
				this.loading = false;
				return;
			}
			const token = ++this.requestToken;
			this.loading = true;
			this.error = "";
			this.filters.offset = (this.currentPage - 1) * this.filters.limit;
			try {
				const payload = await this.call("retailedge.salesperson_performance.get_salesperson_performance", { filters: this.filters });
				if (token !== this.requestToken) return;
				this.summary = payload?.summary || {};
				this.rows = payload?.rows || [];
			} catch (error) {
				if (token !== this.requestToken) return;
				this.error = this.normalizeError(error, "Performance aggregation failed.");
			} finally {
				if (token === this.requestToken) this.loading = false;
			}
		},
		changePage(direction) {
			this.currentPage = Math.max(1, this.currentPage + direction);
			this.fetchData();
		},
		formatDate(value) {
			return value && window.frappe?.datetime?.str_to_user ? window.frappe.datetime.str_to_user(value) : value || "—";
		},
		formatCurrency(value) {
			const amount = Number(value || 0);
			const currency = window.frappe?.boot?.sysdefaults?.currency || "NGN";
			if (window.frappe?.format_value) return window.frappe.format_value(amount, { fieldtype: "Currency", options: currency });
			return `${currency} ${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
		},
		paymentTone(status) {
			const value = String(status || "").toLowerCase();
			if (value.includes("paid") && !value.includes("unpaid")) return "success";
			if (value.includes("overdue")) return "danger";
			if (value.includes("unpaid") || value.includes("outstanding")) return "warning";
			return "neutral";
		},
		openDoc(doctype, name) {
			if (doctype && name) window.frappe?.set_route?.("Form", doctype, name);
		},
		handleNavigation(route) {
			if (window.RetailEdgeUIBridge?.openRoute?.(route)) return;
			if (route) window.location.assign(route);
		},
	},
};
</script>

<style scoped>
.salesperson-filter-grid {
	display: grid;
	gap: 0.8rem;
	grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
	width: 100%;
}

.salesperson-filter-field {
	display: grid;
	gap: 0.35rem;
	min-width: 0;
}

.salesperson-filter-field label {
	color: var(--text-muted, #6b7d90);
	font-size: 0.72rem;
	font-weight: 700;
}

.salesperson-filter-action {
	align-items: end;
	display: flex;
}

.salesperson-filter-action .edge-button {
	min-height: 2.5rem;
	width: 100%;
}

.salesperson-summary-grid {
	margin: 1rem 0;
}

.salesperson-dashboard-state {
	margin-top: 1rem;
}

.salesperson-table-card {
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #dce5ef);
	border-radius: var(--edge-radius-lg, 1rem);
	overflow: hidden;
}

.salesperson-table-scroll {
	overflow-x: auto;
}

.salesperson-dashboard-table {
	border-collapse: collapse;
	font-size: 0.76rem;
	min-width: 78rem;
	width: 100%;
}

.salesperson-dashboard-table th,
.salesperson-dashboard-table td {
	border-bottom: 1px solid var(--border-color, #dce5ef);
	padding: 0.75rem;
	text-align: left;
	vertical-align: middle;
	white-space: nowrap;
}

.salesperson-dashboard-table th {
	background: var(--subtle-fg, #f8fafc);
	color: var(--text-muted, #6b7d90);
	font-weight: 700;
}

.salesperson-dashboard-table tbody tr:hover {
	background: var(--subtle-fg, #f8fafc);
}

.salesperson-dashboard-table .is-number {
	font-variant-numeric: tabular-nums;
	text-align: right;
}

.salesperson-dashboard-table .is-muted {
	color: var(--text-muted, #6b7d90);
}

.salesperson-dashboard-table .is-strong {
	font-weight: 700;
}

.salesperson-dashboard-table .is-danger {
	color: var(--red-600, #b42318);
	font-weight: 700;
}

.salesperson-items-cell {
	max-width: 14rem;
	overflow: hidden;
	text-overflow: ellipsis;
}

.salesperson-doc-link {
	background: transparent;
	border: 0;
	color: var(--primary, #0b6e99);
	cursor: pointer;
	font: inherit;
	font-weight: 600;
	padding: 0;
	text-align: left;
}

.salesperson-doc-link:hover,
.salesperson-doc-link:focus-visible {
	text-decoration: underline;
}

.salesperson-pagination {
	align-items: center;
	background: var(--subtle-fg, #f8fafc);
	display: flex;
	flex-wrap: wrap;
	gap: 0.75rem;
	justify-content: space-between;
	padding: 0.75rem 1rem;
}

.salesperson-pagination > div {
	display: flex;
	gap: 0.5rem;
}

@media (max-width: 47.99rem) {
	.salesperson-filter-action {
		align-items: stretch;
	}
	.salesperson-pagination,
	.salesperson-pagination > div {
		align-items: stretch;
		flex-direction: column;
	}
}
</style>
