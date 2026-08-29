<template>
	<div class="control-row" :class="item.severity === 'danger' ? 'control-row--danger' : 'control-row--warning'">
		<div class="control-row-main">
			<span class="control-copy"><strong>{{ item.label }}</strong><small>{{ item.family || sourceLabel(item.source) }} · {{ basisLabel(item.time_basis) }}</small></span>
			<strong>{{ formatValue(item.value, item.datatype) }}</strong>
		</div>
		<div v-if="item.priority_reason" class="control-reason">Why this is prioritised: {{ item.priority_reason }}</div>
		<div class="follow-up-summary">
			<span class="follow-up-status">{{ followUpStatus }}</span>
			<span v-if="followUp.is_due" class="follow-up-due">Due / overdue</span>
			<span v-if="followUp.assigned_to">Assigned: {{ followUp.assigned_to }}</span>
			<span v-if="followUp.follow_up_on">Follow up: {{ formatDateTime(followUp.follow_up_on) }}</span>
			<span v-if="followUpStatus === 'Snoozed' && followUp.snoozed_until">Snoozed until: {{ formatDateTime(followUp.snoozed_until) }}</span>
		</div>
		<div class="control-actions">
			<button class="edge-button edge-button--primary" type="button" :title="workflowTitle" @click="$emit('open', item)">Open workflow</button>
			<template v-if="item.follow_up_supported !== false && item.fingerprint">
				<button v-if="followUpStatus !== 'Acknowledged'" class="edge-button" type="button" :disabled="busy" @click="$emit('follow-up', item, 'acknowledge')">Acknowledge</button>
				<button class="edge-button" type="button" :disabled="busy" @click="$emit('follow-up', item, 'assign')">Assign</button>
				<button class="edge-button" type="button" :disabled="busy" @click="$emit('follow-up', item, 'schedule')">Follow-up</button>
				<button v-if="followUpStatus !== 'Snoozed'" class="edge-button" type="button" :disabled="busy" @click="$emit('follow-up', item, 'snooze')">Snooze</button>
				<button v-if="followUpStatus !== 'Open'" class="edge-button" type="button" :disabled="busy" @click="$emit('follow-up', item, 'reopen')">Reopen</button>
			</template>
		</div>
	</div>
</template>

<script>
export default {
	name: "RetailEdgeBusinessControlRow",
	props: {
		item: { type: Object, required: true },
		busy: { type: Boolean, default: false },
	},
	emits: ["open", "follow-up"],
	computed: {
		followUp() { return this.item.follow_up || { status: "Open", effective_status: "Open" }; },
		followUpStatus() { return this.followUp.effective_status || this.followUp.status || "Open"; },
		workflowTitle() { return this.item?.open_mode === "new_tab" ? "Open authoritative workflow in a new tab" : "Open RetailEdge workflow"; },
	},
	methods: {
		sourceLabel(source) { return String(source || "management").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()); },
		basisLabel(value) { return value === "current" ? "Current position" : "Selected period"; },
		formatDateTime(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(value); } catch (_error) { return value; } },
		formatValue(value, datatype) { try { return frappe.format(value, { fieldtype: datatype || "Data" }); } catch (_error) { return value ?? "—"; } },
	},
};
</script>

<style scoped>
.control-row { display: grid; gap: 10px; width: 100%; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); }
.control-row--danger { border-color: var(--red-300, var(--edge-border)); }
.control-row--warning { border-color: var(--orange-300, var(--edge-border)); }
.control-row-main { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.control-copy { display: grid; gap: 4px; }
.control-copy small, .control-reason, .follow-up-summary { color: var(--edge-text-muted); font-size: 12px; }
.follow-up-summary, .control-actions { display: flex; flex-wrap: wrap; gap: 7px 12px; align-items: center; }
.follow-up-status, .follow-up-due { padding: 2px 7px; border: 1px solid var(--edge-border); border-radius: 999px; background: var(--edge-surface-soft, var(--edge-surface)); color: var(--edge-text); font-weight: 600; }
.follow-up-due { border-color: var(--orange-300, var(--edge-border)); }
@media (max-width: 720px) { .control-row-main { align-items: flex-start; } .control-actions .edge-button { flex: 1 1 auto; } }
</style>
