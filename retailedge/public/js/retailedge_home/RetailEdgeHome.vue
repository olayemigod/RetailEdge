<template>
	<EdgeAppShell
		product="retailedge"
		:menu-items="menuItems"
		active-route="/app/retailedge-home"
		title="RetailEdge"
		subtitle="Retail operations and business intelligence"
		:tenant-name="tenantName"
		:branch-name="activeBranch"
		:user-name="userName"
		:user-image="userImage"
		:hide-native-sidebar="false"
		@navigate="openRoute"
		data-edge-product="retailedge"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					title="RetailEdge Home"
					subtitle="Run branch operations, review exceptions and open trusted ERPNext workflows from one place."
					:with-back-button="false"
				/>
			</template>

			<div class="retailedge-home-toolbar">
				<button type="button" class="edge-button" @click="openNativeWorkspace">
					Open native workspace
				</button>
				<button type="button" class="edge-button edge-button--primary" :disabled="loading" @click="loadContext">
					{{ loading ? "Refreshing…" : "Refresh Home" }}
				</button>
			</div>

			<EdgeBranchContextSwitcher
				v-model="activeBranch"
				:options="branches"
				:current-company="company"
				:current-label="activeBranch || 'All permitted branches'"
				:can-switch="canSwitchBranch"
				:busy="loading"
				label="Home branch filter"
				helper="Filters this Home view only. Existing ERPNext document defaults remain unchanged."
				placeholder="All permitted branches"
				@switch="onBranchSwitch"
			/>

			<div v-if="contextNote" class="retailedge-context-note" role="note">
				<EdgeIcon name="activity" size="sm" />
				<span>{{ contextNote }}</span>
			</div>

			<div v-if="error" class="retailedge-home-state">
				<EdgeErrorState title="RetailEdge Home could not load" :message="error" @retry="loadContext" />
			</div>
			<div v-else-if="loading && !sections.length" class="retailedge-home-state">
				<EdgeLoadingState message="Loading permitted RetailEdge operations…" :skeleton="true" />
			</div>
			<template v-else>
				<div class="edge-stat-grid retailedge-home-stats">
					<EdgeStatCard
						label="Accessible actions"
						:value="summary.accessible_actions || 0"
						tooltip="Routes available after permission and target checks."
					>
						<template #icon><EdgeIcon name="grid" size="sm" /></template>
					</EdgeStatCard>
					<EdgeStatCard
						label="Workspace sections"
						:value="summary.workspace_sections || 0"
						tooltip="Operational groups available to the current user."
					>
						<template #icon><EdgeIcon name="layers" size="sm" /></template>
					</EdgeStatCard>
					<EdgeStatCard
						label="Permitted branches"
						:value="summary.permitted_branches || 0"
						tooltip="Branches resolved from RetailEdge and existing permission context."
					>
						<template #icon><EdgeIcon name="building" size="sm" /></template>
					</EdgeStatCard>
				</div>

				<div v-if="sections.length" class="retailedge-home-sections">
					<section v-for="section in sections" :key="section.key" class="retailedge-home-section">
						<header class="retailedge-home-section__header">
							<span class="retailedge-home-section__icon"><EdgeIcon :name="section.icon" size="md" /></span>
							<div>
								<h2>{{ section.label }}</h2>
								<p>{{ section.description }}</p>
							</div>
						</header>
						<div class="retailedge-home-grid">
							<button
								v-for="item in section.items"
								:key="`${section.key}-${item.link_type}-${item.link_to}`"
								type="button"
								class="retailedge-home-card"
								@click="openItem(item)"
							>
								<span class="retailedge-home-card__icon"><EdgeIcon :name="item.icon" size="md" /></span>
								<span class="retailedge-home-card__copy">
									<strong>{{ item.label }}</strong>
									<small>{{ item.source }}</small>
								</span>
								<EdgeStatusBadge :label="item.link_type" :status="item.link_type" tone="neutral" />
							</button>
						</div>
					</section>
				</div>
				<div v-else class="retailedge-home-state">
					<EdgeEmptyState
						title="No RetailEdge route is available"
						description="Your current roles do not expose a configured RetailEdge operation on this site."
					/>
				</div>
			</template>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
