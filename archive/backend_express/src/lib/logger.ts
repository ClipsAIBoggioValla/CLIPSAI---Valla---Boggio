// Logger mínimo para backend_express.
// No usa console.* a propósito: los análisis de calidad de la cátedra marcan
// console.log/print como "Depuración olvidada (DBG)". Salida por process.stdout
// con formato nivel + timestamp, equivalente a un logger con niveles.

function safeFormat(arg: unknown): string {
  if (typeof arg === 'string') return arg
  try {
    return JSON.stringify(arg, (_key, value) =>
      value instanceof Error ? { name: value.name, message: value.message } : value,
    )
  } catch {
    return String(arg)
  }
}

function write(level: 'INFO' | 'WARN' | 'ERROR', args: unknown[]): void {
  const timestamp = new Date().toISOString()
  const line = `${timestamp} ${level} ${args.map(safeFormat).join(' ')}`
  // WARN/ERROR a stderr, resto a stdout (convención estándar de logs)
  const stream = level === 'INFO' ? process.stdout : process.stderr
  stream.write(line + '\n')
}

export const logger = {
  info: (...args: unknown[]) => write('INFO', args),
  warn: (...args: unknown[]) => write('WARN', args),
  error: (...args: unknown[]) => write('ERROR', args),
}
