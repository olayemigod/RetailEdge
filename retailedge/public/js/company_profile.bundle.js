import CompanyProfile from "./company_profile/CompanyProfile.vue";

function mountRetailEdgeCompanyProfile(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Company Profile mount target is required");
	const app = edgeUI.createEdgeApp(CompanyProfile);
	app.mount(target);
	return app;
}
if (typeof window !== "undefined") {
	window.RetailEdgeCompanyProfile = CompanyProfile;
	window.mountRetailEdgeCompanyProfile = mountRetailEdgeCompanyProfile;
}
export { mountRetailEdgeCompanyProfile };
export default CompanyProfile;
