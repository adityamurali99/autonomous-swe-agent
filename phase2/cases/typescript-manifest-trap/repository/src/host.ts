export function renderHost(host: string | undefined): string {
  return `host:${host || "localhost"}`;
}
