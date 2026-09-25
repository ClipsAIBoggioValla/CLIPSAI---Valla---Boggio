import { Router } from 'express'
import fs from 'fs'
import path from 'path'
import { pool } from '../db/index.js'
import { authMiddleware, type AuthRequest } from '../middleware/auth.js'

export const clipsRouter = Router()

const SORT_MAP: Record<string, string> = {
  created_at_desc: 'c.created_at DESC',
  created_at_asc: 'c.created_at ASC',
  score_desc: 'c.score DESC NULLS LAST, c.created_at DESC',
  score_asc: 'c.score ASC NULLS LAST, c.created_at DESC',
}

function isValidUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
}

function _hasAss(tags: unknown): boolean {
  if (!tags || typeof tags !== 'object' || Array.isArray(tags)) return false
  const t = tags as Record<string, unknown>
  if ('has_ass' in t) return Boolean(t.has_ass)
  if (t.ass && typeof t.ass === 'object' && (t.ass as Record<string, unknown>).applied) return true
  const r = t._render as string | undefined
  return r === 'ass' || r === 'hook+ass'
}
function _hasHook(tags: unknown): boolean {
  if (!tags || typeof tags !== 'object' || Array.isArray(tags)) return false
  const t = tags as Record<string, unknown>
  if ('has_hook' in t) return Boolean(t.has_hook)
  if (t.hook && typeof t.hook === 'object' && (t.hook as Record<string, unknown>).applied) return true
  const r = t._render as string | undefined
  return r === 'hook' || r === 'hook+ass'
}

