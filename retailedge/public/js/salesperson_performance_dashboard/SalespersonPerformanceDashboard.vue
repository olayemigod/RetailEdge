<template>
  <div v-if="!edgeUIValid" class="p-6 text-center" style="border: 1px solid var(--edge-danger, #ff4d4f); border-radius: 8px; background-color: var(--edge-surface, #ffffff); margin: 20px;">
    <div style="color: var(--edge-danger, #ff4d4f); font-weight: bold; font-size: 1.2rem; margin-bottom: 12px;">
      EdgeSuite UI failed to load
    </div>
    <div style="color: var(--edge-text-muted, #8c8c8c); margin-bottom: 20px; font-size: 14px;">
      Missing components: {{ missingComponents.join(', ') }}
    </div>
    <button @click="fetchMetadata" style="padding: 8px 16px; background-color: var(--edge-primary, #1890ff); color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600;">
      Retry Loading Dashboard
    </button>
  </div>

  <EdgeAppShell
    v-else
    product="retailedge"
    :menuItems="menuItems"
    activeRoute="/app/salesperson-performance-dashboard"
    title="RetailEdge"
    :tenantName="tenantName"
    :branchName="branchName"
    :userName="userName"
    @navigate="handleNavigation"
    data-edge-product="retailedge"
  >
    <EdgePageLayout>
      <template #header>
        <EdgePageHeader 
          title="Salesperson Performance Dashboard" 
          subtitle="Proportional salesperson allocations for submitted RetailEdge invoices"
          :withBackButton="false"
        />
      </template>
      <!-- EdgeFilterBar in default slot body flow -->
      <EdgeFilterBar title="Filter Records">
        <div class="edge-filter-grid">
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">Date Range Preset</label>
          <select v-model="filters.date_range_preset" class="edge-select filter-select" :disabled="metadataLoading" @change="onPresetChange">
            <option value="This Month">This Month</option>
            <option value="Today">Today</option>
            <option value="Yesterday">Yesterday</option>
            <option value="This Week">This Week</option>
            <option value="This Quarter">This Quarter</option>
            <option value="This Year">This Year</option>
            <option value="Last Week">Last Week</option>
            <option value="Last Month">Last Month</option>
            <option value="Last Quarter">Last Quarter</option>
            <option value="Last Year">Last Year</option>
            <option value="Custom Period">Custom Period</option>
            <option value="Full History">Full History</option>
          </select>
        </div>
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">From Date</label>
          <input type="date" v-model="filters.from_date" class="edge-input filter-input" :disabled="metadataLoading" @change="onDateChange" />
        </div>
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">To Date</label>
          <input type="date" v-model="filters.to_date" class="edge-input filter-input" :disabled="metadataLoading" @change="onDateChange" />
        </div>
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">Branch</label>
          <select v-model="filters.branch" class="edge-select filter-select" :disabled="metadataLoading || branches.length === 0" @change="fetchData">
            <option v-if="metadataLoading" value="">Loading branches...</option>
            <option v-else-if="branches.length === 0" value="">No branch available</option>
            <option v-else value="">All Branches</option>
            <option v-for="b in branches" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">Salesperson</label>
          <select v-model="filters.salesperson" class="edge-select filter-select" :disabled="metadataLoading" @change="fetchData">
            <option v-if="metadataLoading" value="">Loading salespeople...</option>
            <option v-else value="">All Salespeople</option>
            <option v-for="s in salespeople" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">Customer</label>
          <input type="text" v-model="filters.customer" placeholder="Customer Name" class="edge-input filter-input" :disabled="metadataLoading" @input="debounceFetchData" @change="fetchData" />
        </div>
        <div class="edge-field filter-group">
          <label class="edge-field-label filter-label">Item Code / Item Search</label>
          <input type="text" v-model="filters.item" placeholder="Item Code" class="edge-input filter-input" :disabled="metadataLoading" @change="fetchData" />
        </div>
        <div class="edge-field filter-group filter-action-group">
          <label class="edge-field-label filter-label" style="visibility: hidden;">Action</label>
          <button class="edge-primary-button filter-btn primary" :disabled="metadataLoading" @click="fetchData">
            Apply / Refresh
          </button>
        </div>
      </div>
    </EdgeFilterBar>

      <!-- Error/Loading states -->
      <div v-if="error" class="p-6">
        <EdgeErrorState 
          title="Aggregation Query Failed" 
          :message="error" 
          @retry="fetchMetadata"
        />
      </div>

      <div v-else-if="loading" class="p-6">
        <EdgeLoadingState message="Aggregating performance calculations..." :skeleton="true" />
      </div>

      <div v-else>
        <!-- Summary stats grid -->
        <div class="edge-stat-grid summary-stats-grid">
          <EdgeStatCard 
            label="Gross Sales" 
            :value="formatCurrency(summary.gross_sales)" 
            icon="💰" 
            tooltip="Sum of allocated sales total (Gross total * allocation percentage)"
          />
          <EdgeStatCard 
            label="Net Sales" 
            :value="formatCurrency(summary.net_sales)" 
            icon="📈" 
            tooltip="Sum of allocated net sales (excluding taxes)"
          />
          <EdgeStatCard 
            label="Number of Sales Invoices" 
            :value="summary.total_invoices || 0" 
            icon="📝" 
            tooltip="Unique number of submitted invoices attributed to salespeople"
          />
          <EdgeStatCard 
            label="Average Invoice Value" 
            :value="formatCurrency(summary.avg_invoice_value)" 
            icon="📊" 
            tooltip="Average allocated invoice value"
          />
          <EdgeStatCard 
            label="Total Discount" 
            :value="formatCurrency(summary.total_discount)" 
            icon="🏷️" 
            tooltip="Sum of allocated discount value splits"
          />
          <EdgeStatCard 
            label="Outstanding Amount" 
            :value="formatCurrency(summary.total_outstanding)" 
            icon="⚠️" 
            tooltip="Sum of allocated outstanding invoice amount splits"
          />
        </div>

        <!-- Main Data Table -->
        <div v-if="rows.length > 0" class="edge-table-card table-container-card">
          <div class="table-responsive">
            <table class="edge-dashboard-table dashboard-table">
              <thead>
                <tr>
                  <th>Salesperson</th>
                  <th>Sales Invoice</th>
                  <th>Date</th>
                  <th>Customer</th>
                  <th>Items Sold</th>
                  <th class="text-right">Qty</th>
                  <th class="text-right">Gross (Split)</th>
                  <th class="text-right">Disc. (Split)</th>
                  <th class="text-right">Net (Split)</th>
                  <th class="text-right">Outstanding (Split)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.salesperson + '-' + row.sales_invoice">
                  <td class="bold-text">
                    <a href="#" @click.prevent="openDoc('Sales Person', row.salesperson)" class="doc-link">
                      {{ row.salesperson }}
                    </a>
                  </td>
                  <td>
                    <a href="#" @click.prevent="openDoc('Sales Invoice', row.sales_invoice)" class="doc-link">
                      {{ row.sales_invoice }}
                    </a>
                  </td>
                  <td>{{ formatDate(row.posting_date) }}</td>
                  <td>
                    <a href="#" @click.prevent="openDoc('Customer', row.customer)" class="doc-link">
                      {{ row.customer }}
                    </a>
                  </td>
                  <td class="items-cell" :title="row.items">{{ row.items || '--' }}</td>
                  <td class="text-right">{{ row.total_qty || 0 }}</td>
                  <td class="text-right font-mono">{{ formatCurrency(row.gross_amount) }}</td>
                  <td class="text-right font-mono text-muted">{{ formatCurrency(row.discount) }}</td>
                  <td class="text-right font-mono bold-text">{{ formatCurrency(row.net_amount) }}</td>
                  <td class="text-right font-mono" :class="{ 'red-text': row.outstanding_amount > 0 }">
                    {{ formatCurrency(row.outstanding_amount) }}
                  </td>
                  <td>
                    <EdgeStatusBadge :label="row.payment_status" :status="row.payment_status" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div class="pagination-footer">
            <span class="page-info">Showing page {{ currentPage }} ({{ rows.length }} records)</span>
            <div class="pagination-buttons">
              <button 
                class="pagination-btn" 
                :disabled="currentPage === 1" 
                @click="changePage(-1)"
              >
                Previous
              </button>
              <button 
                class="pagination-btn" 
                :disabled="rows.length < filters.limit" 
                @click="changePage(1)"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="empty-state-container">
          <EdgeEmptyState 
            title="No Sales Attribution Found" 
            description="There are no submitted invoices or salesperson splits matching the current filters."
            icon="search"
          />
        </div>
      </div>
    </EdgePageLayout>
  </EdgeAppShell>
