export function unsafeNumber(input: string): number {
  const value = Number(input);
  if (!Number.isFinite(value)) throw new Error("Enter a finite number");
  return value;
}