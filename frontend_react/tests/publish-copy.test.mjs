import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/components/clip-library/publishCopy.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText
const { getPlatformCaption } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('selects platform copy and appends matching hashtags', () => {
  const clip = {
    title: 'Título original',
    tags: { social_copy: {
      tiktok_caption: 'Copy TikTok',
      reels_caption: 'Copy Reels',
      shorts_title: 'Shorts claro',
      hashtags: { tiktok: ['#parati'], reels: ['#reels'], shorts: ['#shorts'] },
    } },
  }

  assert.equal(getPlatformCaption(clip, 'tiktok'), 'Copy TikTok #parati')
  assert.equal(getPlatformCaption(clip, 'instagram'), 'Copy Reels #reels')
  assert.equal(getPlatformCaption(clip, 'youtube'), 'Shorts claro #shorts')
})

test('uses safe legacy defaults for clips without generated metadata', () => {
  assert.equal(getPlatformCaption({ title: 'Clip antiguo', tags: null }, 'tiktok'), 'Clip antiguo #parati #viral #clipsai')
  assert.equal(getPlatformCaption({ title: null, tags: [] }, 'youtube'), 'Mirá este momento #shorts #viral #clipsai')
})

test('ignores malformed hashtags and respects platform character caps', () => {
  const clip = { title: 'T'.repeat(200), tags: { social_copy: { shorts_title: 'S'.repeat(120), hashtags: { shorts: ['not-a-hashtag'] } } } }
  const caption = getPlatformCaption(clip, 'youtube')

  assert.equal(caption.length, 100)
  assert.match(caption, /^S+ #shorts #viral #clipsai$/)
})