export default {
	name: "RetailEdgeHome",
	data() {
		return {
			loading: false,
			error: "",
			company: "",
			activeBranch: "",
			branches: [],
			canSwitchBranch: false,
			sections: [],
			summary: {},
			contextNote: "",
			identity: {},
		};
	},
	computed: {
		menuItems() {
			return this.sections.map((section) => ({
				key: section.key,
				label: section.label,
				icon: section.icon,
				items: section.items.map((item) => ({
					...item,
					description: item.source,
				})),
			}));
		},
		tenantName() {
			return this.identity.tenant_name || this.company || "Retail Business";
		},
		userName() {
			return this.identity.user?.full_name || window.frappe?.session?.user || "RetailEdge User";
		},
		userImage() {
			return this.identity.user?.image || "";
		},
	},
	mounted() {
		this.loadContext();
	},
	methods: {
		normalizeError(error) {
			return (
				error?.message ||
				error?.exc_type ||
				error?._server_messages ||
				"RetailEdge Home failed to load."
			);
		},
		async loadContext() {
			this.loading = true;
			this.error = "";
			try {
				const response = await window.frappe.call(
					"retailedge.api.ui_context.get_home_context",
					{
						branch: this.activeBranch || undefined,
						company: this.company || undefined,
					},
				);
				const payload = response?.message || {};
				this.identity = payload.identity || {};
				this.company = payload.company || this.identity.company || "";
				this.activeBranch = payload.active_branch || "";
				this.branches = payload.branches || [];
				this.canSwitchBranch = Boolean(payload.can_switch_branch);
				this.sections = payload.sections || [];
				this.summary = payload.summary || {};
				this.contextNote = payload.context_note || "";
			} catch (error) {
				this.error = this.normalizeError(error);
			} finally {
				this.loading = false;
			}
		},
		onBranchSwitch(option) {
			this.activeBranch = option?.value || "";
			this.loadContext();
		},
		openItem(item) {
			if (window.RetailEdgeUIBridge?.openItem?.(item)) return;
			if (item?.route) window.location.assign(item.route);
		},
		openRoute(route) {
			if (window.RetailEdgeUIBridge?.openRoute?.(route)) return;
			if (route) window.location.assign(route);
		},
		openNativeWorkspace() {
			this.openRoute("/app/retailedge");
		},
	},
};
</script>

<style scoped>
.retailedge-home-toolbar {
	display: flex;
	flex-wrap: wrap;
	gap: 0.6rem;
	justify-content: flex-end;
	margin-bottom: 1rem;
}

.retailedge-context-note {
	align-items: flex-start;
	background: var(--edge-color-brand-50, #eef7ff);
	border: 1px solid var(--edge-color-brand-100, #d9edff);
	border-radius: var(--edge-radius-md, 0.75rem);
	color: var(--edge-color-ink-700, #415469);
	display: flex;
	font-size: 0.75rem;
	gap: 0.5rem;
	line-height: 1.45;
	margin: 1rem 0;
	padding: 0.75rem 0.85rem;
}

.retailedge-home-stats {
	margin: 1rem 0;
}

.retailedge-home-sections {
	display: grid;
	gap: 1rem;
}

.retailedge-home-section {
	background: var(--edge-color-surface, var(--card-bg, #fff));
	border: 1px solid var(--edge-color-border, var(--border-color, #dce5ef));
	border-radius: var(--edge-radius-lg, 1rem);
	box-shadow: var(--edge-shadow-xs, 0 1px 2px rgb(18 32 51 / 5%));
	overflow: hidden;
}

.retailedge-home-section__header {
	align-items: flex-start;
	border-bottom: 1px solid var(--edge-color-border, var(--border-color, #dce5ef));
	display: flex;
	gap: 0.75rem;
	padding: 0.9rem 1rem;
}

.retailedge-home-section__icon,
.retailedge-home-card__icon {
	align-items: center;
	background: var(--edge-color-brand-50, #eef7ff);
	border-radius: 0.7rem;
	color: var(--edge-color-brand-700, #0c4f87);
	display: inline-flex;
	justify-content: center;
	min-height: 2.25rem;
	min-width: 2.25rem;
}

.retailedge-home-section__header h2 {
	color: var(--edge-color-ink-900, #1c2b3b);
	font-size: 0.92rem;
	margin: 0;
}

.retailedge-home-section__header p {
	color: var(--edge-color-ink-500, #6b7d90);
	font-size: 0.72rem;
	margin: 0.2rem 0 0;
}

.retailedge-home-grid {
	display: grid;
	gap: 0.65rem;
	grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
	padding: 0.85rem;
}

.retailedge-home-card {
	align-items: center;
	background: var(--edge-color-surface-soft, #f8fafc);
	border: 1px solid var(--edge-color-border, var(--border-color, #dce5ef));
	border-radius: 0.8rem;
	color: inherit;
	cursor: pointer;
	display: grid;
	gap: 0.65rem;
	grid-template-columns: auto minmax(0, 1fr) auto;
	min-height: 4.25rem;
	padding: 0.7rem;
	text-align: left;
	transition: border-color 0.14s ease, background-color 0.14s ease, transform 0.14s ease;
}

.retailedge-home-card:hover,
.retailedge-home-card:focus-visible {
	background: var(--edge-color-brand-50, #eef7ff);
	border-color: var(--edge-color-brand-200, #b8ddf5);
	outline: none;
	transform: translateY(-1px);
}

.retailedge-home-card__copy {
	display: grid;
	gap: 0.15rem;
	min-width: 0;
}

.retailedge-home-card__copy strong {
	color: var(--edge-color-ink-900, #1c2b3b);
	font-size: 0.78rem;
}

.retailedge-home-card__copy small {
	color: var(--edge-color-ink-500, #6b7d90);
	font-size: 0.67rem;
}

.retailedge-home-state {
	margin-top: 1rem;
}

@media (max-width: 47.99rem) {
	.retailedge-home-toolbar {
		justify-content: stretch;
	}

	.retailedge-home-toolbar .edge-button {
		flex: 1 1 auto;
	}

	.retailedge-home-grid {
		grid-template-columns: 1fr;
	}
}
</style>
