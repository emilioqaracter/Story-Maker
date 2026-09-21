// Las tipografias son parte de la arquitectura, no del adorno: serif
// editorial para lo que escribio un agente, monoespaciada para lo que midio la
// maquina. Van empaquetadas y no desde una CDN, porque el dia de la grabacion
// el tablero tiene que arrancar sin red.

import '@fontsource/literata/400.css'
import '@fontsource/literata/600.css'
import '@fontsource/literata/400-italic.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@xyflow/react/dist/style.css'
import './diseno/tokens.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App.tsx'

const raiz = document.getElementById('raiz')
if (!raiz) throw new Error('falta #raiz en index.html')

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
