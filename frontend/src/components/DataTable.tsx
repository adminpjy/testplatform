import type { ReactNode } from "react";

export interface DataTableColumn<T> {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  emptyText: string;
  getRowKey: (row: T) => string | number;
}

export function DataTable<T>({ columns, rows, emptyText, getRowKey }: DataTableProps<T>) {
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)}>
              {columns.map((column) => (
                <td key={column.key}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 ? <div className="empty-state">{emptyText}</div> : null}
    </div>
  );
}
