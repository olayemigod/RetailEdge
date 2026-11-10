import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(
  new URL("../public/js/thermalReceiptPrinting.js", import.meta.url),
  "utf8",
);
const module = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);

const PROFILE = "Ketu POS Print Profile";
let status = { connected: false, boundProfile: "" };
let mode = "handoff";
let connects = 0;
let disconnects = 0;
let writes = 0;
const calls = [];
const adapter = {
  getStatus: () => status,
  async disconnect() {
    disconnects++;
    status = { connected: false, boundProfile: "" };
    return status;
  },
  devices: {
    bindingMatchesStatus(profile, candidate) {
      return candidate?.connected && candidate?.boundProfile === profile;
    },
    async connectBoundSerial(profile, options) {
      connects++;
      assert.equal(profile, PROFILE);
      assert.equal(options.openOptions.baudRate, 9600);
      if (mode === "busy") {
        const error = new Error("The receipt printer is being used in another browser tab.");
        error.code = "SERIAL_TAB_IN_USE";
        throw error;
      }
      status = {
        connected: true,
        boundProfile: mode === "wrong_port" ? "Another Branch Receipt" : PROFILE,
        // All SPP printers may expose the same UUID; this is NOT identity.
        portInfo: { bluetoothServiceClassId: "00001101-0000-1000-8000-00805f9b34fb" },
      };
      return { status };
    },
  },
  profiles: {
    async resolve(context) {
      assert.equal(context.productKey, "retailedge");
      assert.equal(context.purpose, "Receipt");
      assert.equal(context.company, "RetailEdge Consulting");
      assert.equal(context.branch, "Ketu");
      return { name: PROFILE, transport: "serial" };
    },
    connectionOptions() { return { openOptions: { baudRate: 9600 } }; },
    receiptOptions() {
      return {
        paper: 58,
        charactersPerLine: 32,
        feedLines: 2,
        printQr: false,
        copies: 1,
        autoCut: false,
        cashDrawer: false,
      };
    },
    textEncoder() {
      return (value) => new TextEncoder().encode(String(value));
    },
  },
  async printReceipt(document, opts) {
    writes++;
    assert.equal(document.paper, 58);
    assert.equal(document.blocks[0].text, "Authorised invoice");
    assert.equal(opts.transport, "serial");
    return { bytesWritten: 50 };
  },
};
globalThis.window = { EdgeSuiteUI: { print: adapter } };
globalThis.frappe = {
  call({ method, args, type, callback }) {
    calls.push({ method, args, type });
    assert.equal(type, "GET");
    assert.equal(args.document, "Sales Invoice");
    assert.equal(args.name, "ACC-SINV-2026-00041");
    callback({
      message: {
        company: "RetailEdge Consulting",
        branch: "Ketu",
        blocks_by_paper: {
          "58": [{ type: "text", text: "Authorised invoice" }],
        },
      },
    });
  },
};
const options = { document: "Sales Invoice", name: "ACC-SINV-2026-00041" };

// A tab holding the right binding can print without reconnecting.
status = { connected: true, boundProfile: PROFILE };
let result = await module.printRetailReceipt(options);
assert.equal(result.printed, true);
assert.equal(connects, 0);
assert.equal(writes, 1);

// After another tab takes the port, reconnecting restores this exact profile.
status = { connected: false, boundProfile: "" };
result = await module.printRetailReceipt(options);
assert.equal(result.printed, true);
assert.equal(connects, 1);
assert.equal(writes, 2);

// A busy tab is actionable; do not send data, open extra setup, or create sales.
mode = "busy";
status = { connected: false, boundProfile: "" };
await assert.rejects(
  module.printRetailReceipt(options),
  error => error.code === "RETAIL_PRINTER_TAB_BUSY"
    && error.cause?.code === "SERIAL_TAB_IN_USE"
    && /another browser tab/.test(error.message),
);
assert.equal(writes, 2);

// Two Bluetooth printers can report an identical service UUID. A restored
// port must still match the exact branch profile, or we close and fail.
mode = "wrong_port";
status = {
  connected: true,
  boundProfile: "Another Branch Receipt",
  portInfo: { bluetoothServiceClassId: "00001101-0000-1000-8000-00805f9b34fb" },
};
await assert.rejects(
  module.printRetailReceipt(options),
  error => error.code === "RETAIL_PRINTER_SETUP_REQUIRED",
);
assert.equal(writes, 2);
assert.equal(disconnects, 2);
assert.equal(calls.length, 4);
console.log("RetailEdge Document Output serial handoff, busy-tab and branch binding PASS");
