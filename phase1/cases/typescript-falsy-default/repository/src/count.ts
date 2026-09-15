export function displayCount(count: number | null | undefined, fallback: number): number {
  return count || fallback;
}
