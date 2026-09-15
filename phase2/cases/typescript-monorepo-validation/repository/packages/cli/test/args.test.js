import assert from "node:assert/strict";
import test from "node:test";

import { parseArgs } from "../src/args.js";

test("recognizes dry-run", () => assert.deepEqual(parseArgs(["--dry-run"]), { dryRun: true }));
test("defaults dry-run to false", () => assert.deepEqual(parseArgs(["--verbose"]), { dryRun: false }));
