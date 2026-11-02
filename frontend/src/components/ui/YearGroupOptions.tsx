export const YEAR_GROUPS = [7, 8, 9, 10, 11, 12, 13] as const;

/** Options for a year-group <select>. Fixed list: no free text, ever. */
export function YearGroupOptions({ placeholder }: { placeholder?: string }) {
  return (
    <>
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {YEAR_GROUPS.map((year) => (
        <option key={year} value={year}>
          Year {year}
        </option>
      ))}
    </>
  );
}
