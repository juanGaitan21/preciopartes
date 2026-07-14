import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type { BatchUploadResponse, UploadJobStatus } from '../types'
import { ACTIVE_JOB_KEY, JOB_POLL_MS, STALE_POLL_LIMIT } from './constants'

export type UploadPhase = 'idle' | 'sending' | 'processing' | 'done'

interface UploadJobContextValue {
  phase: UploadPhase
  jobStatus: UploadJobStatus | null
  activeJobId: string | null
  sendingProgress: { current: number; total: number; fileName: string } | null
  lastResult: BatchUploadResponse | null
  isActive: boolean
  uploadFiles: (files: File[]) => Promise<void>
  cancelJob: () => Promise<void>
  resetUpload: () => Promise<void>
  clearResult: () => void
  dismissJob: () => void
}

const UploadJobContext = createContext<UploadJobContextValue | null>(null)

function jobToResult(job: UploadJobStatus): BatchUploadResponse {
  return {
    ok: job.ok,
    archivos_ok: job.archivos_completados,
    archivos_error: job.archivos_error,
    total_registros: job.total_registros,
    resultados: job.resultados,
    errores: job.errores,
    mensaje: job.mensaje,
  }
}

function pollErrorResult(message: string): BatchUploadResponse {
  return {
    ok: false,
    archivos_ok: 0,
    archivos_error: 1,
    total_registros: 0,
    resultados: [],
    errores: [{ archivo: '(sistema)', mensaje: message, codigo: 'POLL_ERROR' }],
    mensaje: message,
  }
}

