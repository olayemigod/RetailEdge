import { createApp } from "vue";
import MoneyOverview from "./money_overview/MoneyOverview.vue";

window.retailedgeMountMoneyOverview = function retailedgeMountMoneyOverview(target) {
	if (!target) return null;
	const app = createApp(MoneyOverview);
	app.mount(target);
	return app;
};
