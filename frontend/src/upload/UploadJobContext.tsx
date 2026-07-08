import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type { BatchUploadResponse, UploadJobStatus } from '../types'
import { ACTIVE_JOB_KEY, JOB_POLL_MS } from './constants'

export type UploadPhase = 'idle' | 'sending' | 'processing' | 'done'

interface UploadJobContextValue {
  phase: UploadPhase
  jobStatus: UploadJobStatus | null
  activeJobId: string | null
  sendingProgress: { current: number; total: number; fileName: string } | null
  lastResult: BatchUploadResponse | null
  isActive: boolean
  uploadFiles: (files: File[]) => Promise<void>
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

  const pollJob = useCallback(async (jobId: string) => {
    const status = await api.getUploadJobStatus(jobId)
    setJobStatus(status)

    if (status.estado === 'completed') {
      setLastResult(jobToResult(status))
      setPhase('done')
      setSendingProgress(null)
      localStorage.removeItem(ACTIVE_JOB_KEY)
      return true
    }

    setPhase('processing')
    return false
  }, [])

  const startPolling = useCallback(
    (jobId: string) => {
      setActiveJobId(jobId)
      localStorage.setItem(ACTIVE_JOB_KEY, jobId)

      void (async () => {
        try {
          const done = await pollJob(jobId)
          if (done) return

          const interval = window.setInterval(async () => {
            try {
              const finished = await pollJob(jobId)
              if (finished) window.clearInterval(interval)
            } catch {
              window.clearInterval(interval)
            }
          }, JOB_POLL_MS)
        } catch {
          setPhase('idle')
          setSendingProgress(null)
        }
      })()
    },
    [pollJob],
  )

  useEffect(() => {
    const savedJobId = localStorage.getItem(ACTIVE_JOB_KEY)
    if (!savedJobId) return
    setPhase('processing')
    startPolling(savedJobId)
  }, [startPolling])

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return

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
        setPhase('idle')
        setSendingProgress(null)
        setActiveJobId(null)
        localStorage.removeItem(ACTIVE_JOB_KEY)
        throw err
      }
    },
    [startPolling],
  )

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