</template>

<script>
import { h } from 'vue';

const EdgeAppShell = {
  name: 'EdgeAppShell',
  props: ['product', 'menuItems', 'activeRoute', 'title', 'tenantName', 'branchName', 'userName'],
  emits: ['navigate'],
  render() {
    const menu = (this.menuItems || []).map((item) =>
      h('button', {
        class: ['edge-sidebar-item', item.route === this.activeRoute ? 'active' : ''],
        type: 'button',
        onClick: () => this.$emit('navigate', item.route)
      }, [h('span', { class: 'edge-sidebar-icon' }, item.icon || ''), h('span', item.label || '')])
    );
    const context = [this.tenantName, this.branchName, this.userName].filter(Boolean).join(' · ');
    return h('div', { class: 'edge-app-shell', 'data-edge-product': this.product }, [
      h('div', { class: 'edge-topbar' }, [
        h('div', { class: 'edge-topbar-title' }, this.title || ''),
        h('div', { class: 'edge-topbar-context' }, context)
      ]),
      h('div', { class: 'edge-shell-body' }, [
        h('aside', { class: 'edge-sidebar' }, menu),
        h('main', { class: 'edge-shell-main' }, this.$slots.default ? this.$slots.default() : [])
      ])
    ]);
  }
};

const EdgePageLayout = {
  name: 'EdgePageLayout',
  render() {
    return h('section', { class: 'edge-page-layout' }, [
      this.$slots.header ? h('div', { class: 'edge-page-layout-header' }, this.$slots.header()) : null,
      h('div', { class: 'edge-page-layout-body' }, this.$slots.default ? this.$slots.default() : [])
    ]);
  }
};

