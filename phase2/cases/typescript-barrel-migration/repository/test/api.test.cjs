const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../dist/index.js");
const { createUser } = require("../dist/service.js");
const cli = require("../src/cli.cjs");

test("exports the corrected public API", () => {
  assert.equal(api.normalizeUsername(" Ada "), "ada");
  assert.equal(api.normalizeUser, undefined);
});

test("updates TypeScript and JavaScript consumers", () => {
  assert.equal(createUser(" Grace ").username, "grace");
  assert.equal(cli.run(" Linus "), "linus");
});

test("preserves the distinct ID normalizer", () => {
  assert.equal(api.normalizeUserId(" user-1 "), "USER-1");
});
