interface Props {
  caption: string;
  headers: string[];
  rows: string[][];
}

export function DataTable({ caption, headers, rows }: Props) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={h} scope="col" className={i === 0 ? "left" : "right"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]}>
              {row.map((cell, i) => (
                <td key={`${row[0]}-${headers[i]}`} className={i === 0 ? "left" : "right"}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}