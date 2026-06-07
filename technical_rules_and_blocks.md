# 📘 Reglas Técnicas de Conversión y Análisis de Bloques (GTA SA)

Este documento detalla las reglas de compatibilidad de datos, la estructura de los bloques del archivo de guardado (`.b`), por qué ciertos bloques no se copian, y cómo solucionar los problemas de **iconos de guardado** y de **misiones faltantes**.

---

## 1. Reglas Generales de Conversión (Android → PC)
1. **Firma de Bloques ("BLOCK"):** Cada sección de datos en el archivo de guardado está delimitada por la palabra `"BLOCK"`. El tamaño físico de los bloques debe respetarse para evitar desbordar y corromper las firmas de los bloques siguientes.
2. **Ajuste de Offsets por UTF-16 (Bloque 0):** En Android, el nombre de la partida se guarda en UTF-16 (200 bytes), mientras que en PC se guarda en ASCII (100 bytes). Esto provoca un desfase de exactamente 100 bytes en todas las variables posteriores dentro del Bloque 0 (como las coordenadas de spawn y el activeInterior).
3. **Variables de Script Selectivas (Bloque 1):** No se copia el bloque de variables completo. En su lugar, se transfieren únicamente 48 variables de progreso clave ($25, $545, $728, etc.) cuyos índices coinciden exactamente entre el `main.scm` de Android y PC.
4. **Reseteo de Punteros de Memoria:** Variables de punteros a objetos del proceso de Android (como `$883 SAVE_PICKUPS_INDEX` y `$1685 BUY_ASSET_PICKUPS`) se ponen en `0` en PC para evitar crasheos por lectura de direcciones de memoria inválidas.

---

## 2. Bloques que NO se Copian (Incompatibles)

Los siguientes bloques se omiten en la transferencia directa de Android a PC debido a diferencias de tamaño, estructura o dependencias del sistema:

| Bloque | Nombre Técnico | Tamaño PC (bytes) | Tamaño Android (bytes) | Razón de Incompatibilidad / Equivalencia |
| :--- | :--- | :--- | :--- | :--- |
| **Bloque 5** | **Path Find / Nodes** | 1012 o 1068 | 872 o 1124 | Contiene rutas dinámicas y nodos de tráfico modificados por el juego. Difiere en tamaño debido a optimizaciones de memoria del motor móvil. |
| **Bloque 6** | **Pickups (Disquetes/Armas)** | 19923 | 19923 | Aunque el tamaño coincide, contiene punteros a memoria específicos del motor. **No se copia en mid-game** (se usa `--clean-pickups`) para forzar al juego a recrear los disquetes de guardado limpiamente. |
| **Bloque 7** | **Phone Info** | 0 | 0 | Está vacío en la mayoría de las partidas estándar. |
| **Bloque 13** | **Ped Generators / Objects** | 0 | 0 | Reservado para generación temporal de entidades. Vacío en guardados normales. |
| **Bloque 14** | **Object Pool** | 0 | 0 | Reservado para objetos dinámicos. Vacío en guardados normales. |
| **Bloque 23** | **Gang Wars (Estado de Batalla)** | 92 | 100 | Controla si hay una guerra de bandas activa en ese instante (oleada, estado). Android tiene 8 bytes extra (posiblemente variables de control táctil o logros). Se mantiene en `0` (sin guerra activa) de la plantilla. |
| **Bloque 27** | **Entrance/Exit Markers** | 3558 o 3590 | 140 | En PC almacena la base de datos completa de marcadores 3D activos y sus colores. En Android se maneja por script dinámico, por lo que casi todo el bloque está ausente (solo tiene 140 bytes). Copiarlo causaría corrupción de memoria. |
| **Bloque 28** | **Mobile Autosave / Achievements** | 0 (No existe) | 9745 | Exclusivo de Android. Almacena el estado de autoguardado automático, estadísticas de Google Play Games y controles táctiles. |
| **Bloque 29** | **Mobile Settings** | 0 (No existe) | 160 | Exclusivo de Android. Ajustes específicos del port móvil. |
| **Bloque 30** | **Mobile Telemetry / PC Money duplicate**| 44 (Duplicado B15) | 659 | En PC, este bloque es una copia de seguridad del dinero (B15). En Android almacena telemetría y datos analíticos de la aplicación móvil. |
| **Bloque 31** | **PC Stats Redundancy** | 1940 (Duplicado B16) | 0 (No existe) | Duplicado de seguridad de estadísticas del jugador exclusivo de la versión PC. |
| **Bloque 32** | **PC Set Pieces Redundancy** | 6724 (Duplicado B17) | 0 (No existe) | Duplicado de seguridad de scripts del mundo exclusivo de la versión PC. |
| **Bloque 33** | **PC Padding / Checksum Area** | 19157 o 20583 | 0 (No existe) | Bloque final de alineación de disco y control exclusivo de PC. |

---

## 3. Resolución de Problemas Complejos

