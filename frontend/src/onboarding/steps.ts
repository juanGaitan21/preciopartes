import type { Rol } from '../types'

export type OnboardingStepId =
  | 'welcome'
  | 'comparador'
  | 'cargar_listas'
  | 'usuarios'
  | 'done'

export interface OnboardingStep {
  id: OnboardingStepId
  title: string
  description: string
  hint?: string
  route?: string
  cta?: string
  roles: Rol[]
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Bienvenido a PrecioPartes',
    description:
      'Esta aplicacion compara precios de repuestos entre varios proveedores. ' +
      'Te mostramos en pocos pasos como empezar.',
    cta: 'Comenzar',
    roles: ['admin', 'vendedor', 'consulta'],
  },
  {
    id: 'comparador',
    title: 'Comparar precios',
    description:
      'En el Comparador buscas por referencia, descripcion, marca o vehiculo. ' +
      'El repuesto mas barato se resalta en verde.',
    hint: 'Prueba buscar algo como "filtro", "hyundai" o una referencia.',
    route: '/comparador',
    cta: 'Ir al Comparador',
    roles: ['admin', 'vendedor', 'consulta'],
  },
  {
    id: 'cargar_listas',
    title: 'Subir listas de precios',
    description:
      'Cada quincena subes los Excel de tus proveedores. El sistema detecta el formato, ' +
      'normaliza los datos y los deja listos para comparar.',
    hint: 'Puedes subir 16 o mas archivos a la vez. La carga corre en segundo plano.',
    route: '/admin?tab=cargar',
    cta: 'Ir a Cargar listas',
    roles: ['admin'],
  },
  {
    id: 'usuarios',
    title: 'Invitar a tu equipo',
    description:
      'Crea usuarios para vendedores (buscan y comparan) o consulta (solo lectura). ' +
      'Tu como admin puedes subir listas y gestionar todo.',
    route: '/admin?tab=usuarios',
    cta: 'Ir a Usuarios',
    roles: ['admin'],
  },
  {
    id: 'done',
    title: 'Listo para usar',
    description:
      'Ya conoces lo esencial. Si necesitas repasar, abre esta guia desde el menu lateral.',
    cta: 'Empezar',
    roles: ['admin', 'vendedor', 'consulta'],
  },
]

export function stepsForRole(rol: Rol): OnboardingStep[] {
  return ONBOARDING_STEPS.filter((s) => s.roles.includes(rol))
}
