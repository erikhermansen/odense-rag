import { describe, expect, it } from 'vitest'
import type { Source } from '../api/client'
import { groupSources, pluralKilder, sectionLabel, splitAnswer } from './answer'

describe('splitAnswer', () => {
  it('deler ved første sætning', () => {
    expect(splitAnswer('Ja, I må gerne. Det kræver to vidner.')).toEqual({
      headline: 'Ja, I må gerne.',
      body: 'Det kræver to vidner.',
    })
  })

  it('deler ikke ved punktum efter et tal', () => {
    expect(splitAnswer('Rådhuset har lukket den 28. november.')).toEqual({
      headline: 'Rådhuset har lukket den 28. november.',
      body: '',
    })
  })

  it('giver hele teksten som overskrift, hvis der kun er én sætning', () => {
    expect(splitAnswer('Et pas koster 723 kr')).toEqual({ headline: 'Et pas koster 723 kr', body: '' })
  })
})

describe('groupSources', () => {
  const source = (url: string, quote: string): Source => ({
    chunk_id: `${url}#${quote}`,
    title: `Titel ${url}`,
    section: 'Afsnit',
    url,
    quote,
  })

  it('samler citater fra samme side og bevarer rækkefølgen', () => {
    const pages = groupSources([source('a', 'x'), source('b', 'y'), source('a', 'z'), source('a', 'x')])

    expect(pages.map((p) => [p.url, p.quotes])).toEqual([
      ['a', ['x', 'z']],
      ['b', ['y']],
    ])
  })
})

it('bøjer kilde i ental og flertal', () => {
  expect(pluralKilder(1)).toBe('1 kilde')
  expect(pluralKilder(3)).toBe('3 kilder')
})

it('fjerner sidens overskrift fra afsnitsstien', () => {
  expect(sectionLabel('Vielse > Vielse i kirke')).toBe('Vielse i kirke')
  expect(sectionLabel('Vielse > Borgerlig vielse > Vidner')).toBe('Borgerlig vielse › Vidner')
  expect(sectionLabel('Vielse')).toBe('Vielse')
})