### A. El Icono de Guardado (Disquetes) No Aparece
*   **Causa:** El script del juego en PC crea los disquetes en las casas basándose en los flags de propiedades compradas (`$728`). Sin embargo, si el Bloque 6 (pickups) ya contiene registros (heredados de una plantilla al 100%), el script piensa que ya se crearon y no hace nada.
*   **Solución:** Al usar `--clean-pickups "GTASAsf3.b"`, se limpia el Bloque 6 del savegame final. Al cargar la partida, el script de PC detecta que el Bloque 6 está vacío y automáticamente genera los disquetes verdes frente a todas tus casas compradas.

### B. No Aparecen las Misiones Siguientes (Faltan Iconos en el Mapa)
*   **Causa Raíz:** Los hilos de script activos (los procesos en segundo plano que controlan el progreso de la historia y activan las misiones) se guardan en el **Bloque 1**.
    *   Como el código del script compilado de Android (`main.scm`) tiene diferentes direcciones y offsets que el de PC, **no podemos copiar los hilos activos de Android**; si lo hiciéramos, el juego en PC crashearía inmediatamente al intentar leer punteros de código inválidos.
    *   Por lo tanto, la partida convertida hereda los hilos activos **directamente de la plantilla de PC** utilizada.
    *   Si utilizas como plantilla un save al 100% (`GTASAsf1-windows.b`), los hilos de script de misiones ya finalizaron, por lo que **nunca aparecerán nuevos iconos de misiones en el mapa**.
    *   Si utilizas una plantilla de inicio (`GTASAsf3.b`), los hilos de script están configurados para buscar las primeras misiones de Sweet en Los Santos, no las misiones de San Fierro.

*   **Solución Definitiva:**
    Para que las misiones que te faltan aparezcan correctamente, **debes usar como plantilla base (`--template`) un savegame de PC que esté exactamente en la misma misión (o muy cerca)**.
    1. Ve a un repositorio de saves de PC (como **GTASnP.com** o foros de GTA).
    2. Descarga una partida guardada de PC que esté en la misión **"Toreno's Last Flight"** (o la misión en la que te quedaste).
    3. Ejecuta la conversión usando ese archivo como plantilla:
       ```bash
       node gta_sa_android_to_pc_converter.js --android "files/GTASAsf2.b" --template "DESCARGADO_DE_PC.b" --output "GTASAsf2-PC-v2.b"
       ```
    Al hacer esto, los hilos de script heredados de la plantilla de PC estarán en el paso exacto de la historia listo para activar el siguiente icono en el mapa, mientras que tus estadísticas, dinero, armas, progreso y territorios se importarán fielmente de tu partida de Android.

---

## 4. Análisis Comparativo: PC Remastered vs Android

Al comparar partidas nativas guardadas en el mismo punto exacto en la versión **PC Remastered (Steam v3 / MS Store)** y la versión **Android (Móvil)**, se descubren las siguientes peculiaridades en la codificación binaria de los bloques:

### A. Marcador de Integridad `0xC0DE` (Inyección de Bytes)
La versión de PC Remastered infla sistemáticamente el tamaño del archivo inyectando la firma de verificación `0xDE 0xC0` (`0xC0DE` en Little Endian) después de escribir sub-estructuras individuales. 

1. **Estructura del Bloque 1 (Script Data):**
   - **Android:**
     - Cabecera: `4 bytes` (tamaño del código).
     - Código de hilos activos: Contiguo (sin firmas).
     - Variables globales: Contiguas (de 4 bytes, o del tamaño correspondiente según el tipo).
   - **PC Remastered:**
     - Cabecera: `8 bytes` (Firma `0xdec0` + `4 bytes` tamaño + Firma `0xdec0`).
     - Código de hilos activos: Cada hilo se guarda como `20 bytes` de datos de hilo + `2 bytes` del marcador `0xdec0` (total 22 bytes).
     - Variables globales: Cada variable se guarda como su tamaño correspondiente + `2 bytes` del marcador `0xdec0` (ej: un entero/decimal de 4 bytes ocupa 6 bytes).

2. **Estructura del Bloque 18 (Mapa/IPLs):**
   - **Android:** `26,316 bytes` (1 byte por elemento de mapa).
   - **PC Remastered:** `78,948 bytes` (cada elemento ocupa 3 bytes: 1 byte de datos + 2 bytes de firma `0xdec0`). Esto explica por qué el bloque de PC es exactamente 3 veces el de Android.

### B. Distribución y Conclusión de Bloques
El guardado de Android cuenta con **31 bloques**, ya que almacena configuraciones táctiles y logs del autoguardado móvil en los bloques 28 a 30. La versión de PC Remastered posee **28 bloques**, omitiendo estas áreas. 

Ambos puertos comparten la misma lógica del estado del juego (las variables globales tienen el mismo índice y propósito), lo que facilita su lectura e interoperabilidad directa una vez que se remueven o inyectan las firmas de integridad correspondientes.

