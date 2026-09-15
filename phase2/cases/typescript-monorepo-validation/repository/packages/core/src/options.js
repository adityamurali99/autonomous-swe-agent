export function normalizeOption(raw) {
  return raw.replace(/^--/, "").replaceAll("-", "_");
}

export function optionLabel(raw) {
  return `option:${normalizeOption(raw)}`;
}