export function UploadJobProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<UploadPhase>('idle')
  const [jobStatus, setJobStatus] = useState<UploadJobStatus | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [sendingProgress, setSendingProgress] = useState<{
    current: number
    total: number
    fileName: string
  } | null>(null)
  const [lastResult, setLastResult] = useState<BatchUploadResponse | null>(null)

  const pollIntervalRef = useRef<number | null>(null)
  const stalePollsRef = useRef(0)
  const lastProgressRef = useRef('')

  const clearPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    stalePollsRef.current = 0
    lastProgressRef.current = ''
  }, [])

  const resetActiveJob = useCallback(() => {
    clearPolling()
    localStorage.removeItem(ACTIVE_JOB_KEY)
    setPhase('idle')
    setJobStatus(null)
    setActiveJobId(null)
    setSendingProgress(null)
  }, [clearPolling])

  const finishWithResult = useCallback(
    (result: BatchUploadResponse) => {
      clearPolling()
      localStorage.removeItem(ACTIVE_JOB_KEY)
      setSendingProgress(null)
      setJobStatus(null)
      setActiveJobId(null)
      setLastResult(result)
      setPhase('done')
    },
    [clearPolling],
  )

  const pollJob = useCallback(
    async (jobId: string) => {
      const status = await api.getUploadJobStatus(jobId)
      setJobStatus(status)

      if (status.estado === 'completed' || status.estado === 'failed') {
        if (status.estado === 'completed' && status.mensaje.includes('Cancelado')) {
          resetActiveJob()
          return true
        }
        finishWithResult(jobToResult(status))
        return true
      }

      // Si hay un archivo procesandose, el servidor sigue trabajando
      // (un Excel grande puede tardar 10-20 min en leer/guardar).
      // Solo detectar atasco si no hay actividad real.
      const processingFile = status.archivos.find((a) => a.estado === 'processing')
      if (processingFile || status.archivos_procesando > 0) {
        stalePollsRef.current = 0
        lastProgressRef.current = `${status.progreso_pct}|${status.mensaje}|${processingFile?.fase_detalle ?? ''}`
        setPhase('processing')
        return false
      }

      const progressKey = [
        status.progreso_pct,
        status.archivos_completados,
        status.archivos_error,
        status.mensaje,
        status.estado,
      ].join('|')

      if (progressKey === lastProgressRef.current) {
        stalePollsRef.current += 1
      } else {
        stalePollsRef.current = 0
        lastProgressRef.current = progressKey
      }

      if (stalePollsRef.current >= STALE_POLL_LIMIT) {
        finishWithResult(
          pollErrorResult(
            'La carga lleva mucho tiempo sin avances. Usa "Liberar formulario" y vuelve a intentar; con archivos muy grandes sube de a uno.',
          ),
        )
        return true
      }

      setPhase('processing')
      return false
    },
    [finishWithResult, resetActiveJob],
  )

  const startPolling = useCallback(
    (jobId: string) => {
      setActiveJobId(jobId)
      localStorage.setItem(ACTIVE_JOB_KEY, jobId)
      clearPolling()

      void (async () => {
        try {
          const done = await pollJob(jobId)
          if (done) return

          pollIntervalRef.current = window.setInterval(async () => {
            try {
              const finished = await pollJob(jobId)
              if (finished) clearPolling()
            } catch (err) {
              clearPolling()
              const msg =
                err instanceof Error ? err.message : 'Error consultando el progreso de la carga'
              finishWithResult(pollErrorResult(msg))
            }
          }, JOB_POLL_MS)
        } catch (err) {
          clearPolling()
          const msg =
            err instanceof Error ? err.message : 'Error consultando el progreso de la carga'
          finishWithResult(pollErrorResult(msg))
        }
      })()
    },
    [clearPolling, finishWithResult, pollJob],
  )

  useEffect(() => {
    const savedJobId = localStorage.getItem(ACTIVE_JOB_KEY)
    if (!savedJobId) return

    let cancelled = false

    void (async () => {
      try {
        const status = await api.getUploadJobStatus(savedJobId)
        if (cancelled) return

        if (status.estado === 'completed' || status.estado === 'failed') {
          localStorage.removeItem(ACTIVE_JOB_KEY)
          if (
            status.estado === 'failed' ||
            (status.estado === 'completed' && !status.mensaje.includes('Cancelado'))
          ) {
            setLastResult(jobToResult(status))
            setPhase('done')
          }
          return
        }

        setJobStatus(status)
        startPolling(savedJobId)
      } catch {
        if (cancelled) return
        resetActiveJob()
      }
    })()

    return () => {
      cancelled = true
    }
    // Solo al montar: recuperar job guardado sin bloquear la UI si falla.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return

      if (phase === 'sending' || phase === 'processing') {
        const jobId = activeJobId || localStorage.getItem(ACTIVE_JOB_KEY)
        if (jobId) {
          try {
            await api.cancelUploadJob(jobId)
          } catch {
            // Si falla cancelar en servidor, igual limpiamos la UI local
          }
        }
        resetActiveJob()
      }

      setPhase('sending')
      setLastResult(null)
      setJobStatus(null)
      setSendingProgress({ current: 0, total: files.length, fileName: files[0].name })

      try {
        const job = await api.createUploadJob()
        setActiveJobId(job.job_id)
        localStorage.setItem(ACTIVE_JOB_KEY, job.job_id)

        for (let i = 0; i < files.length; i++) {
          const file = files[i]
          setSendingProgress({ current: i + 1, total: files.length, fileName: file.name })
          await api.addFileToUploadJob(job.job_id, file)
        }

        setSendingProgress(null)
        await api.startUploadJob(job.job_id)
        startPolling(job.job_id)
      } catch (err) {
        resetActiveJob()
        const msg = err instanceof Error ? err.message : 'Error al subir archivos'
        if (msg === 'Failed to fetch') {
          throw new Error(
            'No se pudo conectar con el servidor. Verifica tu conexion o intenta con menos archivos a la vez.',
          )
        }
        if (msg.includes('Sesión') || msg.includes('Token') || msg.includes('autorizado')) {
          throw new Error('Sesion expirada. Cierra sesion y vuelve a entrar.')
        }
        throw err
      }
    },
    [activeJobId, phase, resetActiveJob, startPolling],
  )

  const cancelJob = useCallback(async () => {
    const jobId = activeJobId || localStorage.getItem(ACTIVE_JOB_KEY)
    if (jobId) {
      try {
        await api.cancelUploadJob(jobId)
      } catch {
        // Si la API no responde, igual liberamos la UI
      }
    }
    resetActiveJob()
    setLastResult(null)
  }, [activeJobId, resetActiveJob])

  const resetUpload = cancelJob

  const clearResult = useCallback(() => {
    setLastResult(null)
    if (phase === 'done') {
      setPhase('idle')
      setJobStatus(null)
      setActiveJobId(null)
    }
  }, [phase])

  const dismissJob = useCallback(() => {
    if (phase === 'processing' || phase === 'sending') return
    setPhase('idle')
    setJobStatus(null)
    setActiveJobId(null)
    setLastResult(null)
    setSendingProgress(null)
  }, [phase])

  const value = useMemo<UploadJobContextValue>(
    () => ({
      phase,
      jobStatus,
      activeJobId,
      sendingProgress,
      lastResult,
      isActive: phase === 'sending' || phase === 'processing',
      uploadFiles,
      cancelJob,
      resetUpload,
      clearResult,
      dismissJob,
    }),
    [
      phase,
      jobStatus,
      activeJobId,
      sendingProgress,
      lastResult,
      uploadFiles,
      cancelJob,
      resetUpload,
      clearResult,
      dismissJob,
    ],
  )

  return <UploadJobContext.Provider value={value}>{children}</UploadJobContext.Provider>
}

export function useUploadJob() {
  const ctx = useContext(UploadJobContext)
  if (!ctx) throw new Error('useUploadJob debe usarse dentro de UploadJobProvider')
  return ctx
}
