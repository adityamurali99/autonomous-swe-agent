async function loadName(id: number): Promise<string> {
  return id === 1 ? "Ada" : "Unknown";
}

export async function loadUpperName(id: number): Promise<string> {
  return loadName(id).toString().toUpperCase();
}
