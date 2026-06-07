# 🎮 Convertidor de Partidas GTA San Andreas (Android → PC)

Herramienta para convertir archivos de guardado `.b` de GTA San Andreas desde dispositivos Android a la versión de PC Windows (Clásica v1.0).

---

## 📌 Propósito del Proyecto y Colaboración

*   **Objetivo:** Este proyecto nace con la meta de lograr un convertidor de partidas de Android a PC 100% funcional. 
*   **Para Fans:** Es un proyecto sin fines de lucro, desarrollado por fans y para fans, con el único propósito de permitir a los jugadores convertir sus archivos de guardado de Android y continuar su progreso de forma fluida en la PC.
*   **No es para Mods:** No está diseñado ni tiene la intención de servir para realizar modificaciones (mods) en el juego.
*   **Investigación y Avances:** Toda la documentación técnica, estructura de bloques y mapeo de variables presentados aquí son el resultado directo de mis investigaciones y descubrimientos hasta el momento.
*   **¡Colabora!** El proyecto está abierto a contribuciones y mejoras para resolver los detalles de compatibilidad restantes. Estaré muy atento a colaboraciones en GitHub.

### 📬 Contacto
*   **Autor:** Richard Subero
*   **GitHub:** [richarsbv](https://github.com/richarsbv)
*   **Correo electrónico:** richardsub13@gmail.com

---

## 📋 Manual de Uso

### Paso 1: Localizar la partida de Android
En tu dispositivo Android, accede a la siguiente ruta utilizando un gestor de archivos:
```
/Android/data/com.rockstargames.gtasa/files/
```
Copia el archivo `GTASAsf#.b` (donde `#` es el número de la ranura de guardado) a tu PC.

> [!NOTE]
> Los archivos adicionales como `CINFO.BIN`, `gta_sa.set` y `gtasatelem.set` no contienen progreso del jugador y no deben ser convertidos.

### Paso 2: Conseguir una plantilla de PC adecuada
El convertidor requiere una **plantilla de PC válida** (un save `.b` de PC en la misma versión) para transferir los datos sin corromper el motor de juego.

*   **Para partidas a mitad de la historia:** Usa como plantilla un archivo de PC que esté guardado **en la misma misión o punto de la historia**, preferiblemente en **modo libre** (guardado dentro de un piso franco). Esto garantiza que los hilos de script activos (threads) estén limpios y no bloqueen misiones ni disquetes de guardado.
*   **Para partidas al 100% completado:** Puedes usar cualquier partida de PC al 100% como plantilla base.

### Paso 3: Ejecutar el convertidor

El script requiere tener **Node.js** instalado (o Python si prefieres el script alternativo).

#### Ejemplo Simple (Conversión Básica)
```bash
node gta_sa_android_to_pc_converter.js --android "GTASAsf_android.b" --template "GTASAsf_pc_plantilla.b" --output "GTASAsf_convertido.b"
```

#### Ejemplo Avanzado (Con reemplazo de hilos de script)
Si tu plantilla de PC fue guardada durante una misión y deseas limpiarla para forzar el modo libre (evitando el bloqueo del reloj, propiedades o guardados):
```bash
node gta_sa_android_to_pc_converter.js --android "GTASAsf_android.b" --template "GTASAsf_pc_plantilla.b" --output "GTASAsf_convertido.b" --threads-from "save_pc_100_libre.b"
```

**Opciones disponibles:**
| Parámetro | Descripción |
|---|---|
| `--android` | Ruta al archivo de guardado `.b` de Android. |
| `--template` | Ruta a un save de PC clásico v1.0 que servirá como plantilla de estructura. |
| `--output` | Nombre y ruta del archivo final convertido para PC. |
| `--keep-properties` | Conserva los datos de propiedades y compras (Bloque 22) de la plantilla de PC. |
| `--threads-from` | Copia la sección de hilos activos de un save de PC en modo libre (ej. un save 100% completado). Útil para destrabar el estado de misión activa. |

### Paso 4: Instalar en la PC
Copia el archivo `.b` convertido en la carpeta de documentos de GTA San Andreas en tu PC:
```
%USERPROFILE%\Documents\GTA San Andreas User Files\
```

---

## 🔬 Documentación Técnica y Descubrimientos

### Descubrimiento: Tabla de Variables en main.scm
Durante mis investigaciones analizando el script compilado del juego (`main.scm`), descubrí que la versión de Android contiene una tabla de depuración con los índices originales de las variables globales. Al compararlos con el `main.scm` de PC clásico, se determinó que:
*   Los índices de las variables de progreso coinciden exactamente entre Android y PC.
*   Esto permite transferir variables de progreso específicas (como misiones secundarias y compras) de forma quirúrgica sin romper el resto de la memoria de guardado.

### Mapeo de Bloques en la Conversión

| Bloque | Contenido | Acción del Convertidor |
|---|---|---|
| **Bloque 0** | Metadatos (Nombre de partida, fecha, clima, posición de spawn) | Copiado y ajustado. Si la posición de spawn es un interior propenso a errores en PC, se reubica al jugador en el exterior. |
| **Bloque 1** | Script Globals y Threads | **Fusión Selectiva:** Se copian estadísticas de propiedades completadas y se resetean punteros inválidos de Android. |
| **Bloque 2** | Datos del jugador (salud, armadura, armas, ropa, estadísticas físicas) | Copiado con ajuste de desfase de bytes. |
| **Bloque 3** | Garajes y vehículos guardados | Copia directa. |
| **Bloque 9** | Blips del radar | Copia de los blips activos. |
| **Bloque 15/30** | Dinero del jugador | Copia directa (duplicada en el bloque 30 en PC). |
| **Bloque 16/31** | Estadísticas | Copia directa (duplicada en el bloque 31 en PC). |
| **Bloque 18** | Zonas de Mapa / IPLs (Controla puentes y barreras abiertas) | Copia directa para mantener el progreso del mapa desbloqueado. |
| **Bloque 22** | Shopping (Propiedades compradas y ropa de clóset) | Copia dinámica adaptativa. |

### Punteros y Flags Críticos Corregidos
El convertidor ajusta automáticamente variables que en Android poseen valores incompatibles con PC:
*   **`$728 (PROPERTY_BOUGHT_FLAGS)`:** En Android se inicializa en `-1` (todos los bits activados), lo que en PC bloquea la compra de cualquier propiedad nueva. Se fuerza a `0` para que el script de PC controle la compra con `TAB`.
*   **`$409 (ONMISSION)`:** Se fuerza a `0` al limpiar hilos para permitir el guardado (evitando que los disquetes desaparezcan).
*   **`$865–$882 (SAVE_PICKUPS)`:** Se limpian los punteros de los disquetes para que el motor de PC los regenere dinámicamente frente a las safehouses.

---

## 📊 Diferencias de Estructura: Android vs PC (Clásico y Remasterizado)

A través de análisis binario en mis investigaciones, he documentado cómo varía la estructura del archivo de guardado:

| Campo | Android Remastered | PC Clásico (v1.0) | PC Remastered (Steam/MS Store) |
|---|---|---|---|
| **Tamaño total del save** | ~195,000 bytes | **202,752 bytes** | **260,000 bytes** |
| **Bloques totales** | 31 (0 a 30) | 34 (0 a 33) | 28 (0 a 27) |
| **Marcadores de Integridad (`0xC0DE`)** | No utiliza | No utiliza | **Sí (después de cada elemento)** |
| **Tamaño Hilo de Script (B1)** | 20 bytes | 128 / 136 bytes | 22 bytes (20 + 2 de `0xC0DE`) |
| **Tamaño Variable Global (B1)** | 4 bytes | 4 bytes | 6 bytes (4 + 2 de `0xC0DE`) |
| **Código de Script (B1)** | 49,212 bytes | 43,808 bytes | 49,212 bytes |
| **Tamaño Bloque 18 (Mapa/IPLs)** | 26,316 bytes | 78,948 bytes | 78,948 bytes (26,316 + 52,632 de `0xC0DE`) |
| **Nombre del save** | UTF-16LE (200 bytes) | ASCII (100 bytes) | UTF-16LE (200 bytes) |

### 🔬 El Marcador de Verificación `0xC0DE`
Descubrí que en la versión **PC Remastered (Steam v3 / Windows Store / Rockstar Launcher)**, el motor inyecta un código de 2 bytes (`0xDE 0xC0` en hexadecimal o `0xC0DE` en formato Little Endian) al final de cada variable global, hilo de script y elementos en bloques de mapa (B18, B21, etc.). Esto incrementa de forma predecible el tamaño de los bloques (por ejemplo, el Bloque 18 es exactamente **3 veces más grande** en PC Remastered que en Android por esta razón). 

---

## 📁 Archivos de Prueba Incluidos

Para facilitar las pruebas de conversión e investigación, se han dejado los siguientes recursos en este repositorio:
*   **`files/`**: Carpeta que contiene partidas de guardado reales de Android en formato original `.b` para realizar pruebas de conversión directa.
*   **`GTASAsf1-windows.b`**: Archivo de guardado de PC Clásica (v1.0) con el **100% del juego completado**. Se incluye para usarse como plantilla de pruebas o para extraer/inyectar sus hilos libres (free-roam) usando la opción `--threads-from`.

---

## ⚠️ Limitaciones Actuales
1.  **Iconos de guardado y misiones tras conversión:** Si la plantilla de PC utilizada contiene hilos de scripts bloqueados o terminados, es posible que no se generen los disquetes de guardado o no aparezcan nuevas misiones. Esto se soluciona encontrando una plantilla de PC en modo libre en el mismo punto de la historia.
2.  **Misiones activas:** El convertidor no transfiere misiones que estén activadas a mitad de ejecución; se debe guardar la partida en un piso franco antes de transferir el save.

