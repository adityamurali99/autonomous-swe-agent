import { renderHost } from "./host";
import { renderPort } from "./port";

export function renderAddress(host: string | undefined, port: number | undefined): string {
  return `${renderHost(host)},${renderPort(port)}`;
}
