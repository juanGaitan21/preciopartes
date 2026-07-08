import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { stepsForRole, type OnboardingStepId } from './steps'

const STORAGE_PREFIX = 'pp_onboarding_'

interface StoredOnboarding {
  completed: boolean
  skipped: boolean
  currentStep: number
  doneSteps: OnboardingStepId[]
}

interface OnboardingContextValue {
  open: boolean
  stepIndex: number
  totalSteps: number
  currentStepId: OnboardingStepId | null
  doneSteps: OnboardingStepId[]
  isFirstStep: boolean
  isLastStep: boolean
  openGuide: () => void
  closeGuide: () => void
  skipGuide: () => void
  nextStep: () => void
  prevStep: () => void
  goToStepAction: () => void
  markStepDone: (id: OnboardingStepId) => void
  isStepDone: (id: OnboardingStepId) => boolean
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null)

function defaultState(): StoredOnboarding {
  return { completed: false, skipped: false, currentStep: 0, doneSteps: [] }
}

function loadState(userId: number): StoredOnboarding {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${userId}`)
    if (!raw) return defaultState()
    return { ...defaultState(), ...JSON.parse(raw) }
  } catch {
    return defaultState()
  }
}

function saveState(userId: number, state: StoredOnboarding) {
  localStorage.setItem(`${STORAGE_PREFIX}${userId}`, JSON.stringify(state))
}

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const steps = useMemo(() => (user ? stepsForRole(user.rol) : []), [user])
  const [open, setOpen] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [doneSteps, setDoneSteps] = useState<OnboardingStepId[]>([])

  useEffect(() => {
    if (!user) {
      setOpen(false)
      return
    }
    const stored = loadState(user.id)
    setStepIndex(Math.min(stored.currentStep, stepsForRole(user.rol).length - 1))
    setDoneSteps(stored.doneSteps)
    if (!stored.completed && !stored.skipped) {
      setOpen(true)
    }
  }, [user])

  const persist = useCallback(
    (patch: Partial<StoredOnboarding>) => {
      if (!user) return
      const next = { ...loadState(user.id), ...patch }
      saveState(user.id, next)
    },
    [user],
  )

  const markStepDone = useCallback(
    (id: OnboardingStepId) => {
      if (!user) return
      setDoneSteps((prev) => {
        if (prev.includes(id)) return prev
        const next = [...prev, id]
        persist({ doneSteps: next })
        return next
      })
    },
    [persist, user],
  )

  const finishGuide = useCallback(() => {
    if (!user) return
    persist({ completed: true, currentStep: 0 })
    setOpen(false)
  }, [persist, user])

  const skipGuide = useCallback(() => {
    if (!user) return
    persist({ skipped: true, completed: true })
    setOpen(false)
  }, [persist, user])

  const openGuide = useCallback(() => {
    if (!user) return
    const stored = loadState(user.id)
    setStepIndex(stored.currentStep || 0)
    setOpen(true)
  }, [user])

  const closeGuide = useCallback(() => {
    if (!user) return
    persist({ currentStep: stepIndex })
    setOpen(false)
  }, [persist, stepIndex, user])

  const nextStep = useCallback(() => {
    const step = steps[stepIndex]
    if (step) markStepDone(step.id)

    if (stepIndex >= steps.length - 1) {
      finishGuide()
      return
    }
    const next = stepIndex + 1
    setStepIndex(next)
    persist({ currentStep: next })
  }, [finishGuide, markStepDone, persist, stepIndex, steps])

  const prevStep = useCallback(() => {
    const prev = Math.max(0, stepIndex - 1)
    setStepIndex(prev)
    persist({ currentStep: prev })
  }, [persist, stepIndex])

  const goToStepAction = useCallback(() => {
    const step = steps[stepIndex]
    if (!step?.route) {
      nextStep()
      return
    }
    markStepDone(step.id)
    navigate(step.route)
    if (stepIndex < steps.length - 1) {
      const next = stepIndex + 1
      setStepIndex(next)
      persist({ currentStep: next })
    }
  }, [markStepDone, navigate, nextStep, persist, stepIndex, steps])

  const isStepDone = useCallback(
    (id: OnboardingStepId) => doneSteps.includes(id),
    [doneSteps],
  )

  useEffect(() => {
    if (!user || !open) return
    if (location.pathname.startsWith('/comparador')) markStepDone('comparador')
    if (location.pathname.startsWith('/admin')) {
      const tab = new URLSearchParams(location.search).get('tab')
      if (tab === 'cargar') markStepDone('cargar_listas')
      if (tab === 'usuarios') markStepDone('usuarios')
    }
  }, [location.pathname, location.search, markStepDone, open, user])

  const value = useMemo<OnboardingContextValue>(
    () => ({
      open,
      stepIndex,
      totalSteps: steps.length,
      currentStepId: steps[stepIndex]?.id ?? null,
      doneSteps,
      isFirstStep: stepIndex === 0,
      isLastStep: stepIndex === steps.length - 1,
      openGuide,
      closeGuide,
      skipGuide,
      nextStep,
      prevStep,
      goToStepAction,
      markStepDone,
      isStepDone,
    }),
    [
      open,
      stepIndex,
      steps,
      doneSteps,
      openGuide,
      closeGuide,
      skipGuide,
      nextStep,
      prevStep,
      goToStepAction,
      markStepDone,
      isStepDone,
    ],
  )

  return (
    <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>
  )
}

export function useOnboarding() {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding debe usarse dentro de OnboardingProvider')
  return ctx
}
