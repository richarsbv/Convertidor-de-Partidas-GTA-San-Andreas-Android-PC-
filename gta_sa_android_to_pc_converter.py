# =============================================================================
# CONVERTIDOR GTA SAN ANDREAS (ANDROID → PC)
# =============================================================================
# REGLAS TÉCNICAS Y ANÁLISIS DE COMPATIBILIDAD DE BLOQUES:
#
# 1. Bloques de redundancia de PC (B30-B33) y exclusivos de móvil (B28-B29)
#    se omiten o se manejan por plantilla para evitar desajustes estructurales.
# 2. Bloque 22 (Shopping) varía de tamaño (552 bytes en inicio vs 584 en 100%).
#    Para evitar desbordamiento sobre B23 se unifica la plantilla a una de 100%
#    y se limpian los pickups de B6 si se requiere (--clean-pickups).
# 3. Hilos de Script activos (Bloque 1) no se copian de Android para evitar crasheos
#    por diferencias de offsets de código SCM (main.scm). Se heredan de la plantilla.
#    Por ello, para que aparezcan las misiones siguientes en mid-game, se debe usar
#    como plantilla un save de PC del mismo punto de la historia.
#
# Lista de bloques omitidos e incompatibles:
# - B5 (Nodes): Diferencia de tamaño.
# - B6 (Pickups): Copiado opcionalmente limpio para regenerar iconos de guardado.
# - B23 (Gangs): PC=92 bytes, Android=100 bytes (exclusivo móvil).
# - B27 (ENEX markers): PC ~3.5KB, Android=140 bytes.
# - B28, B29, B30 (móvil): Datos analíticos, autoguardado y controles táctiles.
# - B31, B32, B33 (PC): Redundancias exclusivas de PC.
# =============================================================================
import os
import sys
import struct

# =============================================================================
# MAPA DE VARIABLES GLOBALES DEL SCRIPT
# Extraído del main.scm de Android y validado contra main-pc.scm.
# Resultado: 753/754 variables tienen ÍNDICE IDÉNTICO en ambas plataformas.
# Fuente: tabla de debug embebida en main.scm (offset 0x1512C en Android,
#         offset 0x2FB4C7 en PC).
# =============================================================================

# Variables de PROGRESO DE MISIONES - seguras de copiar (mismo índice en ambas plataformas)
MISSION_PROGRESS_VARS = {
    24:   "MISSION_INTRO_PASSED",
    25:   "STAT_UNLOCKED_CITIES_NUMBER",
    26:   "SHOOTING_AVAILABLE",
    57:   "LS_FINAL_MISSIONS_STARTED",
    64:   "CATALINA_TOTAL_PASSED_MISSIONS",
    86:   "MISSION_BACK_TO_SCHOOL_PASSED",
    87:   "MISSION_LEARNING_TO_FLY_PASSED",
    195:  "MISSION_CESAR_VIALPANDO_PASSED",
    # NOTA: $409 ONMISSION NO se copia de Android - se resetea a 0 en RESET_TO_ZERO_VARS.
    # El template puede tener una mision activa (SYND_6, etc.) que al reanudar pone $409=1
    # bloqueando compras y guardado. Android tiene $409=0 (guardado en free-roam).

    448:  "INTRO_TOTAL_PASSED_MISSIONS",
    452:  "SWEET_TOTAL_PASSED_MISSIONS",
    453:  "RYDER_TOTAL_PASSED_MISSIONS",
    454:  "SMOKE_TOTAL_PASSED_MISSIONS",
    455:  "OG_LOC_TOTAL_PASSED_MISSIONS",
    456:  "CRASH_LS_TOTAL_PASSED_MISSIONS",
    457:  "MISSION_LOWRIDER_PASSED",
    458:  "LS_FINAL_TOTAL_PASSED_MISSIONS",
    491:  "TRUTH_TOTAL_PASSED_MISSIONS",
    492:  "CESAR_TOTAL_PASSED_MISSIONS",
    493:  "MISSION_BADLANDS_PASSED",
    541:  "GARAGE_TOTAL_PASSED_MISSIONS",
    542:  "ZERO_TOTAL_PASSED_MISSIONS",
    543:  "WUZIMU_TOTAL_PASSED_MISSIONS",
    544:  "STEAL_TOTAL_PASSED_MISSIONS",
    545:  "SYNDICATE_TOTAL_PASSED_MISSIONS",
    546:  "CRASH_SF_TOTAL_PASSED_MISSIONS",
    593:  "TORENO_TOTAL_PASSED_MISSIONS",
    597:  "CASINO_TOTAL_PASSED_MISSIONS",
    600:  "HEIST_TOTAL_PASSED_MISSIONS",
    626:  "MANSION_TOTAL_PASSED_MISSIONS",
    627:  "GROVE_TOTAL_PASSED_MISSIONS",
    629:  "RIOT_TOTAL_PASSED_MISSIONS",
    717:  "ALL_CATALINA_MISSIONS_PASSED",
    718:  "CATALINA_SELECTED_MISSION",
    # NOTA: $728 PROPERTY_BOUGHT_FLAGS NO se copia de Android.
    # En Android este valor es -1 (0xFFFFFFFF) por diferente inicializacion.
    # En PC, -1 = 'todas las propiedades compradas' -> bloquea TODAS las compras.
    # Se resetea a 0 en RESET_TO_ZERO_VARS y el SCM lo gestiona correctamente.
    802:  "_100_PERCENT_COMPLETE",
    815:  "STAT_PERCENTAGE_COMPLETED",
    1203: "AIRPORT_OPEN_FLAG",
    1620: "ZERO_RCSHOP_BOUGHT",
    2416: "GYMS_ACCESSIBLE_FLAG",
    2555: "GIMP_SUIT_AVAILABLE",
    2556: "VALET_UNIFORM_AVAILABLE",
    2557: "CROUPIER_UNIFORM_AVAILABLE",
    2558: "COP_UNIFORM_AVAILABLE",
    2559: "RURAL_CLOTHES_AVAILABLE",
    2560: "RACING_SUIT_AVAILABLE",
    2561: "MEDIC_UNIFORM_AVAILABLE",
    2562: "PIMP_SUIT_AVAILABLE",
}

