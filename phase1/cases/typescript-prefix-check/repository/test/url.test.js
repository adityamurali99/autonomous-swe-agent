import assert from "node:assert/strict";
import test from "node:test";

import { isSecureUrl } from "../src/url.js";

test("accepts a secure URL", () => assert.equal(isSecureUrl("https://example.com"), true));
test("rejects embedded scheme", () => assert.equal(isSecureUrl("redirect?to=https://example.com"), false));
