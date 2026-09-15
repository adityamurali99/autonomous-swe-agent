import { normalizeUser } from "./index";

export function createUser(rawName: string): { username: string } {
  return { username: normalizeUser(rawName) };
}
