import type { ReactNode } from 'react'
import { cx } from '../utils/cx'

export interface Column<T> {
  key: string
  header: ReactNode
  render: (row: T, index: number) => ReactNode
  align?: 'left' | 'right' | 'center'
  width?: string
  className?: string
}

interface TableProps<T> {
  columns: Array<Column<T>>
  rows: T[]
  rowKey: (row: T, index: number) => string
  caption?: string
  empty?: ReactNode
  dense?: boolean
  className?: string
  maxHeight?: number
}

/** A real <table> with scoped headers, used everywhere data is tabular. */
export function Table<T>({
  columns,
  rows,
  rowKey,
  caption,
  empty,
  dense = false,
  className,
  maxHeight,
}: TableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="table-empty" role="status">
        {empty ?? 'Nothing to show yet.'}
      </div>
    )
  }

  return (
    <div className={cx('table-scroll', className)} style={maxHeight ? { maxHeight } : undefined}>
      <table className={cx('table', dense && 'table--dense')}>
        {caption ? <caption className="table__caption">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={{ textAlign: column.align, width: column.width }}
                className={column.className}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={rowKey(row, index)}>
              {columns.map((column) => (
                <td key={column.key} style={{ textAlign: column.align }} className={column.className}>
                  {column.render(row, index)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
