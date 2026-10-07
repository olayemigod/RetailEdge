<template>
	<div v-if="!edgeUIValid" class="history-fallback"><strong>RFQ History could not start.</strong><span>Required interface components are unavailable.</span></div>
	<EdgeAppShell v-else product="RetailEdge" title="RFQ History" :tenantName="tenantName" :branchName="branchName" :userName="userName" :menuItems="menuItems" activeRoute="/app/rfq-history" :hideNativeSidebar="true" @navigate="handleNavigation">
		<EdgePageLayout class="history-page">
			<EdgePageHeader title="RFQ History" description="Review Requests for Quotation on a persistent paginated page. Record a supplier response through a focused transaction review only when needed." />
			<section class="edge-panel history-controls">
				<div class="filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
					<label class="history-input"><span>Search</span><input v-model="filters.search" type="search" placeholder="RFQ or status" @keyup.enter="applyFilters" /></label>
				</div>
				<div class="control-actions"><button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="applyFilters">{{ loading ? "Refreshing…" : "Apply Filters" }}</button><button type="button" class="edge-button" @click="backToPurchasing">Back to Purchasing</button></div>
			</section>
			<EdgeLoadingState v-if="loading && !loaded" message="Loading RFQ history..." :skeleton="true" />
			<EdgeErrorState v-else-if="error && !loaded" title="RFQ history unavailable" :message="error" @retry="applyFilters" />
			<section v-else class="edge-panel history-list">
				<div v-if="error" class="inline-error" role="alert">{{ error }}</div>
				<div class="scope"><span><strong>Company:</strong> {{ history.company || filters.company || "—" }}</span><span><strong>Branch:</strong> {{ history.branch || "All permitted" }}</span><span><strong>Supplier:</strong> {{ history.supplier || "All suppliers" }}</span><span><strong>Loaded:</strong> {{ rows.length }}</span></div>
				<EdgeEmptyState v-if="!rows.length" title="No RFQs" description="No permission-visible RFQs match the selected scope." />
				<div v-else class="table-responsive"><table class="table history-table"><thead><tr><th>RFQ</th><th>Date</th><th>Suppliers</th><th>Items</th><th>Branch</th><th>Status</th><th>Actions</th></tr></thead><tbody>
					<tr v-for="row in rows" :key="row.name"><td><strong>{{ row.name }}</strong></td><td>{{ formatDate(row.transaction_date || row.modified) }}</td><td>{{ (row.suppliers || []).join(", ") || "—" }}</td><td>{{ row.item_count || 0 }}</td><td>{{ row.branch || "—" }}</td><td>{{ row.status || statusLabel(row.docstatus) }}</td><td><div class="row-actions"><button v-if="canRecordQuote(row)" type="button" class="edge-small-button edge-small-button--primary" @click="recordSupplierQuote(row)">Record Supplier Quote</button><button v-if="canUseNativeDesk" type="button" class="edge-small-button" @click="openAdvanced(row.name)">Advanced: Open RFQ</button></div></td></tr>
				</tbody></table></div>
				<div class="pagination"><span>{{ history.has_more ? "More RFQs are available." : (rows.length ? "End of matching RFQs." : "") }}</span><button v-if="history.has_more" type="button" class="edge-button edge-button--primary" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? "Loading…" : "Load More" }}</button></div>
			</section>
		</EdgePageLayout>
	</EdgeAppShell>
