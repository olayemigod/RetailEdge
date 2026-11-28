import CashDepositRegisterPage from "./cash_deposit_register/CashDepositRegisterPage.vue";

function mountCashDepositRegisterPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Cash Deposit Register mount target is required.");
	const app = edgeUI.createEdgeApp(CashDepositRegisterPage);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.CashDepositRegisterPage = CashDepositRegisterPage;
	window.mountCashDepositRegisterPage = mountCashDepositRegisterPage;
}

export { mountCashDepositRegisterPage };
export default CashDepositRegisterPage;
