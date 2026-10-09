import crypto from 'crypto'

/**
 * Generación de URLs prefirmadas S3 (SigV4, query-string auth) sin SDK.
 *
 * Paridad con `boto3.client("s3", ...).generate_presigned_url(...)` de FastAPI:
 *   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
 *   - `AWS_ENDPOINT_URL` (Cloudflare R2), `AWS_REGION` (default `auto`)
 *   - `BUCKET_NAME` (default `clipsai-videos`)
 *
 * Usa direccionamiento path-style (`<endpoint>/<bucket>/<key>`), que R2 acepta.
 */

const AWS_ALGORITHM = 'AWS4-HMAC-SHA256'
const SERVICE = 's3'

function sha256Hex(data: string | Buffer): string {
  return crypto.createHash('sha256').update(data).digest('hex')
}

function hmac(key: Buffer | string, data: string): Buffer {
  return crypto.createHmac('sha256', key).update(data).digest()
}

/** RFC 3986 URI encoding (encodeSlash=false preserva `/`). */
function uriEncode(input: string, encodeSlash = true): string {
  let out = ''
  for (const ch of input) {
    if (/[A-Za-z0-9\-_.~]/.test(ch)) {
      out += ch
    } else if (ch === '/' && !encodeSlash) {
      out += ch
    } else {
      const bytes = Buffer.from(ch, 'utf-8')
      for (const b of bytes) out += '%' + b.toString(16).toUpperCase().padStart(2, '0')
    }
  }
  return out
}

function amzDate(d = new Date()): { amz: string; date: string } {
  const iso = d.toISOString().replace(/[:-]|\.\d{3}/g, '') // YYYYMMDDTHHMMSSZ
  return { amz: iso, date: iso.slice(0, 8) }
}

export interface PresignOptions {
  method: 'PUT' | 'GET'
  key: string
  expiresIn: number
  contentType?: string
}

export interface S3Config {
  accessKeyId: string
  secretAccessKey: string
  region: string
  bucket: string
  endpoint: string
}

export function getS3Config(): S3Config {
  const accessKeyId = (process.env.AWS_ACCESS_KEY_ID || '').trim()
  const secretAccessKey = (process.env.AWS_SECRET_ACCESS_KEY || '').trim()
  if (!accessKeyId || !secretAccessKey) {
    throw new Error('AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY no están configuradas')
  }
  const region = (process.env.AWS_REGION || 'auto').trim() || 'auto'
  const bucket = (process.env.BUCKET_NAME || 'clipsai-videos').trim()
  const endpoint = (process.env.AWS_ENDPOINT_URL || '').trim().replace(/\/+$/, '')
  return { accessKeyId, secretAccessKey, region, bucket, endpoint }
}

function endpointHost(endpoint: string, region: string): { protocol: string; host: string } {
  const base = endpoint || `https://s3.${region}.amazonaws.com`
  const url = new URL(base)
  return { protocol: url.protocol.replace(':', ''), host: url.host }
}

/** Firma y devuelve una URL prefirmada (query-string) para `put_object`/`get_object`. */
export function generatePresignedUrl(opts: PresignOptions): string {
  const cfg = getS3Config()
  const { protocol, host } = endpointHost(cfg.endpoint, cfg.region)
  const { amz, date } = amzDate()

  const canonicalUri = `/${uriEncode(cfg.bucket, false)}/${opts.key.split('/').map((s) => uriEncode(s)).join('/')}`
  const scope = `${date}/${cfg.region}/${SERVICE}/aws4_request`

  const params: Record<string, string> = {
    'X-Amz-Algorithm': AWS_ALGORITHM,
    'X-Amz-Credential': `${cfg.accessKeyId}/${scope}`,
    'X-Amz-Date': amz,
    'X-Amz-Expires': String(opts.expiresIn),
    'X-Amz-SignedHeaders': 'host',
  }
  const canonicalQuery = Object.keys(params)
    .sort()
    .map((k) => `${uriEncode(k)}=${uriEncode(params[k])}`)
    .join('&')

  const canonicalHeaders = `host:${host}\n`
  const canonicalRequest = [
    opts.method,
    canonicalUri,
    canonicalQuery,
    canonicalHeaders,
    'host',
    'UNSIGNED-PAYLOAD',
  ].join('\n')

  const stringToSign = [AWS_ALGORITHM, amz, scope, sha256Hex(canonicalRequest)].join('\n')

  const kDate = hmac(`AWS4${cfg.secretAccessKey}`, date)
  const kRegion = hmac(kDate, cfg.region)
  const kService = hmac(kRegion, SERVICE)
  const kSigning = hmac(kService, 'aws4_request')
  const signature = crypto.createHmac('sha256', kSigning).update(stringToSign).digest('hex')

  return `${protocol}://${host}${canonicalUri}?${canonicalQuery}&X-Amz-Signature=${signature}`
}