# Variables CRITICAS a resetear SIEMPRE a 0 en el save PC
# Estas tienen valores invalidos en Android que rompen la logica de PC.
RESET_TO_ZERO_VARS = {
    # PROPERTY_BOUGHT_FLAGS: debe ser 0 para que el script SCM gestione las propiedades.
    # El valor -1 de Android bloquea todas las compras de propiedades en PC.
    728:  "PROPERTY_BOUGHT_FLAGS",
    # BUY_INDEX: debe ser 0 para evitar estado corrupto en el thread de compras.
    727:  "BUY_INDEX",
    # ONMISSION ($409): Si el template fue guardado DURANTE una mision (ej. SYND_6 Toreno),
    # este flag queda en 1 al reanudar el save en PC -> bloquea compras de propiedades
    # y hace desaparecer los iconos de guardado (el juego rechaza guardar durante mision).
    # Lo seteamos siempre a 0 para garantizar free-roam al cargar.
    409:  "ONMISSION",

    # Save pickups: handles y flags se recrean dinamicamente por el thread SAVE.
    # Reseteamos siempre para que el juego los reinicialice correctamente al cargar.
    865:  "SAVE_PICKUPS[0]",
    866:  "SAVE_PICKUPS[1]",
    867:  "SAVE_PICKUPS[2]",
    868:  "SAVE_PICKUPS[3]",
    869:  "SAVE_PICKUPS[4]",
    870:  "SAVE_PICKUPS[5]",
    871:  "SAVE_PICKUPS[6]",
    872:  "SAVE_PICKUPS[7]",
    873:  "SAVE_PICKUPS[8]",
    874:  "SAVE_PICKUPS[9]",
    875:  "SAVE_PICKUPS[10]",
    876:  "SAVE_PICKUPS[11]",
    877:  "SAVE_PICKUPS[12]",
    878:  "SAVE_PICKUPS[13]",
    879:  "SAVE_PICKUPS[14]",
    880:  "SAVE_PICKUPS[15]",
    881:  "SAVE_PICKUPS[16]",
    882:  "SAVE_PICKUPS[17]",
    883:  "SAVE_PICKUPS_INDEX",
    884:  "SAVE_PICKUPS_EXIST",
    885:  "TOTAL_AVAILABLE_SAVE_PICKUPS",
    1685: "BUY_ASSET_PICKUPS",
    1735: "PROPERTY_BUYING_NOW",
}


