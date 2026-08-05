if (typeof window.retailedgeRegisterBusinessHubPage === "function") {
	window.retailedgeRegisterBusinessHubPage();
} else {
	console.error(
		"[RetailEdge Business Hub] Desk controller is unavailable. Rebuild RetailEdge assets and clear the site cache."
	);
}
