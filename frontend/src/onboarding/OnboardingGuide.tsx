import { useAuth } from '../auth/AuthContext'
import { stepsForRole } from './steps'
import { useOnboarding } from './OnboardingContext'

export function OnboardingGuide() {
  const { user } = useAuth()
  const {
    open,
    stepIndex,
    totalSteps,
    isFirstStep,
    isLastStep,
    closeGuide,
    skipGuide,
    nextStep,
    prevStep,
    goToStepAction,
    isStepDone,
  } = useOnboarding()

  if (!user || !open) return null

  const steps = stepsForRole(user.rol)
  const step = steps[stepIndex]
  if (!step) return null

  const isWelcome = step.id === 'welcome'
  const hasRoute = Boolean(step.route)
  const done = isStepDone(step.id)

  return (
    <div
      className={
        isWelcome
          ? 'fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4'
          : 'fixed bottom-4 right-4 z-[60] w-full max-w-sm p-4 sm:p-0'
      }
      role="dialog"
      aria-labelledby="onboarding-title"
      aria-describedby="onboarding-desc"
    >
      <div
        className={`rounded-xl border border-primary/30 bg-surface shadow-2xl ${
          isWelcome ? 'w-full max-w-md p-6' : 'p-5'
        }`}
      >
        <div className="mb-1 flex items-center justify-between gap-3">
          <p className="text-xs font-medium uppercase tracking-wide text-primary">
            Guia rapida · Paso {stepIndex + 1} de {totalSteps}
          </p>
          <button
            type="button"
            onClick={closeGuide}
            className="rounded p-1 text-muted hover:bg-surface-hover hover:text-text"
            aria-label="Minimizar guia"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mb-4 flex gap-1">
          {steps.map((s, i) => (
            <div
              key={s.id}
              className={`h-1.5 flex-1 rounded-full ${
                i < stepIndex || isStepDone(s.id)
                  ? 'bg-accent'
                  : i === stepIndex
                    ? 'bg-primary'
                    : 'bg-border'
              }`}
            />
          ))}
        </div>

        <h2 id="onboarding-title" className="text-lg font-semibold text-text">
          {step.title}
        </h2>
        <p id="onboarding-desc" className="mt-2 text-sm leading-relaxed text-muted">
          {step.description}
        </p>

        {step.hint && (
          <p className="mt-3 rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text">
            {step.hint}
          </p>
        )}

        {done && step.id !== 'welcome' && step.id !== 'done' && (
          <p className="mt-3 text-sm font-medium text-accent">Paso completado</p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {!isFirstStep && (
            <button
              type="button"
              onClick={prevStep}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface-hover"
            >
              Anterior
            </button>
          )}

          {hasRoute ? (
            <button
              type="button"
              onClick={goToStepAction}
              className="rounded-lg bg-accent-dim px-4 py-2 text-sm font-semibold text-white hover:bg-accent"
            >
              {step.cta ?? 'Ir'}
            </button>
          ) : (
            <button
              type="button"
              onClick={nextStep}
              className="rounded-lg bg-accent-dim px-4 py-2 text-sm font-semibold text-white hover:bg-accent"
            >
              {step.cta ?? (isLastStep ? 'Empezar' : 'Siguiente')}
            </button>
          )}

          {!isLastStep && hasRoute && (
            <button
              type="button"
              onClick={nextStep}
              className="rounded-lg px-3 py-2 text-sm text-muted hover:text-text"
            >
              Saltar paso
            </button>
          )}

          <button
            type="button"
            onClick={skipGuide}
            className="ml-auto rounded-lg px-3 py-2 text-sm text-muted hover:text-text"
          >
            Omitir guia
          </button>
        </div>
      </div>
    </div>
  )
}
