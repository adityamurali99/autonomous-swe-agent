import { normalizeOption } from "@fixture/core/src/options.js";

export function parseArgs(args) {
  const normalized = args.map(normalizeOption);
  return { dryRun: normalized.some((option) => option === "dry-run") };
}
