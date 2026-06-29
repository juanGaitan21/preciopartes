# PrecioPartes 🔧

Comparador de precios de repuestos automotrices.  
Normaliza listas de múltiples proveedores y permite búsqueda unificada.

---

## Estructura del proyecto

```
preciopartes/
├── etl/
│   ├── etl.py          ← ETL: parsea y normaliza cualquier Excel de proveedor
│   └── test_etl.py     ← Script para probar el ETL con archivos reales
├── api/
│   ├── main.py         ← API FastAPI (endpoints de búsqueda y carga)
│   └── schema.sql      ← Schema PostgreSQL (tablas, índices, vista comparador)
├── Dockerfile
├── docker-compose.yml  ← Dev local con PostgreSQL incluido
└── requirements.txt
```

---

## Levantar en desarrollo local

```bash
# 1. Clonar y entrar al proyecto
git clone <tu-repo> && cd preciopartes

# 2. Levantar API + PostgreSQL con Docker
docker-compose up --build

# La API queda en http://localhost:8000
# Docs automáticos en http://localhost:8000/docs
```

---

## Desplegar en tu servidor (Deploy + Docker)

### Variables de entorno requeridas

```env
DATABASE_URL=postgresql://usuario:password@host:5432/preciopartes
```

### Pasos en Deploy

1. Conecta tu repositorio en Deploy
2. Selecciona **Docker** como runtime
3. Agrega la variable `DATABASE_URL` apuntando a tu PostgreSQL
4. Deploy detecta el `Dockerfile` y construye automáticamente

---

## Cargar una lista nueva (cada 15 días)

### Opción A — Desde la app (frontend)
El frontend tiene un botón "Cargar nueva lista" que sube el Excel directamente.

### Opción B — curl / Postman
```bash
curl -X POST https://tu-dominio.com/api/listas/upload \
  -F "archivo=@DH_4350_COREA_JULIO_2026.xls" \
  -F "proveedor_id=1" \
  -F "subido_por=admin"
```

### Opción C — Script automático
```bash
# Puedes programar esto con cron cada vez que llegue un nuevo Excel
python etl/cargar_lista.py --archivo "nueva_lista.xls" --proveedor 1
```

**¿Qué pasa cuando subes una lista nueva?**
1. El ETL detecta automáticamente el formato del proveedor
2. Normaliza todos los precios, referencias y descripciones
3. La lista anterior del proveedor queda **desactivada** (los datos históricos no se borran)
4. Los nuevos precios quedan activos de inmediato

---

## Proveedores soportados (auto-detectados)

| Tipo | Formato | Ejemplo de archivo |
|------|---------|-------------------|
| `DH` | 1 hoja, cols: VEHICULO, REFERENCIA, PRECIO | `DH_4350_COREA_JUNIO_2026.xls` |
| `CAJAS` | Multi-hoja por marca, precio con `$` | `Lista_CAJAS_DE_DIRECCION_26_junio.xls` |
| `LISTA_E` | 2 hojas, filas categoría mezcladas | `ListaPrecioE20260619.xlsx` |

**Para agregar un proveedor nuevo:** el ETL auto-detecta el formato. Si el formato es completamente diferente, se agrega un nuevo parser en `etl/etl.py` (función `_parse_nuevo_proveedor`).

---

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/buscar?q=filtro kia` | Busca repuestos, retorna precios ordenados |
| `POST` | `/api/listas/upload` | Sube nuevo Excel de lista de precios |
| `GET` | `/api/proveedores` | Lista los proveedores activos |
| `GET` | `/api/listas` | Historial de listas subidas |
| `DELETE` | `/api/listas/{id}` | Desactiva una lista |
| `GET` | `/docs` | Documentación Swagger interactiva |

---

## Probar el ETL localmente

```bash
# Poner los Excel en la carpeta listas/
mkdir listas
cp *.xls *.xlsx listas/

# Correr el test
python etl/test_etl.py
```

---

## Base de datos: tablas principales

```
proveedores  — Quién vende (DH, Cajas Dir, etc.)
listas       — Cada Excel subido = una lista
partes       — Los repuestos normalizados (referencia, descripción, precio)
v_comparador — Vista con ranking de precios por referencia
```
