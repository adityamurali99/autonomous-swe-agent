import { formtName } from "./formatter";

export function greet(name: string): string {
  return `Hello, ${formtName(name)}!`;
}
