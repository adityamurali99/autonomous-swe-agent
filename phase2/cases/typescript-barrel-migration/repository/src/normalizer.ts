export function normalizeUser(value: string): string {
  return value.trim().toLowerCase();
}

export function normalizeUserId(value: string): string {
  return value.trim().toUpperCase();
}