class GTASaveConverter:
    def __init__(self, android_file_path, pc_template_path, keep_properties=False, clean_pickups_path=None, threads_from_path=None):
        self.android_path = android_file_path
        self.pc_template_path = pc_template_path
        self.keep_properties = keep_properties
        self.clean_pickups_path = clean_pickups_path
        self.threads_from_path = threads_from_path

        self.android_data = None
        self.pc_data = None
        self.android_offsets = []
        self.pc_offsets = []


    def log(self, message):
        print(f"[INFO] {message}")

    def log_warn(self, message):
        print(f"[WARN] {message}")

    def log_error(self, message):
        print(f"[ERROR] {message}", file=sys.stderr)

    def load_files(self):
        self.log(f"Cargando archivo de Android desde: {self.android_path}")
        if not os.path.exists(self.android_path):
            raise FileNotFoundError(f"El archivo de Android no existe: {self.android_path}")
        with open(self.android_path, "rb") as f:
            self.android_data = bytearray(f.read())
        self.log(f"Tamaño de Android: {len(self.android_data):,} bytes")

        self.log(f"Cargando plantilla de PC desde: {self.pc_template_path}")
        if not os.path.exists(self.pc_template_path):
            raise FileNotFoundError(f"La plantilla de PC no existe: {self.pc_template_path}")
        with open(self.pc_template_path, "rb") as f:
            self.pc_data = bytearray(f.read())
        self.log(f"Tamaño de PC: {len(self.pc_data):,} bytes")

        self.android_offsets = self._find_blocks(self.android_data)
        self.pc_offsets = self._find_blocks(self.pc_data)
        self.log(f"Bloques encontrados - Android: {len(self.android_offsets)}, PC: {len(self.pc_offsets)}")

        if len(self.android_offsets) < 28:
            raise ValueError("El archivo de Android parece corrupto (menos de 28 bloques).")
        if len(self.pc_offsets) < 34:
            raise ValueError("La plantilla de PC no es válida (necesita >= 34 bloques, versión 1.0 PC).")

    def _find_blocks(self, data):
        offsets = []
        offset = 0
        target = b"BLOCK"
        while True:
            idx = data.find(target, offset)
            if idx == -1:
                break
            offsets.append(idx)
            offset = idx + 5
        return offsets

    def get_block_body(self, data, offsets, block_idx):
        start = offsets[block_idx] + 5
        end = offsets[block_idx + 1] if block_idx + 1 < len(offsets) else len(data) - 4
        return start, end, data[start:end]

    # -------------------------------------------------------------------------
    # TRANSFERENCIA SELECTIVA DE VARIABLES DE SCRIPT (Bloque 1)
    # -------------------------------------------------------------------------
    def transfer_script_globals(self):
        """
        Transfiere selectivamente las variables de progreso de misiones del
        Bloque 1 de Android al Bloque 1 de PC, usando los índices $N validados
        contra ambos main.scm (Android y PC).

        Reglas:
        1. Variables en MISSION_PROGRESS_VARS → copiar de Android a PC
        2. Variables en RESET_TO_ZERO_VARS    → poner en 0 en PC (punteros inválidos)
        3. Resto de variables                  → conservar del template de PC (script state)
        """
        self.log("Procesando Bloque 1 (Script Globals - Transferencia Selectiva)...")

        a_b1_start, _, _ = self.get_block_body(self.android_data, self.android_offsets, 1)
        p_b1_start, _, _ = self.get_block_body(self.pc_data, self.pc_offsets, 1)

        # Leer tamaños del código del script
        a_code_size = struct.unpack_from("<I", self.android_data, a_b1_start)[0]
        p_code_size = struct.unpack_from("<I", self.pc_data, p_b1_start)[0]

        self.log(f"  Código Android: {a_code_size:,} bytes | Código PC: {p_code_size:,} bytes")

        # Opción: reemplazar el code section del template con el de otro save PC (free-roam)
        # Esto elimina cualquier thread de misión activo que pueda quedar del template.
        # Útil cuando el template fue guardado DURANTE una misión (p.ej. SYND_6, Toreno).
        if self.threads_from_path and os.path.exists(self.threads_from_path):
            self.log(f"  ℹ️  Cargando threads desde: {self.threads_from_path}")
            with open(self.threads_from_path, "rb") as f:
                tf_data = bytearray(f.read())
            tf_offsets = self._find_blocks(tf_data)
            tf_b1_start, _, _ = self.get_block_body(tf_data, tf_offsets, 1)
            tf_code_size = struct.unpack_from("<I", tf_data, tf_b1_start)[0]
            if tf_code_size == p_code_size:
                # Mismas versiones de SCM: reemplazar code section directamente
                src_start = tf_b1_start + 4
                src_end = src_start + tf_code_size
                dst_start = p_b1_start + 4
                self.pc_data[dst_start:dst_start + tf_code_size] = tf_data[src_start:src_end]
                self.log(f"  ✅ Code section (threads) reemplazado ({tf_code_size} bytes) desde template libre")
            else:
                self.log_warn(f"  Tamaño de code section diferente ({tf_code_size} vs {p_code_size}) - omitiendo")
        elif self.threads_from_path:
            self.log_warn(f"  Archivo de threads no encontrado: {self.threads_from_path} - omitiendo")


        a_globals_start = a_b1_start + 4 + a_code_size
        p_globals_start = p_b1_start + 4 + p_code_size

        # Calcular cuántas variables hay en cada plataforma
        a_b1_end = self.android_offsets[1 + 1] if 1 + 1 < len(self.android_offsets) else len(self.android_data) - 4
        p_b1_end = self.pc_offsets[1 + 1] if 1 + 1 < len(self.pc_offsets) else len(self.pc_data) - 4
        a_num_vars = (a_b1_end - a_globals_start) // 4
        p_num_vars = (p_b1_end - p_globals_start) // 4

        self.log(f"  Variables globales - Android: {a_num_vars} | PC: {p_num_vars}")

        # Paso 1: Copiar variables de progreso de Android a PC
        copied = 0
        skipped_range = 0
        for var_idx, var_name in MISSION_PROGRESS_VARS.items():
            a_offset = a_globals_start + var_idx * 4
            p_offset = p_globals_start + var_idx * 4

            if a_offset + 4 > a_b1_end:
                self.log_warn(f"  $${var_idx} ({var_name}) fuera del rango de Android - omitido")
                skipped_range += 1
                continue
            if p_offset + 4 > p_b1_end:
                self.log_warn(f"  $${var_idx} ({var_name}) fuera del rango de PC - omitido")
                skipped_range += 1
                continue

            self.pc_data[p_offset:p_offset + 4] = self.android_data[a_offset:a_offset + 4]
            copied += 1

        self.log(f"  Variables de misiones transferidas: {copied} | Omitidas (rango): {skipped_range}")

        # Paso 2: Resetear variables criticas a 0 SIEMPRE (no solo con --clean-pickups)
        # Estas variables tienen valores invalidos en Android que rompen la logica de PC.
        reset = 0
        for var_idx, var_name in RESET_TO_ZERO_VARS.items():
            p_offset = p_globals_start + var_idx * 4
            if p_offset + 4 <= p_b1_end:
                self.pc_data[p_offset:p_offset + 4] = b'\x00\x00\x00\x00'
                reset += 1

        self.log(f"  Variables criticas reseteadas a 0: {reset} (PROPERTY_BOUGHT_FLAGS y SAVE_PICKUPS incluidos)")

        # Paso 3: Log de valores de progreso transferidos
        self.log("  --- Progreso de misiones transferido ---")
        for var_idx, var_name in sorted(MISSION_PROGRESS_VARS.items()):
            p_offset = p_globals_start + var_idx * 4
            if p_offset + 4 <= p_b1_end:
                val = struct.unpack_from("<i", self.pc_data, p_offset)[0]
                if val != 0:
                    self.log(f"    ${var_idx} {var_name} = {val}")

    def convert(self, output_path):
        self.log("=" * 60)
        self.log("INICIANDO CONVERSIÓN GTA SA: Android → PC")
        self.log("=" * 60)
        self.load_files()

        # ----------------------------------------------------------------
        # BLOQUE 0: Metadatos (nombre, tiempo, clima, posición)
        # ----------------------------------------------------------------
        self.log("\n[BLOQUE 0] Metadatos...")
        a_b0_start, _, a_b0 = self.get_block_body(self.android_data, self.android_offsets, 0)
        p_b0_start, _, p_b0 = self.get_block_body(self.pc_data, self.pc_offsets, 0)

        # Nombre de la partida: Android=UTF-16LE 200 bytes desde offset 4
        #                       PC=ASCII 100 bytes desde offset 4
        name_raw = a_b0[4:204]
        try:
            save_name = name_raw.decode("utf-16le").split('\x00')[0]
        except Exception:
            save_name = "Partida Convertida"
        self.log(f"  Nombre: '{save_name}'")
        save_name_ascii = save_name.encode("ascii", errors="ignore")[:99].ljust(100, b'\x00')
        self.pc_data[p_b0_start + 4 : p_b0_start + 104] = save_name_ascii

        # Tiempo y clima
        self.pc_data[p_b0_start + 132 : p_b0_start + 136] = a_b0[232:236]  # currentTime
        self.pc_data[p_b0_start + 136] = a_b0[236]                          # weekday

        # timeCopy (Month, Day, Hour, Minute) - Si es 0, forzar a currentTime
        t_copy_val = struct.unpack_from("<i", a_b0, 237)[0]
        if t_copy_val == 0:
            self.pc_data[p_b0_start + 137 : p_b0_start + 141] = a_b0[232:236]
            self.log("  Aviso: timeCopy en Android es 0. Forzando a currentTime.")
        else:
            self.pc_data[p_b0_start + 137 : p_b0_start + 141] = a_b0[237:241]

        self.pc_data[p_b0_start + 144] = a_b0[244]                          # boolHasEverCheated

        # Sincronizar temporizadores globales (globalTimer1 y globalTimer2)
        self.pc_data[p_b0_start + 128 : p_b0_start + 132] = a_b0[228:232]  # globalTimer1
        self.pc_data[p_b0_start + 148 : p_b0_start + 152] = a_b0[248:252]  # globalTimer2
        g_timer = struct.unpack_from("<I", a_b0, 248)[0]
        self.log(f"  Temporizadores globales sincronizados: {g_timer} ms")

        # Copiar minuteLength para consistencia
        self.pc_data[p_b0_start + 124 : p_b0_start + 128] = a_b0[224:228]  # minuteLength

        self.pc_data[p_b0_start + 168 : p_b0_start + 174] = a_b0[268:274]  # Weather IDs

        # Posición de spawn
        a_b2_start, _, a_b2 = self.get_block_body(self.android_data, self.android_offsets, 2)
        p_b2_start, _, p_b2 = self.get_block_body(self.pc_data, self.pc_offsets, 2)

        temp_interior = bytes(self.pc_data[p_b0_start + 188 : p_b0_start + 200])
        temp_town     = bytes(self.pc_data[p_b0_start + 108 : p_b0_start + 112])
        temp_pos      = bytes(self.pc_data[p_b2_start + 20  : p_b2_start + 32])
        temp_x, temp_y, temp_z = struct.unpack("<fff", temp_pos)

        a_interior_val = struct.unpack("<i", a_b0[296:300])[0]
        a_town_val     = struct.unpack("<I", a_b0[208:212])[0]
        a_pos_bytes    = bytes(a_b2[20:32])
        pos_x, pos_y, pos_z = struct.unpack("<fff", a_pos_bytes)

        # Validar coordenadas
        coords_invalid = False
        if not (-3000.0 <= pos_x <= 3000.0 and -3000.0 <= pos_y <= 3000.0):
            coords_invalid = True
            self.log_warn(f"  Coordenadas fuera del mapa: X={pos_x:.2f}, Y={pos_y:.2f} → usando spawn seguro")
        if a_interior_val < 0 or a_interior_val > 20:
            coords_invalid = True
            self.log_warn(f"  Interior ID inválido: {a_interior_val} → usando spawn seguro")
        if a_interior_val == 0 and not (-10.0 <= pos_z <= 200.0):
            coords_invalid = True
            self.log_warn(f"  Altura Z inválida para exterior: Z={pos_z:.2f} → usando spawn seguro")
        elif a_interior_val > 0 and not (800.0 <= pos_z <= 1200.0):
            coords_invalid = True
            self.log_warn(f"  Altura Z inválida para interior: Z={pos_z:.2f} → usando spawn seguro")

        if coords_invalid:
            self.pc_data[p_b0_start + 188 : p_b0_start + 200] = temp_interior
            self.pc_data[p_b0_start + 108 : p_b0_start + 112] = temp_town
            self.pc_data[p_b2_start + 20  : p_b2_start + 32 ] = temp_pos
            final_x, final_y, final_z = temp_x, temp_y, temp_z
        else:
            self.pc_data[p_b0_start + 188 : p_b0_start + 200] = a_b0[288:300]
            self.pc_data[p_b0_start + 108 : p_b0_start + 112] = a_b0[208:212]
            self.pc_data[p_b2_start + 20  : p_b2_start + 32 ] = a_pos_bytes
            final_x, final_y, final_z = pos_x, pos_y, pos_z

        self.log(f"  Spawn: X={final_x:.2f}, Y={final_y:.2f}, Z={final_z:.2f} | Interior={a_interior_val} | Town={a_town_val}")

        # ----------------------------------------------------------------
        # BLOQUE 1: Script Globals (transferencia selectiva de misiones)
        # ----------------------------------------------------------------
        self.transfer_script_globals()

        # ----------------------------------------------------------------
        # BLOQUE 2: Player Ped (salud, armas, ropa)
        # ----------------------------------------------------------------
        self.log("\n[BLOQUE 2] Jugador (salud, armas, ropa)...")

        # Salud y armadura
        self.pc_data[p_b2_start + 32 : p_b2_start + 40] = a_b2[36:44]
        h_val, a_val = struct.unpack("<ff", a_b2[36:44])
        self.log(f"  Salud: {h_val:.1f} | Armadura: {a_val:.1f}")

        # Armas (13 slots × 28 bytes)
        self.pc_data[p_b2_start + 40 : p_b2_start + 404] = a_b2[44:408]
        self.log("  Armas: copiadas (13 slots)")

        # Nivel de búsqueda
        self.pc_data[p_b2_start + 424] = a_b2[448]

        # Ropa (texturesCRC, 112 bytes)
        self.pc_data[p_b2_start + 428 : p_b2_start + 540] = a_b2[452:564]

        # Grasa y músculo
        self.pc_data[p_b2_start + 540 : p_b2_start + 548] = a_b2[564:572]
        fat_val, musc_val = struct.unpack("<ff", a_b2[564:572])
        self.log(f"  Grasa: {fat_val:.1f} | Músculo: {musc_val:.1f}")

        # ----------------------------------------------------------------
        # BLOQUE 3: Garajes
        # ----------------------------------------------------------------
        self.log("\n[BLOQUE 3] Garajes...")
        a_b3_start, a_b3_end, _ = self.get_block_body(self.android_data, self.android_offsets, 3)
        p_b3_start, p_b3_end, _ = self.get_block_body(self.pc_data, self.pc_offsets, 3)
        self.pc_data[p_b3_start : p_b3_end] = self.android_data[a_b3_start : a_b3_end]
        self.log("  Garajes: copiados")

        # ----------------------------------------------------------------
        # BLOQUES IDÉNTICOS (copia directa)
        # ----------------------------------------------------------------
        self.log("\n[BLOQUES DIRECTOS] Configuración, Zonas, Coches, Relaciones, etc...")
        safe_blocks = [
            (4, "Configuración simple"),
            (8, "Ubicaciones de reinicio (Hospital/Policía)"),
            (10, "Zonas / Territorios de Bandas"),
            (11, "Armas de Bandas"),
            (12, "Generadores de Coches (Parked Cars)"),
            (17, "Set Pieces"),
            (18, "Zonas de Mapa/IPLs"),
            (19, "Relaciones de Peds / Respeto de Bandas"),
            (20, "Grafitis/Tags"),
            (21, "IPLs de Interiores"),
            (24, "Saltos Únicos"),
            (25, "Conexiones ENEX (Puertas Abiertas/Cerradas)"),
            (26, "Datos de Radio")
        ]
        for idx, desc in safe_blocks:
            a_s, a_e, _ = self.get_block_body(self.android_data, self.android_offsets, idx)
            p_s, p_e, _ = self.get_block_body(self.pc_data, self.pc_offsets, idx)
            self.pc_data[p_s : p_e] = self.android_data[a_s : a_e]
            self.log(f"  Bloque {idx} ({desc}): copiado")

        # ----------------------------------------------------------------
        # BLOQUE 6: Pickups (limpieza / copia de disquetes limpios)
        # ----------------------------------------------------------------
        if self.clean_pickups_path:
            self.log(f"\n[BLOQUE 6] Copiando pickups limpios desde: {self.clean_pickups_path}")
            with open(self.clean_pickups_path, "rb") as f:
                c_data = bytearray(f.read())
            c_offsets = self._find_blocks(c_data)
            c_s, c_e, _ = self.get_block_body(c_data, c_offsets, 6)
            p_s, p_e, _ = self.get_block_body(self.pc_data, self.pc_offsets, 6)
            self.pc_data[p_s : p_e] = c_data[c_s : c_e]
            self.log("  Pickups limpios copiados (iconos de guardado listos para recrear)")

        # ----------------------------------------------------------------
        # BLOQUE 9: Radar Blips
        # ----------------------------------------------------------------
        self.log("\n[BLOQUE 9] Radar Blips...")
        a_b9_start, _, _ = self.get_block_body(self.android_data, self.android_offsets, 9)
        p_b9_start, _, _ = self.get_block_body(self.pc_data, self.pc_offsets, 9)
        self.pc_data[p_b9_start : p_b9_start + 7000] = self.android_data[a_b9_start : a_b9_start + 7000]
        self.log("  Blips copiados (175 × 40 bytes)")

        # ----------------------------------------------------------------
        # BLOQUES 15 & 30: Dinero del jugador
        # ----------------------------------------------------------------
        self.log("\n[BLOQUES 15 & 30] Dinero...")
        a_b15_start, a_b15_end, _ = self.get_block_body(self.android_data, self.android_offsets, 15)
        p_b15_start, p_b15_end, _ = self.get_block_body(self.pc_data, self.pc_offsets, 15)
        self.pc_data[p_b15_start : p_b15_end] = self.android_data[a_b15_start : a_b15_end]
        p_b30_start, p_b30_end, _ = self.get_block_body(self.pc_data, self.pc_offsets, 30)
        self.pc_data[p_b30_start : p_b30_end] = self.android_data[a_b15_start : a_b15_end]
        money_val = struct.unpack("<i", self.android_data[a_b15_start + 4 : a_b15_start + 8])[0]
        self.log(f"  Dinero: ${money_val:,}")

        # ----------------------------------------------------------------
        # BLOQUES 16 & 31: Estadísticas
        # ----------------------------------------------------------------
        self.log("\n[BLOQUES 16 & 31] Estadísticas...")
        a_b16_start, a_b16_end, _ = self.get_block_body(self.android_data, self.android_offsets, 16)
        p_b16_start, p_b16_end, _ = self.get_block_body(self.pc_data, self.pc_offsets, 16)
        self.pc_data[p_b16_start : p_b16_end] = self.android_data[a_b16_start : a_b16_end]
        p_b31_start, p_b31_end, _ = self.get_block_body(self.pc_data, self.pc_offsets, 31)
        self.pc_data[p_b31_start : p_b31_end] = self.android_data[a_b16_start : a_b16_end]
        self.log("  Estadísticas copiadas (respeto, habilidades, etc.)")

        # ----------------------------------------------------------------
        # BLOQUE 22: Shopping / Propiedades compradas
        # ----------------------------------------------------------------
        # NOTA IMPORTANTE: El Bloque 22 en Android tiene nEntries=0 (la gestion de propiedades
        # en Android usa un sistema diferente basado en flags de script, no en este bloque).
        # En PC, los pickups de compra se recrean dinamicamente por el thread BUY_PROP/BUY_ASSET.
        # Con $728 PROPERTY_BOUGHT_FLAGS reseteado a 0, el jugador puede comprar propiedades
        # que ya tenia en Android (necesario para que el sistema PC funcione correctamente).
        #
        # Estructura real del Bloque 22 (PC):
        #   4 bytes: nEntries (numero de propiedades registradas)
        #   160 bytes * nEntries: datos de cada propiedad (PROP_ENTRY_SIZE=160)
        #   restante: cloth data y otros datos de shopping
        self.log("\n[BLOQUE 22] Shopping / Propiedades...")
        a_b22_start, _, a_b22 = self.get_block_body(self.android_data, self.android_offsets, 22)
        p_b22_start, p_b22_end, _ = self.get_block_body(self.pc_data, self.pc_offsets, 22)

        a_entries22 = struct.unpack("<I", a_b22[0:4])[0]
        p_entries22 = struct.unpack("<I", self.pc_data[p_b22_start:p_b22_start + 4])[0]

        PROP_ENTRY_SIZE = 160
        a_cloth_offset = 4 + a_entries22 * PROP_ENTRY_SIZE
        p_cloth_offset = 4 + p_entries22 * PROP_ENTRY_SIZE

        self.log(f"  Block 22: Android nEntries={a_entries22} | PC nEntries={p_entries22}")
        self.log(f"  Offsets de cloth data: Android={a_cloth_offset} | PC={p_cloth_offset}")

        if a_entries22 == 0 and p_entries22 == 0:
            # Ambos vacios: copiar solo la seccion de ropa (cloth/shopping)
            a_b22_len = len(a_b22)
            p_b22_len = p_b22_end - p_b22_start
            cloth_size = min(a_b22_len - a_cloth_offset, p_b22_len - p_cloth_offset)
            if cloth_size > 0:
                self.pc_data[p_b22_start + p_cloth_offset : p_b22_start + p_cloth_offset + cloth_size] = \
                    a_b22[a_cloth_offset : a_cloth_offset + cloth_size]
                self.log(f"  Cloth/Shopping data copiada: {cloth_size} bytes")
        elif a_entries22 > 0:
            # Android tiene propiedades registradas: copiar hasta el tamano de PC
            copy_size = min(len(a_b22), p_b22_end - p_b22_start)
            self.pc_data[p_b22_start : p_b22_start + copy_size] = a_b22[:copy_size]
            if a_entries22 > p_entries22 and p_entries22 > 0:
                struct.pack_into("<I", self.pc_data, p_b22_start, p_entries22)
                self.log(f"  Aviso: Android tiene mas propiedades ({a_entries22}) que PC ({p_entries22}). Truncado.")
            self.log("  Propiedades copiadas desde Android")
        else:
            self.log("  Conservando Bloque 22 de la plantilla PC (Android sin propiedades registradas)")

        # ----------------------------------------------------------------
        # CHECKSUM FINAL
        # ----------------------------------------------------------------
        self.log("\n[CHECKSUM] Recalculando...")
        checksum_calc = sum(self.pc_data[:-4]) & 0xFFFFFFFF
        struct.pack_into("<I", self.pc_data, len(self.pc_data) - 4, checksum_calc)
        self.log(f"  Checksum: 0x{checksum_calc:08X}")

        # ----------------------------------------------------------------
        # GUARDAR ARCHIVO
        # ----------------------------------------------------------------
        if os.path.exists(output_path):
            backup_path = output_path + ".bak"
            self.log(f"\nBackup del archivo anterior: {backup_path}")
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(output_path, backup_path)

        with open(output_path, "wb") as f:
            f.write(self.pc_data)

        self.log(f"\n{'=' * 60}")
        self.log(f"✅ CONVERSIÓN COMPLETADA: {output_path}")
        self.log(f"{'=' * 60}")


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    android_file  = None
    pc_template   = None
    output_file   = None
    keep_props    = False
    clean_pickups = None
    threads_from  = None


    args = sys.argv[1:]

    # Parseo de argumentos
    i = 0
    while i < len(args):
        if args[i] == "--android" and i + 1 < len(args):
            android_file = args[i + 1]; i += 2
        elif args[i] == "--template" and i + 1 < len(args):
            pc_template = args[i + 1]; i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]; i += 2
        elif args[i] == "--keep-properties":
            keep_props = True; i += 1
        elif args[i] == "--clean-pickups" and i + 1 < len(args):
            clean_pickups = args[i + 1]; i += 2
        elif args[i] == "--threads-from" and i + 1 < len(args):
            threads_from = args[i + 1]; i += 2
        else:
            i += 1


    # Fallback a argumentos posicionales
    if not android_file and len(sys.argv) >= 4:
        android_file = sys.argv[1]
        pc_template  = sys.argv[2]
        output_file  = sys.argv[3]

    if not android_file or not pc_template or not output_file:
        print("Uso:")
        print("  python gta_sa_android_to_pc_converter.py --android <android.b> --template <plantilla_pc.b> --output <salida_pc.b> [--keep-properties]")
        print("")
        print("Opciones:")
        print("  --keep-properties   Conserva el Bloque 22 (propiedades) de la plantilla de PC")
        print("                      en lugar de copiar el de Android. Útil si la plantilla")
        print("                      ya tiene las propiedades correctas desbloqueadas.")
        print("  --clean-pickups <clean_template.b> Copia pickups limpios de una plantilla de inicio (Bloque 6)")
        print("  --threads-from <free_roam.b>       Usa los threads de script de otro save PC en free-roam")
        print("                                     (Necesario si el template fue guardado durante una mision)")

        sys.exit(1)

    try:
        converter = GTASaveConverter(android_file, pc_template, keep_properties=keep_props, clean_pickups_path=clean_pickups, threads_from_path=threads_from)

        converter.convert(output_file)
    except Exception as e:
        print(f"[ERROR CRÍTICO] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
