import assert from "node:assert/strict";
import test from "node:test";

import { normalizeOption } from "../src/options.js";

test("removes the option prefix", () => assert.equal(normalizeOption("--verbose"), "verbose"));
test("normalizes multi-word options to camelCase", () => assert.equal(normalizeOption("--dry-run"), "dryRun"));
