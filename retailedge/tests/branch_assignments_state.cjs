const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(
	path.join(__dirname, "../public/js/branch_assignments/BranchAssignments.vue"),
	"utf8"
);

function setup(respond = () => ({})) {
	const requests = [];
	const sandbox = {
		module: { exports: {} },
		window: { EdgeSuiteUI: { components: {} } },
		__: (message) => message,
		frappe: {
			datetime: { get_today: () => "2026-10-20" },
			call(options) {
				requests.push(options.args);
				options.callback({ message: respond(options.args) });
			},
		},
	};
	const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
	vm.runInNewContext(script.replace("export default", "module.exports ="), sandbox);
	const component = sandbox.module.exports;
	const state = component.data();
	for (const [name, method] of Object.entries(component.methods)) {
		state[name] = method.bind(state);
	}
	return { state, requests };
}

test("assignment creation ignores a click event and preserves deliberate repair prefill", async () => {
	const { state } = setup();
	state.openAssign({ type: "click", target: {} });
	assert.equal(state.assign.user, "");
	assert.equal(state.assignOpen, true);
	state.readinessSummary.can_repair = true;
	await state.repairReadiness({ user: "incomplete@example.com", repair_action: { key: "assign_branch" } });
	assert.equal(state.assign.user, "incomplete@example.com");
	state.openAssign();
	assert.equal(state.assign.user, "");
	assert.match(source, /@click="openAssign\(\)"/);
});

test("all 205 readiness rows remain reachable across response pages", async () => {
	const users = Array.from({ length: 205 }, (_, index) => ({ user: `user-${index}@example.com` }));
	const { state, requests } = setup(({ start, page_length }) => ({
		rows: users.slice(start, start + page_length),
		total: users.length,
		has_more: start + page_length < users.length,
	}));
	await state.loadReadiness();
	assert.equal(state.readinessRows.length, 100);
	assert.equal(state.readinessHasMore, true);
	await state.loadReadiness({ append: true });
	await state.loadReadiness({ append: true });
	assert.deepEqual(requests.map((args) => args.start), [0, 100, 200]);
	assert.equal(state.readinessRows.length, 205);
	assert.equal(new Set(state.readinessRows.map((row) => row.user)).size, 205);
	assert.equal(state.readinessTotal, 205);
	assert.equal(state.readinessHasMore, false);
	assert.match(source, /v-if="readinessHasMore"/);
	assert.match(source, /Load More Users/);
});

test("changing the readiness view replaces rows from the first page", async () => {
	const { state, requests } = setup(({ include_ready }) => ({
		rows: [{ user: include_ready ? "ready@example.com" : "incomplete@example.com" }],
		total: 1,
		has_more: false,
	}));
	await state.loadReadiness();
	state.includeReadyUsers = true;
	await state.loadReadiness();
	assert.deepEqual(requests.map((args) => args.start), [0, 0]);
	assert.equal(requests[1].include_ready, 1);
	assert.equal(state.readinessRows.length, 1);
	assert.equal(state.readinessRows[0].user, "ready@example.com");
});
