<template>
  <div class="salesperson-dashboard-wrapper">
    <EdgePageHeader 
      title="Salesperson Performance Dashboard" 
      subtitle="Proportional salesperson allocations for submitted RetailEdge invoices"
      :withBackButton="false"
    />

    <!-- Filter Card -->
    <div class="filter-card">
      <h3 class="filter-title">Filter Records</h3>
      <div class="filter-grid">
        <div class="filter-group">
          <label class="filter-label">From Date</label>
          <input type="date" v-model="filters.from_date" class="filter-input" @change="fetchData" />
        </div>
        <div class="filter-group">
          <label class="filter-label">To Date</label>
          <input type="date" v-model="filters.to_date" class="filter-input" @change="fetchData" />
        </div>
        <div class="filter-group">
          <label class="filter-label">Branch</label>
          <select v-model="filters.branch" class="filter-select" @change="fetchData">
            <option value="">All Branches</option>
            <option v-for="b in branches" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Salesperson</label>
          <select v-model="filters.salesperson" class="filter-select" @change="fetchData">
            <option value="">All Salespeople</option>
            <option v-for="s in salespeople" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Customer</label>
          <input type="text" v-model="filters.customer" placeholder="Customer Name" class="filter-input" @debounce="fetchData" @change="fetchData" />
        </div>
        <div class="filter-group">
          <label class="filter-label">Item Code</label>
          <input type="text" v-model="filters.item" placeholder="Item Code" class="filter-input" @change="fetchData" />
        </div>
      </div>
    </div>

    <!-- Error/Loading states -->
    <div v-if="error" class="p-6">
      <EdgeErrorState 
        title="Aggregation Query Failed" 
        :message="error" 
        @retry="fetchData"
      />
    </div>

    <div v-else-if="loading" class="p-6">
      <EdgeLoadingState message="Aggregating performance calculations..." :skeleton="true" />
    </div>

    <div v-else>
      <!-- Summary stats grid -->
      <div class="summary-stats-grid">
        <EdgeStatCard 
          label="Proportional Gross Sales" 
          :value="formatCurrency(summary.gross_sales)" 
          icon="💰" 
          tooltip="Sum of allocated sales total (Gross total * allocation percentage)"
        />
        <EdgeStatCard 
          label="Proportional Net Sales" 
          :value="formatCurrency(summary.net_sales)" 
          icon="📈" 
          tooltip="Sum of allocated net sales (excluding taxes)"
        />
        <EdgeStatCard 
          label="Total Invoices Count" 
          :value="summary.total_invoices || 0" 
          icon="📝" 
          tooltip="Unique number of submitted invoices attributed to salespeople"
        />
        <EdgeStatCard 
          label="Avg Invoice Value" 
          :value="formatCurrency(summary.avg_invoice_value)" 
          icon="📊" 
          tooltip="Average allocated invoice value"
        />
        <EdgeStatCard 
          label="Total Discounts Split" 
          :value="formatCurrency(summary.total_discount)" 
          icon="🏷️" 
          tooltip="Sum of allocated discount value splits"
        />
        <EdgeStatCard 
          label="Outstanding Split" 
          :value="formatCurrency(summary.total_outstanding)" 
          icon="⚠️" 
          tooltip="Sum of allocated outstanding invoice amount splits"
        />
      </div>

      <!-- Main Data Table -->
      <div v-if="rows.length > 0" class="table-container-card">
        <div class="table-responsive">
          <table class="dashboard-table">
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
  </div>
</template>

<script>
// Consume CoreEdge EdgeUI elements safely from global namespace wrapper
const { 
  EdgePageHeader, 
  EdgeStatCard, 
  EdgeStatusBadge, 
  EdgeEmptyState, 
  EdgeLoadingState, 
  EdgeErrorState 
} = window.EdgeUI || {};

export default {
  name: 'SalespersonPerformanceDashboard',
  components: {
    EdgePageHeader,
    EdgeStatCard,
    EdgeStatusBadge,
    EdgeEmptyState,
    EdgeLoadingState,
    EdgeErrorState
  },
  data() {
    return {
      loading: true,
      error: '',
      summary: {},
      rows: [],
      salespeople: [],
      branches: [],
      currentPage: 1,
      filters: {
        from_date: this.getFirstDayOfMonth(),
        to_date: this.getTodayDate(),
        branch: '',
        salesperson: '',
        customer: '',
        item: '',
        limit: 50,
        offset: 0
      }
    };
  },
  mounted() {
    this.fetchMetadata();
    this.fetchData();
  },
  methods: {
    getFirstDayOfMonth() {
      const d = new Date();
      return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split('T')[0];
    },
    getTodayDate() {
      return new Date().toISOString().split('T')[0];
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
      if (typeof frappe === 'undefined') return;
      
      // Get all active salespeople
      frappe.call({
        method: 'frappe.client.get_list',
        args: {
          doctype: 'Sales Person',
          fields: ['name'],
          filters: { enabled: 1 },
          limit_page_length: 500
        },
        callback: (r) => {
          if (r.message) {
            this.salespeople = r.message.map(s => s.name);
          }
        }
      });

      // Get allowed branches using RetailEdge branch helper
      frappe.call({
        method: 'retailedge.branch_performance.get_candidate_branches',
        callback: (r) => {
          if (r.message) {
            this.branches = r.message;
          }
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
    changePage(direction) {
      this.currentPage += direction;
      this.fetchData();
    }
  }
}
</script>

<style scoped>
.salesperson-dashboard-wrapper {
  color: var(--edge-text);
  font-family: var(--edge-font);
}

/* Filter Card */
.filter-card {
  background-color: var(--edge-surface);
  border: 1px solid var(--edge-border);
  border-radius: var(--edge-radius-lg);
  padding: var(--edge-space-lg);
  box-shadow: var(--edge-shadow-sm);
  margin-bottom: var(--edge-space-lg);
}

.filter-title {
  margin: 0 0 var(--edge-space-md) 0;
  font-size: 0.95rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--edge-text-muted);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--edge-space-md);
}

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
</style>
