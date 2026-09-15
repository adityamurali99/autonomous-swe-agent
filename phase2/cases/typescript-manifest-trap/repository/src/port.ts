import { DEFAULT_PORT } from "./constants";

export function renderPort(port: number | null | undefined): string {
  return `port:${port || DEFAULT_PORT}`;
}
