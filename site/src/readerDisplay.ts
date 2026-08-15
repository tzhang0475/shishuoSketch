/**
 * Remove physical witness line endings from reader prose.
 *
 * Canonical source/evidence keeps those line endings for provenance.  The
 * reading layer may already have removed them, but this final display guard
 * prevents a source-only newline from becoming a reader paragraph or forced
 * browser break if an older projection reaches the UI.
 */
export function normalizeReaderText(value: string): string {
  return value.replace(/\r\n?/gu, "").replace(/\n/gu, "");
}