const EdgePageHeader = {
  name: 'EdgePageHeader',
  props: ['title', 'subtitle'],
  render() {
    return h('div', { class: 'edge-page-header' }, [
      h('h1', { class: 'edge-page-title' }, this.title || ''),
      this.subtitle ? h('p', { class: 'edge-page-subtitle' }, this.subtitle) : null
    ]);
  }
};

const EdgeFilterBar = {
  name: 'EdgeFilterBar',
  props: ['title'],
  render() {
    return h('section', { class: 'edge-filter-bar' }, [
      this.title ? h('h2', { class: 'edge-filter-title' }, this.title) : null,
      h('div', { class: 'edge-filter-body' }, this.$slots.default ? this.$slots.default() : [])
    ]);
  }
};

const EdgeStatCard = {
  name: 'EdgeStatCard',
  props: ['label', 'value', 'icon', 'tooltip'],
  render() {
    return h('div', { class: 'edge-stat-card', title: this.tooltip || '' }, [
      h('div', { class: 'edge-stat-icon' }, this.icon || ''),
      h('div', { class: 'edge-stat-content' }, [
        h('div', { class: 'edge-stat-label' }, this.label || ''),
        h('div', { class: 'edge-stat-value' }, String(this.value ?? ''))
      ])
    ]);
  }
};

const EdgeStatusBadge = {
  name: 'EdgeStatusBadge',
  props: ['label', 'status'],
  render() {
    const status = String(this.status || this.label || '').toLowerCase().replace(/\s+/g, '-');
    return h('span', { class: ['edge-status-badge', `edge-status-${status}`] }, this.label || this.status || '');
  }
};

const EdgeEmptyState = {
  name: 'EdgeEmptyState',
  props: ['title', 'description', 'icon'],
  render() {
    return h('div', { class: 'edge-empty-state' }, [
      h('div', { class: 'edge-empty-icon' }, this.icon || ''),
      h('h3', this.title || ''),
      h('p', this.description || '')
    ]);
  }
};

