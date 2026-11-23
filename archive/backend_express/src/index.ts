import dotenv from 'dotenv'
import { createApp } from './app.js'

dotenv.config()

const port = Number(process.env.PORT ?? process.env.BACKEND_EXPRESS_PORT ?? 3001)
const app = createApp()

app.listen(port, () => {
})
