const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
	testDir: __dirname,
	testMatch: /retailedge_(?:mvp_smoke|rc3_acceptance|business_hub_qa_regression)\.spec\.cjs/,
	fullyParallel: false,
	retries: 0,
	workers: 1,
	timeout: 90_000,
	expect: { timeout: 15_000 },
	use: {
		baseURL: process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000",
		// Preserve browser evidence for regression review. A green automated run is
		// not Business Hub QA acceptance and must not be promoted to RC3 by itself.
		trace: "on",
		screenshot: "on",
		video: "on",
	},
	reporter: [
		["line"],
		["html", { outputFolder: "playwright-report", open: "never" }],
	],
});