const EdgeLoadingState = {
  name: 'EdgeLoadingState',
  props: ['message', 'skeleton'],
  render() {
    return h('div', { class: ['edge-loading-state', this.skeleton ? 'with-skeleton' : ''] }, [
      h('div', { class: 'edge-loading-spinner' }),
      h('p', this.message || 'Loading...')
    ]);
  }
};

const EdgeErrorState = {
  name: 'EdgeErrorState',
  props: ['title', 'message'],
  emits: ['retry'],
  render() {
    return h('div', { class: 'edge-error-state' }, [
      h('h3', this.title || 'Error'),
      h('p', this.message || ''),
      h('button', { class: 'edge-primary-button', type: 'button', onClick: () => this.$emit('retry') }, 'Retry')
    ]);
  }
};

const localEdgeUIComponents = {
  EdgePageHeader,
  EdgeStatCard,
  EdgeStatusBadge,
  EdgeEmptyState,
  EdgeLoadingState,
  EdgeErrorState,
  EdgeAppShell,
  EdgePageLayout,
  EdgeFilterBar
};

const requiredEdgeUIComponents = [
  'EdgeAppShell',
  'EdgePageLayout',
  'EdgeFilterBar',
  'EdgeStatCard',
  'EdgeStatusBadge',
  'EdgeLoadingState',
  'EdgeEmptyState',
  'EdgeErrorState'
];

const resolveEdgeUIComponents = () => {
  const runtimeComponents =
    typeof window !== 'undefined' && window.EdgeUI
      ? (window.EdgeUI.components || window.EdgeUI)
      : {};
  return Object.fromEntries(
    requiredEdgeUIComponents.map((name) => [name, runtimeComponents[name] || localEdgeUIComponents[name]])
  );
};