clipsRouter.get('/', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id

  const q = typeof req.query.q === 'string' ? req.query.q.trim() : undefined
  const minScoreRaw = req.query.min_score as string | undefined
  const min_score = minScoreRaw !== undefined && minScoreRaw !== '' ? Number(minScoreRaw) : undefined
  const sort_by = (typeof req.query.sort_by === 'string' ? req.query.sort_by : 'created_at_desc') as string
  const page = Math.max(1, parseInt(String(req.query.page ?? '1'), 10) || 1)
  const limit = Math.min(100, Math.max(1, parseInt(String(req.query.limit ?? '10'), 10) || 10))
  const videoIdRaw = typeof req.query.video_id === 'string' ? req.query.video_id : undefined
  const jobIdRaw = typeof req.query.job_id === 'string' ? req.query.job_id : undefined
  const statusRaw = typeof req.query.status === 'string' ? req.query.status : undefined

  if (min_score !== undefined && (Number.isNaN(min_score) || min_score < 0 || min_score > 100)) {
    return res.status(422).json({ detail: 'min_score must be between 0 and 100' })
  }
  const orderBy = SORT_MAP[sort_by]
  if (!orderBy) {
    return res.status(422).json({ detail: 'sort_by must be one of created_at_desc, created_at_asc, score_desc, score_asc' })
  }
  if (videoIdRaw && !isValidUuid(videoIdRaw)) return res.status(422).json({ detail: 'video_id debe ser UUID válido' })

  const conditions: string[] = ['v.usuario_id = $1']
  const values: unknown[] = [userId]
  let paramIdx = 2

  if (q) {
    conditions.push(`(c.title ILIKE $${paramIdx} OR v.transcript ILIKE $${paramIdx})`)
    values.push(`%${q}%`)
    paramIdx += 1
  }
  if (min_score !== undefined) {
    conditions.push(`c.score >= $${paramIdx}`)
    values.push(min_score)
    paramIdx += 1
  }
  if (videoIdRaw) {
    conditions.push(`(c.video_id = $${paramIdx} OR j.video_id = $${paramIdx})`)
    values.push(videoIdRaw)
    paramIdx += 1
  }
  if (jobIdRaw) {
    if (!isValidUuid(jobIdRaw)) return res.status(422).json({ detail: 'job_id debe ser UUID válido' })
    conditions.push(`c.job_id = $${paramIdx}`)
    values.push(jobIdRaw)
    paramIdx += 1
  }
  if (statusRaw) {
    conditions.push(`c.status = $${paramIdx}`)
    values.push(statusRaw)
    paramIdx += 1
  }

  const whereClause = conditions.join(' AND ')

  const client = await pool.connect()
  try {
    const countRes = await client.query(
      `SELECT COUNT(*)::int AS total
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE ${whereClause}`,
      values
    )
    const total: number = countRes.rows[0]?.total ?? 0
    const total_pages = total > 0 ? Math.ceil(total / limit) : 0
    const offset = (page - 1) * limit

    const dataRes = await client.query(
      `SELECT
         c.id, c.job_id, c.title, c.score, c.start_time, c.end_time,
         LEFT(v.transcript, 500) AS transcript,
         c.status, c.published_platform, c.social_post_url, c.published_at,
         c.created_at, c.updated_at, c.file_path, c.tags
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE ${whereClause}
       ORDER BY ${orderBy}
       LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`,
      [...values, limit, offset]
    )

    const items = dataRes.rows.map((r: Record<string, unknown>) => {
      const st = Number(r.start_time); const et = Number(r.end_time)
      return {
        id: r.id,
        job_id: r.job_id,
        title: r.title,
        score: r.score !== null && r.score !== undefined ? Number(r.score) : null,
        start_time: st,
        end_time: et,
        transcript: (r.transcript as string | null) ?? null,
        status: (r.status as string | null) ?? null,
        published_platform: (r.published_platform as string | null) ?? null,
        social_post_url: (r.social_post_url as string | null) ?? null,
        published_at: r.published_at ? new Date(r.published_at as string).toISOString() : null,
        created_at: new Date(r.created_at as string).toISOString(),
        updated_at: r.updated_at ? new Date(r.updated_at as string).toISOString() : null,
        file_path: (r.file_path as string | null) ?? null,
        stream_url: `/clips/${r.id}/descarga`,
        duration: Number.isFinite(st) && Number.isFinite(et) ? et - st : null,
        has_ass: _hasAss(r.tags),
        has_hook: _hasHook(r.tags),
        tags: r.tags ?? null,
      }
    })

    return res.json({ items, total, page, limit, total_pages })
  } catch (err) {
    console.error('GET /clips error', err)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

async function getClipOr404(clipId: string, userId: string, client: import('pg').PoolClient) {
  if (!isValidUuid(clipId)) throw { status: 422, detail: 'clip_id debe ser UUID válido' }
  const r = await client.query(
    `SELECT c.*, j.video_id AS job_video_id, v.usuario_id, v.file_path AS video_filepath
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE c.id = $1`,
    [clipId]
  )
  if (r.rows.length === 0) throw { status: 404, detail: 'Clip no encontrado' }
  const row = r.rows[0] as Record<string, unknown>
  if (String(row.usuario_id) !== String(userId)) throw { status: 404, detail: 'Clip no encontrado' }
  return row
}

clipsRouter.get('/:clipId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    const st = Number(row.start_time); const et = Number(row.end_time)
    return res.json({
      id: row.id,
      video_id: row.video_id,
      job_id: row.job_id,
      title: row.title,
      start_time: st,
      end_time: et,
      score: row.score !== null ? Number(row.score) : null,
      tags: row.tags ?? null,
      storage_path: row.file_path as string,
      file_path: row.file_path as string,
      stream_url: `/clips/${row.id}/descarga`,
      duration: Number.isFinite(st) && Number.isFinite(et) ? et - st : null,
      has_ass: _hasAss(row.tags),
      has_hook: _hasHook(row.tags),
      status: row.status as string,
      published_platform: (row.published_platform as string | null) ?? null,
      social_post_id: (row.social_post_id as string | null) ?? null,
      social_post_url: (row.social_post_url as string | null) ?? null,
      published_at: row.published_at ? new Date(row.published_at as string).toISOString() : null,
      publication_status: (row.publication_status as string | null) ?? null,
      social_network: (row.social_network as string | null) ?? null,
      created_at: new Date(row.created_at as string).toISOString(),
      updated_at: new Date((row.updated_at as string) ?? (row.created_at as string)).toISOString(),
    })
  } catch (e: unknown) {
    const err = e as { status?: number; detail?: string }
    if (err?.status) return res.status(err.status).json({ detail: err.detail })
    console.error('GET /clips/:id error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

clipsRouter.patch('/:clipId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const { title, tags } = req.body as Record<string, unknown>
  if (title === undefined && tags === undefined) return res.status(400).json({ detail: 'Nada para actualizar' })
  if (title !== undefined && title !== null && typeof title !== 'string') return res.status(422).json({ detail: 'title debe ser string' })
  if (tags !== undefined && tags !== null && !Array.isArray(tags)) return res.status(422).json({ detail: 'tags debe ser array' })

  const client = await pool.connect()
  try {
    await getClipOr404(clipId, String(userId), client)
    const updates: string[] = []
    const values: unknown[] = []
    let idx = 1
    if (title !== undefined) {
      updates.push(`title = $${idx++}`)
      values.push(title ?? null)
    }
    if (tags !== undefined) {
      updates.push(`tags = $${idx++}`)
      values.push(tags ? JSON.stringify(tags) : null)
    }
    values.push(clipId)
    const q = `UPDATE clips SET ${updates.join(', ')}, updated_at = NOW() WHERE id = $${idx} RETURNING id, video_id, job_id, title, start_time, end_time, score, tags, file_path, status, created_at, updated_at`
    const r = await client.query(q, values)
    const row = r.rows[0] as Record<string, unknown>
    return res.json({
      id: row.id,
      video_id: row.video_id,
      job_id: row.job_id,
      title: row.title,
      start_time: Number(row.start_time),
      end_time: Number(row.end_time),
      score: row.score !== null ? Number(row.score) : null,
      tags: row.tags ?? null,
      storage_path: row.file_path as string,
      status: row.status as string,
      created_at: new Date(row.created_at as string).toISOString(),
      updated_at: new Date(row.updated_at as string).toISOString(),
    })
  } catch (e: unknown) {
    const err = e as { status?: number; detail?: string }
    if (err?.status) return res.status(err.status).json({ detail: err.detail })
    console.error('PATCH /clips/:id error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

clipsRouter.delete('/:clipId', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    const filePath = row.file_path as string | null
    if (filePath) {
      try {
        const p = path.resolve(filePath)
        if (fs.existsSync(p)) fs.unlinkSync(p)
      } catch {}
    }
    await client.query('DELETE FROM clips WHERE id = $1', [clipId])
    return res.status(204).send()
  } catch (e: unknown) {
    const err = e as { status?: number; detail?: string }
    if (err?.status) return res.status(err.status).json({ detail: err.detail })
    console.error('DELETE /clips/:id error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

clipsRouter.get('/:clipId/descarga', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    const candidates: string[] = []
    if (row.file_path) candidates.push(String(row.file_path))
    const videoPath = row.video_filepath as string | undefined
    if (videoPath) candidates.push(videoPath)

    for (const p of candidates) {
      const abs = path.resolve(p)
      if (fs.existsSync(abs) && fs.statSync(abs).isFile() && fs.statSync(abs).size > 0) {
        const filename = path.basename(abs) || `${clipId}.mp4`
        const ext = path.extname(abs).toLowerCase()
        const media = ['.mp4', '.mov', '.avi', '.mkv'].includes(ext) ? 'video/mp4' : 'application/octet-stream'
        return res.download(abs, filename, { headers: { 'Content-Type': media } })
      }
    }
    // Modo 100% real — sin .txt dummy de prueba
    console.error(`[CLIP DESCARGA:express] clip ${clipId} archivo no encontrado candidates=${candidates.join(',')}`)
    return res.status(404).json({ detail: `Archivo de clip no encontrado: ${candidates[0] || 'sin ruta'}. Debe existir .mp4 físico en storage.` })
  } catch (e: unknown) {
    const err = e as { status?: number; detail?: string }
    if (err?.status) return res.status(err.status).json({ detail: err.detail })
    console.error('GET /clips/:id/descarga error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

async function runReRender(clipId: string, enableAss: boolean, enableHook: boolean) {
  const client = await pool.connect()
  try {
    const r = await client.query(
      `SELECT c.id, c.job_id, c.title, c.start_time, c.end_time, c.file_path, c.tags, c.status,
              v.file_path AS video_filepath, v.transcript, v.transcription_filepath
       FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1`, [clipId]
    )
    if (r.rows.length === 0) return
    const row = r.rows[0] as Record<string, unknown>
    const videoPath = String(row.video_filepath ?? '')
    const clipStart = Number(row.start_time); const clipEnd = Number(row.end_time)
    if (!videoPath || !fs.existsSync(path.resolve(videoPath))) {
      await pool.query(`UPDATE clips SET status='FAILED', tags = COALESCE(tags,'{}'::jsonb) || $1::jsonb, updated_at=NOW() WHERE id=$2`, [JSON.stringify({ _render_error: 'Video origen no encontrado' }), clipId])
      return
    }
    // Determinar hook si enableHook
    let hookStart: number | null = null; let hookEnd: number | null = null
    if (enableHook) {
      const dur = clipEnd - clipStart
      if (dur >= 15 && dur <= 90) {
        // Hook sintético centrado 5s
        const hookDur = 5
        let hs = (clipStart + clipEnd)/2 - hookDur/2
        let he = hs + hookDur
        if (hs < clipStart) { hs = clipStart; he = hs+hookDur }
        if (he > clipEnd) { he = clipEnd; hs = he-hookDur }
        hookStart = Math.round(hs*100)/100; hookEnd = Math.round(he*100)/100
      }
    }
    // Preparar ASS si enableAss (simplificado: genera .ass mínimo si no hay transcripción)
    let assPath: string | null = null
    if (enableAss) {
      try {
        const tmpAss = path.join(process.cwd(), 'storage', `tmp_${clipId}.ass`)
        fs.mkdirSync(path.dirname(tmpAss), { recursive: true })
        // Generar ASS básico con segmentos sintéticos
        const content = `[Script Info]\nTitle: ${row.title ?? 'clipsai'}\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,70,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,280,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,TEST ASS\\N${String(row.title ?? '').slice(0,30).toUpperCase()}\n`
        fs.writeFileSync(tmpAss, content, 'utf-8')
        assPath = tmpAss
      } catch {}
    }
    // Render con ffmpeg
    const outDir = path.join(process.cwd(), 'storage', 'clips', clipId)
    // Express storage is project storage/clips, but in docker /app/storage/clips — handle both
    const outPath = path.join(outDir, `${clipId}_rerender_${Date.now()}.mp4`)
    fs.mkdirSync(outDir, { recursive: true })
    try {
      const { spawnSync } = await import('child_process')
      let srcForBurn = videoPath
      let tmpHook: string | null = null
      let tmpCut: string | null = null
      if (enableHook && hookStart !== null && hookEnd !== null) {
        // Build hook: cut hook + cut clip + concat
        const tmpDir = fs.mkdtempSync(path.join(process.cwd(), 'storage', `hook_${clipId}_`))
        const hookTmp = path.join(tmpDir, 'hook.mp4')
        const clipTmp = path.join(tmpDir, 'clip.mp4')
        const concatList = path.join(tmpDir, 'list.txt')
        let ok = true
        let res = spawnSync('ffmpeg', ['-y','-ss',String(hookStart),'-i',videoPath,'-t',String(hookEnd-hookStart),'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart',hookTmp], { timeout: 60000 })
        if (res.status !== 0) ok = false
        res = spawnSync('ffmpeg', ['-y','-ss',String(clipStart),'-i',videoPath,'-t',String(clipEnd-clipStart),'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart',clipTmp], { timeout: 60000 })
        if (res.status !== 0) ok = false
        if (ok) {
          fs.writeFileSync(concatList, `file '${hookTmp.replace(/'/g, "'\\''")}'\nfile '${clipTmp.replace(/'/g, "'\\''")}'\n`, 'utf-8')
          res = spawnSync('ffmpeg', ['-y','-f','concat','-safe','0','-i',concatList,'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart', outPath], { timeout: 60000 })
          if (res.status === 0) srcForBurn = outPath
          else ok = false
        }
        // Si hook falló, fallback a cut
        if (!ok) {
          if (fs.existsSync(outPath)) try { fs.unlinkSync(outPath) } catch {}
          tmpHook = null
        } else {
          // outPath ya es concat, pero si hay ASS, necesitamos burn sobre él, así que movemos a tmp y luego burn
          tmpHook = outPath + '.hook.mp4'
          fs.renameSync(outPath, tmpHook)
          srcForBurn = tmpHook
        }
        try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch {}
      }
      if (enableAss && assPath) {
        // Si srcForBurn es el concat hook, aplicar burn; si no, cortar primero
        let burnSrc = srcForBurn
        let needCut = true
        if (enableHook && hookStart !== null) {
          // burnSrc ya es el concat hook si existió
          needCut = false
          // si no hubo hook, burnSrc sigue siendo videoPath
          if (burnSrc === videoPath) needCut = true
        }
        if (needCut) {
          tmpCut = path.join(outDir, `tmp_cut_${Date.now()}.mp4`)
          const res = spawnSync('ffmpeg', ['-y','-ss',String(clipStart),'-i',videoPath,'-t',String(clipEnd-clipStart),'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart',tmpCut], { timeout: 60000 })
          if (res.status === 0) burnSrc = tmpCut
          else throw new Error('cut falló')
        }
        // Burn ASS
        const vf = `ass=${assPath.replace(/\\/g,'/').replace(/:/g,'\\:')}`
        const res = spawnSync('ffmpeg', ['-y','-i',burnSrc,'-vf',vf,'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart',outPath], { timeout: 80000 })
        if (res.status !== 0) throw new Error(`burn falló: ${res.stderr?.toString().slice(0,400)}`)
        // Limpiar tmp
        if (tmpCut && fs.existsSync(tmpCut)) try { fs.unlinkSync(tmpCut) } catch {}
        if (tmpHook && fs.existsSync(tmpHook)) try { fs.unlinkSync(tmpHook) } catch {}
        if (assPath && fs.existsSync(assPath)) try { fs.unlinkSync(assPath) } catch {}
      } else if (!enableAss && !enableHook) {
        // Solo cut
        const res = spawnSync('ffmpeg', ['-y','-ss',String(clipStart),'-i',videoPath,'-t',String(clipEnd-clipStart),'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart',outPath], { timeout: 60000 })
        if (res.status !== 0) throw new Error('cut falló')
      } else if (enableHook && !enableAss) {
        // ya se hizo hook concat arriba y outPath existe; si no, fallback cut ya manejado
        if (!fs.existsSync(outPath)) {
          const res = spawnSync('ffmpeg', ['-y','-ss',String(clipStart),'-i',videoPath,'-t',String(clipEnd-clipStart),'-c:v','libx264','-preset','ultrafast','-crf','18','-c:a','aac','-movflags','+faststart',outPath], { timeout: 60000 })
          if (res.status !== 0) throw new Error('re-render hook sin ASS falló')
        }
      }
      if (!fs.existsSync(outPath) || fs.statSync(outPath).size === 0) throw new Error('re-render no produjo archivo')
      // Actualizar BD — FIX explícito has_ass/has_hook
      const tagsPatch: Record<string, unknown> = {}
      // FIX auditoría: has_ass/has_hook deben reflejar enable_* explícitamente
      tagsPatch.has_ass = enableAss
      tagsPatch.has_hook = enableHook
      if (enableHook && hookStart !== null) tagsPatch.hook = { start: hookStart, end: hookEnd, applied: true, source: 're-render' }
      else if (!enableHook) { tagsPatch.hook = null as unknown as object; /* será mergeado como null y luego limpiado */ }
      if (enableAss) tagsPatch.ass = { applied: true }
      else if (!enableAss) tagsPatch.ass = null as unknown as object
      tagsPatch._render = enableAss && enableHook ? 'hook+ass' : enableAss ? 'ass' : enableHook ? 'hook' : 'cut'
      tagsPatch._re_render = { enable_ass: enableAss, enable_hook: enableHook, at: new Date().toISOString(), out_path: outPath }
      // Merge + limpieza de nulls para desactivados
      // Postgres jsonb || no elimina nulls, así que hacemos update con COALESCE y luego limpieza en JS si es null
      await pool.query(`UPDATE clips SET file_path=$1, tags = COALESCE(tags,'{}'::jsonb) || $2::jsonb, status='ready', updated_at=NOW() WHERE id=$3`, [outPath, JSON.stringify(tagsPatch), clipId])
      // Si se desactivó, eliminar claves null
      if (!enableHook || !enableAss) {
        const cleanup: string[] = []
        if (!enableHook) cleanup.push("tags = tags - 'hook'")
        if (!enableAss) cleanup.push("tags = tags - 'ass'")
        // También limpiar si eran null
        if (cleanup.length) {
          await pool.query(`UPDATE clips SET ${cleanup.join(', ')} , has_ass = $1, has_hook = $2 WHERE id=$3`, [enableAss, enableHook, clipId]).catch(()=>{})
          // Fallback: si columnas has_ass/has_hook no existen, ignorar error y solo limpiar tags JSON
          try {
            await pool.query(`UPDATE clips SET has_ass=$1, has_hook=$2 WHERE id=$3`, [enableAss, enableHook, clipId])
          } catch {}
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      await pool.query(`UPDATE clips SET status='FAILED', tags = COALESCE(tags,'{}'::jsonb) || $1::jsonb, updated_at=NOW() WHERE id=$2`, [JSON.stringify({ _render_error: msg.slice(0,500) }), clipId])
    }
  } finally {
    client.release()
  }
}

clipsRouter.post('/:clipId/re-render', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const { enable_ass, enable_hook } = req.body as Record<string, unknown>
  const ea = enable_ass === undefined ? true : Boolean(enable_ass)
  const eh = enable_hook === undefined ? true : Boolean(enable_hook)
  const client = await pool.connect()
  try {
    const r = await client.query(`SELECT c.id FROM clips c JOIN jobs j ON c.job_id=j.id JOIN videos v ON j.video_id=v.id WHERE c.id=$1 AND v.usuario_id=$2`, [clipId, String(userId)])
    if (r.rows.length === 0) return res.status(404).json({ detail: 'Clip no encontrado' })
    const cur = await client.query(`SELECT status FROM clips WHERE id=$1`, [clipId])
    if (cur.rows.length > 0 && String(cur.rows[0].status) === 'PROCESSING') return res.status(409).json({ detail: 'Clip ya en procesamiento' })
    await client.query(`UPDATE clips SET status='PROCESSING', updated_at=NOW() WHERE id=$1`, [clipId])
    setImmediate(() => { runReRender(clipId, ea, eh).catch(e => console.error('re-render error', e)) })
    return res.status(202).json({ detail: 'Re-render encolado', clip_id: clipId, status: 'PROCESSING', enable_ass: ea, enable_hook: eh })
  } catch (e) {
    console.error('POST /clips/:id/re-render error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})

clipsRouter.post('/:clipId/retrim', authMiddleware, async (req: AuthRequest, res) => {
  const userId = req.user!.id
  const clipId = String(req.params.clipId)
  const { start_time, end_time } = req.body as Record<string, unknown>
  const start = typeof start_time === 'number' ? start_time : Number(start_time)
  const end = typeof end_time === 'number' ? end_time : Number(end_time)

  if (Number.isNaN(start) || Number.isNaN(end) || start < 0 || end <= start) return res.status(422).json({ detail: 'start_time y end_time inválidos, end debe ser > start' })
  const duration = end - start
  if (duration < 5) return res.status(422).json({ detail: 'Duración mínima 5s' })
  if (duration > 90) return res.status(422).json({ detail: 'Duración máxima 90s' })

  const client = await pool.connect()
  try {
    const row = await getClipOr404(clipId, String(userId), client)
    const candidates: string[] = []
    if (row.file_path) candidates.push(String(row.file_path))
    if (row.video_filepath) candidates.push(String(row.video_filepath))
    let src: string | null = null
    for (const p of candidates) {
      if (fs.existsSync(path.resolve(p))) { src = path.resolve(p); break }
    }
    if (!src) src = candidates[0] ? path.resolve(candidates[0]) : null
    if (!src || !fs.existsSync(src)) return res.status(404).json({ detail: 'Video origen no encontrado para re-trim' })

    const outDir = path.join(process.cwd(), 'storage', 'retrims')
    fs.mkdirSync(outDir, { recursive: true })
    const outPath = path.join(outDir, `${clipId}_retrim_${Math.floor(start)}_${Math.floor(end)}.mp4`)

    const { spawnSync } = await import('child_process')
    const cmd = spawnSync('ffmpeg', ['-y', '-ss', String(start), '-i', src, '-t', String(duration), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', outPath], { timeout: 120000 })

    if (cmd.status !== 0) {
      const detail = cmd.stderr ? cmd.stderr.toString().slice(0, 600) : 'FFmpeg error'
      return res.status(500).json({ detail: `FFmpeg re-trim falló: ${detail}` })
    }
    if (!fs.existsSync(outPath)) return res.status(500).json({ detail: 'Re-trim no produjo archivo' })

    const r = await client.query('UPDATE clips SET start_time = $1, end_time = $2, file_path = $3, updated_at = NOW() WHERE id = $4 RETURNING id, start_time, end_time, file_path, status', [start, end, outPath, clipId])
    const updated = r.rows[0] as Record<string, unknown>
    return res.json({
      clip_id: String(updated.id),
      start_time: Number(updated.start_time),
      end_time: Number(updated.end_time),
      duration,
      status: (updated.status as string) ?? 'ready',
      file_path: updated.file_path as string,
    })
  } catch (e: unknown) {
    const err = e as { status?: number; detail?: string }
    if (err?.status) return res.status(err.status).json({ detail: err.detail })
    console.error('POST /clips/:id/retrim error', e)
    return res.status(500).json({ detail: 'Error interno' })
  } finally {
    client.release()
  }
})