</template>
<script>
const HISTORY_METHOD = "retailedge.professional_sourcing.get_request_for_quotation_history";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const PAGE_SIZE = 40;
const REQUIRED = ["EdgeAppShell","EdgePageLayout","EdgePageHeader","EdgeLinkField","EdgeLoadingState","EdgeErrorState","EdgeEmptyState"];
function runtime(){ return window.EdgeSuiteUI?.components || {}; }
function callMethod(method,args={}){ return new Promise((resolve,reject)=>frappe.call({method,args,callback:r=>resolve(r.message||{}),error:reject})); }
function customerFacingCopy(value,fallback=""){ const text=String(value||"").trim(); if(!text)return fallback; return text.replace(/Advanced ERPNext/gi,"advanced review").replace(/Frappe Workflow/gi,"approval workflow").replace(/ERPNext/gi,"the accounting system").replace(/EdgeSuite/gi,"the workspace").replace(/Native Desk/gi,"advanced access"); }
function err(error,fallback){ const message=window.retailedge?.userErrorMessage?.(error,fallback)||error?.message||error?.exc||error?._server_messages||fallback; return customerFacingCopy(message,fallback); }
export default {
	name:"RfqHistoryPage",
	components:Object.fromEntries(REQUIRED.map(name=>[name,runtime()[name]])),
	data(){ return { edgeUIValid:true,tenantName:"",branchName:"",userName:"",menuItems:[],canUseNativeDesk:false,loading:false,loadingMore:false,loaded:false,error:"",filters:{company:"",branch:"",supplier:"",search:""},history:{rows:[],has_more:false,next_start:0} }; },
	computed:{ rows(){ return Array.isArray(this.history.rows)?this.history.rows:[]; } },
	created(){ this.edgeUIValid=REQUIRED.every(name=>Boolean(runtime()[name])); },
	mounted(){ if(this.edgeUIValid)this.loadShellAndHistory(); },
	methods:{
		async loadShellAndHistory(){ try{ const [context,operating]=await Promise.all([callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context"),callMethod("retailedge.operating_context.get_operating_context")]); const shell=context.context||{}; this.tenantName=operating.company_label||operating.company||shell.company||""; this.branchName=operating.branch||""; this.userName=shell.user_name||shell.user||""; this.canUseNativeDesk=Boolean(context?.access?.can_use_native_desk); this.menuItems=this.mapNavigationGroups(context.navigation_groups||[]); this.filters.company=operating.company||shell.company||""; this.filters.branch=operating.branch||""; }catch(_error){} await this.applyFilters(); },
		fetchPage(start=0){ return callMethod(HISTORY_METHOD,{company:this.filters.company||null,branch:this.filters.branch||null,supplier:this.filters.supplier||null,search:this.filters.search||null,start,page_length:PAGE_SIZE}); },
		async applyFilters(){ if(this.loading)return; this.loading=true; this.error=""; try{ const result=await this.fetchPage(0); this.history={...(result||{}),rows:result?.rows||[]}; if(!this.filters.company)this.filters.company=result.company||""; if(!this.filters.branch&&result.branch)this.filters.branch=result.branch; this.loaded=true; }catch(error){this.error=err(error,"Unable to load RFQ history.");}finally{this.loading=false;} },
		async loadMore(){ if(this.loadingMore||!this.history.has_more)return; this.loadingMore=true; try{ const result=await this.fetchPage(Number(this.history.next_start||this.rows.length)); const seen=new Set(this.rows.map(r=>r.name)); this.history={...this.history,...result,rows:[...this.rows,...(result.rows||[]).filter(r=>!seen.has(r.name))]}; }catch(error){this.error=err(error,"Unable to load more RFQs.");}finally{this.loadingMore=false;} },
		async searchOptions(kind,txt){ const result=await callMethod(SEARCH_METHOD,{kind,txt,company:this.filters.company||null}); return Array.isArray(result)?result:[]; },
		companySearch(txt){return this.searchOptions("company",txt);},branchSearch(txt){return this.searchOptions("branch",txt);},supplierSearch(txt){return this.searchOptions("supplier",txt);},
		onCompanySelected(option){this.filters.company=option.value;this.filters.branch="";this.filters.supplier="";this.applyFilters();},onBranchSelected(option){this.filters.branch=option.value;this.applyFilters();},clearBranch(){this.filters.branch="";this.applyFilters();},onSupplierSelected(option){this.filters.supplier=option.value;this.applyFilters();},clearSupplier(){this.filters.supplier="";this.applyFilters();},
		canRecordQuote(row){return Number(row?.docstatus||0)===1&&Array.isArray(row?.suppliers)&&row.suppliers.length>0;},
		recordSupplierQuote(row){ if(!this.canRecordQuote(row))return; window.retailedgeProfessionalPurchasingTarget={user:frappe.session?.user||"",action:"rfq-capture",source_name:row.name,createdAt:Date.now()}; frappe.set_route("professional-purchasing"); },
		openAdvanced(name){if(this.canUseNativeDesk&&name)frappe.set_route("Form","Request for Quotation",name);},backToPurchasing(){frappe.set_route("professional-purchasing");},
		statusLabel(v){return Number(v)===1?"Submitted":Number(v)===2?"Cancelled":"Draft";},formatDate(v){return v?frappe.datetime.str_to_user(v):"—";},
		mapNavigationGroups(groups){return(groups||[]).map(g=>({...g,items:(g.items||[]).map(i=>({...i,route:this.routeForItem(i)}))}));},routeForItem(i){if(i.target_type==="Page")return `/app/${i.target}`;if(i.target_type==="Report")return `/app/query-report/${encodeURIComponent(i.target)}`;if(i.target_type==="DocType")return `/app/${String(i.target||"").toLowerCase().replace(/\s+/g,"-")}`;return i.target||"";},handleNavigation(route){const i=this.menuItems.flatMap(g=>g.items||[]).find(x=>x.route===route);if(!i)return;if((i.target_type==="Report"||i.target_type==="DocType")&&!this.canUseNativeDesk)return;if(i.target_type==="Page")frappe.set_route(i.target);else if(i.target_type==="Report")frappe.set_route("query-report",i.target);else if(i.target_type==="DocType")frappe.set_route("List",i.target);}
	}
};
</script>
<style scoped>
.history-page{min-height:100%;display:grid;gap:1rem}.history-fallback,.edge-panel{border:1px solid var(--edge-border,#d9d9d9);border-radius:10px;background:var(--edge-surface,#fff)}.history-fallback{margin:20px;padding:24px;display:grid;gap:8px}.history-controls,.history-list{padding:18px}.filter-grid{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:.75rem}.history-input{display:grid;gap:.35rem;font-size:.8rem;font-weight:600;color:var(--edge-text-muted,#667085)}.history-input input{min-height:40px;border:1px solid var(--edge-border,#d9d9d9);border-radius:8px;padding:0 .7rem;background:inherit;color:inherit}.control-actions,.row-actions,.scope,.pagination{display:flex;gap:.55rem;flex-wrap:wrap;align-items:center}.control-actions{margin-top:.8rem}.scope{margin-bottom:.8rem;font-size:.82rem;color:var(--edge-text-muted,#667085)}.inline-error{padding:.65rem;border:1px solid var(--red-400,#f04438);border-radius:8px;color:var(--red-700,#b42318);margin-bottom:.7rem}.table-responsive{overflow:auto}.history-table{min-width:900px;width:100%}.pagination{justify-content:space-between;margin-top:1rem}.edge-button,.edge-small-button{border:1px solid var(--edge-border,#d9d9d9);border-radius:8px;background:var(--edge-surface,#fff);color:inherit;font-weight:600;cursor:pointer}.edge-button{min-height:38px;padding:0 12px}.edge-small-button{min-height:30px;padding:0 9px;white-space:nowrap}.edge-button--primary,.edge-small-button--primary{background:var(--edge-primary,#0f766e);border-color:var(--edge-primary,#0f766e);color:#fff}button:disabled{opacity:.55;cursor:not-allowed}@media(max-width:900px){.filter-grid{grid-template-columns:repeat(2,minmax(160px,1fr))}}@media(max-width:560px){.filter-grid{grid-template-columns:1fr}}
</style>
