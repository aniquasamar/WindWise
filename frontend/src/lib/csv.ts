export type Cell = string | number | null;

function quote(cell: Cell): string {
  if (cell === null) return "";
  const text = String(cell);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: Cell[][]): string {
  return rows.map((row) => row.map(quote).join(",")).join("\r\n") + "\r\n";
}

export function downloadCsv(filename: string, csv: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}