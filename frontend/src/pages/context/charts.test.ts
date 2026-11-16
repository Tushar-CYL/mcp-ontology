import { describe, expect, it } from 'vitest'
import { compact, headline, shapeOf } from './charts'

describe('which chart answers a result', () => {
  it('one value is a big number', () => {
    expect(shapeOf(['total_payment_value'], [[2203373.09]])).toEqual(
      { kind: 'number', value: 2203373.09, label: 'total_payment_value' })
  })

  it('months and a count are a line', () => {
    const s = shapeOf(['month', 'orders'], [['2017-01', 800], ['2017-02', 1780], ['2017-03', 2682]])
    expect(s.kind).toBe('line')
  })

  it('labels and a number are bars, horizontal when long', () => {
    const short = shapeOf(['status', 'n'], [['paid', 3], ['shipped', 2]])
    expect(short).toMatchObject({ kind: 'bar', horizontal: false, x: ['paid', 'shipped'], y: [3, 2] })
    const long = shapeOf(['category', 'n'], [['health_beauty_and_more', 9], ['b', 1]])
    expect(long).toMatchObject({ kind: 'bar', horizontal: true })
  })

  it('draws only one number column (one axis) and finds it after the label', () => {
    const s = shapeOf(['city', 'orders', 'revenue'], [['sp', 5, 100.5], ['rj', 3, 50]])
    expect(s).toMatchObject({ kind: 'bar', yLabel: 'orders', xLabel: 'city' })
  })

  it('anything else stays a table', () => {
    expect(shapeOf(['a', 'b'], [['x', 'y']]).kind).toBe('table')
    expect(shapeOf([], []).kind).toBe('table')
  })
})

describe('compact numbers', () => {
  it('reads at a glance', () => {
    expect(compact(2203373.09)).toBe('2.2M')
    expect(compact(99441)).toBe('99.4k')
    expect(compact(1950)).toBe('1,950')
    expect(compact(3.14159)).toBe('3.14')
  })
})

describe('headline from the numbers', () => {
  it('names the biggest bar and its share', () => {
    const s = shapeOf(['method', 'total'], [['credit_card', 12542084.19], ['boleto', 2869361.27], ['voucher', 379436.87]])
    expect(headline(s)).toBe('credit_card is the largest: 12.5M, 79% of 15.8M.')
  })
  it('gives the latest and the peak for a line', () => {
    const s = shapeOf(['month', 'n'], [['2017-01', 800], ['2017-11', 7500], ['2018-08', 6500]])
    expect(headline(s)).toBe('6,500 in 2018-08; the peak was 7,500 in 2017-11.')
  })
  it('says nothing for a single number or a table', () => {
    expect(headline(shapeOf(['t'], [[5]]))).toBeNull()
  })
})