export default {
  name: 'SalespersonPerformanceDashboard',
  components: resolveEdgeUIComponents(),
  data() {
    return {
      edgeUIValid: true,
      missingComponents: [],
      metadataLoading: true,
      loading: true,
      error: '',
      summary: {},
      rows: [],
      salespeople: [],
      branches: [],
      currentPage: 1,
      tenantName: '',
      branchName: '',
      userName: '',
      searchTimeout: null,
      filters: {
        date_range_preset: 'This Month',
        from_date: '',
        to_date: '',
        branch: '',
        salesperson: '',
        customer: '',
        item: '',
        limit: 50,
        offset: 0
      },
      menuItems: [
        { label: 'Salesperson Performance', route: '/app/salesperson-performance-dashboard', icon: '📈' },
        { label: 'Sales Invoices', route: '/app/sales-invoice', icon: '🧾' },
        { label: 'Salespeople', route: '/app/sales-person', icon: '💼' },
        { label: 'Customers', route: '/app/customer', icon: '👥' }
      ]
    };
  },
  created() {
    const runtimeComponents =
      typeof window !== 'undefined' && window.EdgeUI
        ? (window.EdgeUI.components || window.EdgeUI)
        : {};
    this.missingComponents = requiredEdgeUIComponents.filter((name) => !runtimeComponents[name]);
    this.edgeUIValid = this.missingComponents.length === 0;
  },
  mounted() {
    this.fetchMetadata();
  },
  methods: {
    async onPresetChange() {
      const val = this.filters.date_range_preset;
      if (val && val !== 'Custom Period') {
        const dates = window.retailedge && window.retailedge.getPresetDates ? window.retailedge.getPresetDates(val) : null;
        if (dates) {
          this.__applying_preset = true;
          this.filters.from_date = dates.from_date;
          this.filters.to_date = dates.to_date;
          await this.$nextTick();
          this.__applying_preset = false;
        }
      }
      this.fetchData();
    },
    onDateChange() {
      if (this.__applying_preset) {
        this.fetchData();
        return;
      }
      const val = this.filters.date_range_preset;
      if (val && val !== 'Custom Period') {
        const dates = window.retailedge && window.retailedge.getPresetDates ? window.retailedge.getPresetDates(val) : null;
        if (dates) {
          const currentFrom = this.filters.from_date || '';
          const currentTo = this.filters.to_date || '';
          if (currentFrom !== dates.from_date || currentTo !== dates.to_date) {
            this.filters.date_range_preset = 'Custom Period';
          }
        }
      }
      this.fetchData();
    },
    formatDate(dateStr) {
      if (!dateStr || typeof frappe === 'undefined') return dateStr;
      return frappe.datetime.str_to_user(dateStr);
    },
    formatCurrency(val) {
      const num = parseFloat(val || 0);
      if (typeof frappe !== 'undefined') {
        return format_currency(num, frappe.boot.sysdefaults.currency || 'USD');
      }
      return '$' + num.toFixed(2);
    },
    openDoc(doctype, name) {
      if (typeof frappe !== 'undefined') {
        frappe.set_route('Form', doctype, name);
      }
    },
    fetchMetadata() {
      if (typeof frappe === 'undefined') {
        this.loading = false;
        this.metadataLoading = false;
        return;
      }
      
      this.metadataLoading = true;
      this.loading = true;
      this.error = '';

      frappe.call({
        method: 'retailedge.salesperson_performance.get_salesperson_dashboard_options',
        callback: (r) => {
          this.metadataLoading = false;
          if (r.message) {
            this.branches = r.message.branches || [];
            this.salespeople = r.message.salespeople || [];
            this.tenantName = r.message.tenant_name || '';
            this.branchName = r.message.branch_name || '';
            this.userName = r.message.user_name || '';
            if (r.message.default_filters) {
              this.filters = { ...this.filters, ...r.message.default_filters };
            }
          }
          this.fetchData();
        },
        error: (err) => {
          this.metadataLoading = false;
          this.loading = false;
          this.error = err.message || 'Failed to load dashboard filters and options.';
        }
      });
    },
    fetchData() {
      if (typeof frappe === 'undefined') {
        this.loading = false;
        return;
      }

      this.loading = true;
      this.error = '';
      
      this.filters.offset = (this.currentPage - 1) * this.filters.limit;

      frappe.call({
        method: 'retailedge.salesperson_performance.get_salesperson_performance',
        args: {
          filters: this.filters
        },
        callback: (r) => {
          this.loading = false;
          if (r.message) {
            this.summary = r.message.summary || {};
            this.rows = r.message.rows || [];
          }
        },
        error: (err) => {
          this.loading = false;
          this.error = err.message || 'An error occurred during aggregation.';
        }
      });
    },
    debounceFetchData() {
      clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => {
        this.fetchData();
      }, 300);
    },
    changePage(direction) {
      this.currentPage += direction;
      this.fetchData();
    },
    handleNavigation(route) {
      if (typeof frappe !== 'undefined') {
        if (route === '/app/salesperson-performance-dashboard') {
          frappe.set_route('salesperson-performance-dashboard');
        } else if (route === '/app/sales-invoice') {
          frappe.set_route('List', 'Sales Invoice');
        } else if (route === '/app/sales-person') {
          frappe.set_route('List', 'Sales Person');
        } else if (route === '/app/customer') {
          frappe.set_route('List', 'Customer');
        }
      }
    }
  }
}
</script>

<style scoped>
/* Filter Group styles */
.filter-group {
  display: flex;
  flex-direction: column;
  gap: var(--edge-space-xs);
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--edge-text-muted);
}

.filter-input, .filter-select {
  padding: 8px 12px;
  border: 1px solid var(--edge-border);
  border-radius: var(--edge-radius-md);
  background-color: var(--edge-bg);
  color: var(--edge-text);
  font-size: var(--edge-text-sm);
  transition: border-color 0.2s ease;
  width: 100%;
}

.filter-input:focus, .filter-select:focus {
  border-color: var(--edge-primary);
  outline: none;
}

