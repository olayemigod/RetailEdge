const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
	testDir: __dirname,
	testMatch: /retailedge_(?:mvp_smoke|rc3_acceptance)\.spec\.cjs/,
	fullyParallel: false,
	retries: 0,
	workers: 1,
	timeout: 90_000,
	expect: { timeout: 15_000 },
	use: {
		baseURL: process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000",
		// RC3 is a reviewed acceptance gate, not only an automated pass/fail gate.
		// Preserve successful-run evidence so the exact-head persona journeys can
		// be inspected independently before the release is promoted.
		trace: "on",
		screenshot: "on",
		video: "on",
	},
	reporter: [
		["line"],
		["html", { outputFolder: "playwright-report", open: "never" }],
	],
});
