<template>
	<ProfessionalPurchaseOrderDialog
		:open="open"
		:nativeFallbackEnabled="nativeFallbackEnabled"
		@close="open = false"
		@saved="handleSaved"
		@open-native="openNative"
	/>
</template>

<script>
import ProfessionalPurchaseOrderDialog from "./ProfessionalPurchaseOrderDialog.vue";

const OPEN_EVENT = "retailedge-open-professional-purchase-order";
const ACCESS_MODE = "edgesuite_only";

export default {
	name: "ProfessionalPurchaseOrderOverlay",
	components: { ProfessionalPurchaseOrderDialog },
	data() { return { open: false }; },
	computed: {
		nativeFallbackEnabled() {
			return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE;
		},
	},
	created() { this._open = () => { this.open = true; }; },
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		handleSaved(result) {
			this.open = false;
			const name = result?.name || "";
			frappe.show_alert({ message: __(name ? `Draft Purchase Order ${name} created.` : "Draft Purchase Order created."), indicator: "green" });
			window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
		},
		openNative() {
			if (!this.nativeFallbackEnabled) return;
			this.open = false;
			frappe.new_doc("Purchase Order");
		},
	},
};
</script>