.filter-action-group {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.filter-btn {
  padding: 8px 16px;
  border-radius: var(--edge-radius-md);
  font-size: var(--edge-text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter-btn.primary {
  background-color: var(--edge-primary);
  color: white;
}

.filter-btn.primary:hover:not(:disabled) {
  opacity: 0.9;
}

.filter-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Stats grid */
.summary-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--edge-space-md);
  margin-bottom: var(--edge-space-lg);
}

/* Table Card */
.table-container-card {
  background-color: var(--edge-surface);
  border: 1px solid var(--edge-border);
  border-radius: var(--edge-radius-lg);
  box-shadow: var(--edge-shadow-sm);
  overflow: hidden;
  margin-top: var(--edge-space-lg);
}

.table-responsive {
  overflow-x: auto;
}

.dashboard-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--edge-text-sm);
}

.dashboard-table th {
  background-color: var(--edge-bg);
  border-bottom: 1px solid var(--edge-border);
  padding: var(--edge-space-md);
  text-align: left;
  font-weight: 600;
  color: var(--edge-text-muted);
  white-space: nowrap;
}

.dashboard-table td {
  padding: var(--edge-space-md);
  border-bottom: 1px solid var(--edge-border);
  white-space: nowrap;
}

.dashboard-table tr:last-child td {
  border-bottom: none;
}

.doc-link {
  color: var(--edge-primary);
  text-decoration: none;
  font-weight: 500;
}

.doc-link:hover {
  text-decoration: underline;
}

.items-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--edge-text-muted);
}

.bold-text {
  font-weight: 600;
}

.text-right {
  text-align: right !important;
}

.font-mono {
  font-family: monospace;
}

.text-muted {
  color: var(--edge-text-muted);
}

.red-text {
  color: var(--edge-danger);
  font-weight: 600;
}

/* Pagination */
.pagination-footer {
  padding: var(--edge-space-md) var(--edge-space-lg);
  border-top: 1px solid var(--edge-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--edge-space-md);
  background-color: var(--edge-bg);
}

.page-info {
  font-size: 0.815rem;
  color: var(--edge-text-muted);
}

.pagination-buttons {
  display: flex;
  gap: var(--edge-space-sm);
}

.pagination-btn {
  padding: 6px 12px;
  border: 1px solid var(--edge-border);
  border-radius: var(--edge-radius-md);
  background-color: var(--edge-surface);
  color: var(--edge-text);
  font-size: 0.815rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.pagination-btn:hover:not(:disabled) {
  border-color: var(--edge-primary);
  color: var(--edge-primary);
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.empty-state-container {
  padding: var(--edge-space-xl) 0;
}

.edge-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--edge-space-md);
  width: 100%;
}

.edge-field {
  display: flex;
  flex-direction: column;
  gap: var(--edge-space-xs);
  min-width: 0;
}

.edge-field-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--edge-muted-text, var(--edge-text-muted));
  text-transform: uppercase;
  letter-spacing: 0;
}

.edge-input,
.edge-select {
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--edge-border);
  border-radius: var(--edge-radius, var(--edge-radius-md));
  background-color: var(--edge-surface);
  color: var(--edge-text);
  font-family: var(--edge-font);
  font-size: var(--edge-text-sm);
  box-shadow: var(--edge-shadow-sm);
}

.edge-select {
  appearance: none;
  padding-right: 34px;
}

.edge-input:focus,
.edge-select:focus {
  border-color: var(--edge-primary);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
  outline: none;
}

.edge-primary-button {
  min-height: 40px;
  padding: 8px 16px;
  border: 1px solid var(--edge-primary);
  border-radius: var(--edge-radius, var(--edge-radius-md));
  background-color: var(--edge-primary);
  color: white;
  font-family: var(--edge-font);
  font-size: var(--edge-text-sm);
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--edge-shadow-sm);
}

.edge-primary-button:hover:not(:disabled) {
  background-color: var(--edge-primary-hover);
  border-color: var(--edge-primary-hover);
}

.edge-table-card {
  background-color: var(--edge-surface);
  border: 1px solid var(--edge-border);
  border-radius: var(--edge-radius, var(--edge-radius-lg));
  box-shadow: var(--edge-shadow, var(--edge-shadow-sm));
}

.edge-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--edge-space-md);
}
</style>
