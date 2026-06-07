#!/usr/bin/env node
/**
 * GTA SA Android → PC Save Converter (Node.js)
 * =============================================
 * Convierte partidas guardadas de GTA San Andreas de Android a PC Windows.
 *
 * REGLAS TÉCNICAS Y ANÁLISIS DE COMPATIBILIDAD DE BLOQUES:
 * 
 * 1. Bloques de redundancia de PC (B30-B33) y exclusivos de móvil (B28-B29)
 *    se omiten o se manejan por plantilla para evitar desajustes estructurales.
 * 2. Bloque 22 (Shopping) varía de tamaño (552 bytes en inicio vs 584 en 100%).
 *    Para evitar desbordamiento sobre B23 se unifica la plantilla a una de 100%
 *    y se limpian los pickups de B6 si se requiere (--clean-pickups).
 * 3. Hilos de Script activos (Bloque 1) no se copian de Android para evitar crasheos
 *    por diferencias de offsets de código SCM (main.scm). Se heredan de la plantilla.
 *    Por ello, para que aparezcan las misiones siguientes en mid-game, se debe usar
 *    como plantilla un save de PC del mismo punto de la historia.
 *
 * Lista de bloques omitidos e incompatibles:
 * - B5 (Nodes): Diferencia de tamaño.
 * - B6 (Pickups): Copiado opcionalmente limpio para regenerar iconos de guardado.
 * - B23 (Gangs): PC=92 bytes, Android=100 bytes (exclusivo móvil).
 * - B27 (ENEX markers): PC ~3.5KB, Android=140 bytes.
 * - B28, B29, B30 (móvil): Datos analíticos, autoguardado y controles táctiles.
 * - B31, B32, B33 (PC): Redundancias exclusivas de PC.
 *
 * Uso:
 *   node gta_sa_android_to_pc_converter.js --android <android.b> --template <plantilla_pc.b> --output <salida.b>
 *   node gta_sa_android_to_pc_converter.js --android <android.b> --template <plantilla_pc.b> --output <salida.b> --clean-pickups <clean.b>
 */

const fs = require('fs');
const path = require('path');

// =============================================================================
// MAPA DE VARIABLES DE SCRIPT
// Validado contra main.scm de Android (103,876 bytes) y main-pc.scm (3,144,055 bytes)
// Los índices $N son idénticos en ambas plataformas.
// =============================================================================

/** Variables de progreso de misiones - seguras de copiar de Android a PC */
const MISSION_PROGRESS_VARS = {
    // NOTA: $728 PROPERTY_BOUGHT_FLAGS NO se copia de Android.
    // En Android, este valor es -1 (0xFFFFFFFF) por diferente inicialización.
    // En PC, -1 = "todas las propiedades compradas" → bloquea TODAS las compras.
    // Lo reseteamos a 0 y el script SCM lo gestiona correctamente al cargar.
    1620: 'ZERO_RCSHOP_BOUGHT',
};

/** Variables a resetear SIEMPRE a 0 en el save PC (punteros inválidos de Android) */
const RESET_TO_ZERO_VARS = {
    // PROPERTY_BOUGHT_FLAGS: debe ser 0 para que el script SCM gestione las propiedades.
    // El valor -1 de Android bloquea todas las compras de propiedades en PC.
    728:  'PROPERTY_BOUGHT_FLAGS',
    // BUY_INDEX debe ser 0 para evitar estado corrupto en el thread de compras.
    727:  'BUY_INDEX',

    // ONMISSION ($409): Si el template fue guardado DURANTE una misión (ej. SYND_6 Toreno),
    // este flag queda en 1 al reanudar el save en PC → bloquea compras de propiedades
    // y hace desaparecer los iconos de guardado (el juego rechaza guardar durante misión).
    // Lo seteamos siempre a 0 para garantizar free-roam al cargar.
    409:  'ONMISSION',

    // Save pickups: handles y flags se recrean dinámicamente por el thread SAVE.
    // Reseteamos siempre para que el juego los reinicialice correctamente al cargar.
    865:  'SAVE_PICKUPS[0]',
    866:  'SAVE_PICKUPS[1]',
    867:  'SAVE_PICKUPS[2]',
    868:  'SAVE_PICKUPS[3]',
    869:  'SAVE_PICKUPS[4]',
    870:  'SAVE_PICKUPS[5]',
    871:  'SAVE_PICKUPS[6]',
    872:  'SAVE_PICKUPS[7]',
    873:  'SAVE_PICKUPS[8]',
    874:  'SAVE_PICKUPS[9]',
    875:  'SAVE_PICKUPS[10]',
    876:  'SAVE_PICKUPS[11]',
    877:  'SAVE_PICKUPS[12]',
    878:  'SAVE_PICKUPS[13]',
    879:  'SAVE_PICKUPS[14]',
    880:  'SAVE_PICKUPS[15]',
    881:  'SAVE_PICKUPS[16]',
    882:  'SAVE_PICKUPS[17]',
    883:  'SAVE_PICKUPS_INDEX',
    884:  'SAVE_PICKUPS_EXIST',
    885:  'TOTAL_AVAILABLE_SAVE_PICKUPS',
    1685: 'BUY_ASSET_PICKUPS',
    1735: 'PROPERTY_BUYING_NOW',
};



// =============================================================================
// FUNCIONES AUXILIARES
// =============================================================================

function log(msg)  { console.log(`[INFO] ${msg}`); }
function warn(msg) { console.log(`[WARN] ${msg}`); }
function err(msg)  { console.error(`[ERROR] ${msg}`); }

/** Encuentra los offsets de cada bloque "BLOCK" en el save */
function findBlocks(data) {
    const target = Buffer.from('BLOCK');
    const offsets = [];
    let pos = 0;
    while (true) {
        const idx = data.indexOf(target, pos);
        if (idx === -1) break;
        offsets.push(idx);
        pos = idx + 5;
    }
    return offsets;
}

/** Devuelve {start, end, body} del cuerpo de un bloque (sin la firma "BLOCK") */
function getBlock(data, offsets, idx) {
    const start = offsets[idx] + 5;
    const end   = (idx + 1 < offsets.length) ? offsets[idx + 1] : data.length - 4;
    return { start, end, body: data.subarray(start, end) };
}

/** Lee un float IEEE754 de 4 bytes LE */
function readFloat(buf, offset) {
    return buf.readFloatLE(offset);
}

// =============================================================================
// CONVERSIÓN PRINCIPAL
// =============================================================================

function convert(androidPath, templatePath, outputPath, keepProperties, cleanPickupsPath, threadsFromPath) {

    log('=' .repeat(60));
    log('GTA SA Android → PC Save Converter');
    log('='.repeat(60));

    // Cargar archivos
    log(`Cargando Android: ${androidPath}`);
    const aData = Buffer.from(fs.readFileSync(androidPath)); // copia mutable
    const aRaw  = Buffer.from(aData);                        // referencia lectura

    log(`Cargando Plantilla PC: ${templatePath}`);
    const pData = Buffer.from(fs.readFileSync(templatePath));

    log(`Android: ${aData.length.toLocaleString()} bytes | PC: ${pData.length.toLocaleString()} bytes`);

    const aOffsets = findBlocks(aData);
    const pOffsets = findBlocks(pData);
    log(`Bloques - Android: ${aOffsets.length} | PC: ${pOffsets.length}`);

    if (aOffsets.length < 28) throw new Error('Android: menos de 28 bloques (archivo corrupto?)');
    if (pOffsets.length < 34) throw new Error('PC: menos de 34 bloques (debe ser versión 1.0 PC estándar)');

    // ----------------------------------------------------------------
    // BLOQUE 0: Metadatos (nombre, tiempo, clima, spawn)
    // ----------------------------------------------------------------
    log('\n[BLOQUE 0] Metadatos...');
    const aB0 = getBlock(aData, aOffsets, 0);
    const pB0 = getBlock(pData, pOffsets, 0);
    const aB2 = getBlock(aData, aOffsets, 2);
    const pB2 = getBlock(pData, pOffsets, 2);

    // Nombre: Android=UTF-16LE 200 bytes desde offset 4, PC=ASCII 100 bytes desde offset 4
    const nameRaw = aData.subarray(aB0.start + 4, aB0.start + 204);
    let saveName = '';
    try {
        saveName = nameRaw.toString('utf16le').split('\x00')[0];
    } catch(e) { saveName = 'Partida Convertida'; }
    log(`  Nombre: "${saveName}"`);

    const nameAscii = Buffer.alloc(100, 0);
    Buffer.from(saveName, 'ascii').copy(nameAscii, 0, 0, 99);
    nameAscii.copy(pData, pB0.start + 4, 0, 100);

    // Tiempo y clima
    aData.copy(pData, pB0.start + 132, aB0.start + 232, aB0.start + 236); // currentTime
    pData[pB0.start + 136] = aData[aB0.start + 236];                       // weekday

    // timeCopy (Month, Day, Hour, Minute) - Si viene en 0 de Android,
    // lo forzamos a ser igual a currentTime para evitar congelar el reloj en PC.
    let tCopyVal = aData.readInt32LE(aB0.start + 237);
    if (tCopyVal === 0) {
        aData.copy(pData, pB0.start + 137, aB0.start + 232, aB0.start + 236); // usar currentTime
        log('  Aviso: timeCopy en Android es 0. Forzando a currentTime.');
    } else {
        aData.copy(pData, pB0.start + 137, aB0.start + 237, aB0.start + 241); // timeCopy original
    }

    pData[pB0.start + 144] = aData[aB0.start + 244];                       // hasEverCheated

    // globalTimer (Sincronizar ambas copias de temporizadores globales)
    aData.copy(pData, pB0.start + 128, aB0.start + 228, aB0.start + 232); // globalTimer1
    aData.copy(pData, pB0.start + 148, aB0.start + 248, aB0.start + 252); // globalTimer2
    log(`  Temporizadores globales de juego sincronizados: ${aData.readUInt32LE(aB0.start + 248)} ms`);

    // minuteLength (copiar para consistencia)
    aData.copy(pData, pB0.start + 124, aB0.start + 224, aB0.start + 228); // minuteLength

    aData.copy(pData, pB0.start + 168, aB0.start + 268, aB0.start + 274); // weather IDs

    // Spawn: validar coordenadas
    const tempInterior = Buffer.from(pData.subarray(pB0.start + 188, pB0.start + 200));
    const tempTown     = Buffer.from(pData.subarray(pB0.start + 108, pB0.start + 112));
    const tempPos      = Buffer.from(pData.subarray(pB2.start + 20,  pB2.start + 32));
    const [tempX, tempY, tempZ] = [readFloat(tempPos,0), readFloat(tempPos,4), readFloat(tempPos,8)];

    const aInterior = aData.readInt32LE(aB0.start + 296);
    const aTown     = aData.readUInt32LE(aB0.start + 208);
    const posX      = readFloat(aData, aB2.start + 20);
    const posY      = readFloat(aData, aB2.start + 24);
    const posZ      = readFloat(aData, aB2.start + 28);

    let useAndroidSpawn = true;
    if (aInterior > 0 || posZ > 900) {
        warn(`  Guardado dentro de interior (ID: ${aInterior}, Z: ${posZ.toFixed(1)}) → spawn seguro (exterior)`);
        useAndroidSpawn = false;
    }
    if (posX < -3000 || posX > 3000 || posY < -3000 || posY > 3000) {
        warn(`  Coords fuera del mapa X=${posX.toFixed(1)}, Y=${posY.toFixed(1)} → spawn seguro`);
        useAndroidSpawn = false;
    }
    if (aInterior < 0 || aInterior > 20) {
        warn(`  Interior ID inválido: ${aInterior} → spawn seguro`);
        useAndroidSpawn = false;
    }
    if (aInterior === 0 && (posZ < -10 || posZ > 200)) {
        warn(`  Z inválida para exterior: ${posZ.toFixed(1)} → spawn seguro`);
        useAndroidSpawn = false;
    }


    if (useAndroidSpawn) {
        aData.copy(pData, pB0.start + 188, aB0.start + 288, aB0.start + 300); // copiar los 12 bytes del bloque de interior (incluye activeInterior en offset 196)
        aData.copy(pData, pB0.start + 108, aB0.start + 208, aB0.start + 212); // town
        aData.copy(pData, pB2.start + 20,  aB2.start + 20,  aB2.start + 32);  // posición
        log(`  Spawn: X=${posX.toFixed(2)}, Y=${posY.toFixed(2)}, Z=${posZ.toFixed(2)} | Interior=${aInterior}`);
    } else {
        tempInterior.copy(pData, pB0.start + 188);
        tempTown.copy(pData,     pB0.start + 108);
        tempPos.copy(pData,      pB2.start + 20);
        log(`  Spawn seguro (plantilla): X=${tempX.toFixed(2)}, Y=${tempY.toFixed(2)}, Z=${tempZ.toFixed(2)}`);
    }

    // ----------------------------------------------------------------
    // BLOQUE 1: Script Globals (transferencia selectiva de misiones)
    // ----------------------------------------------------------------
    log('\n[BLOQUE 1] Script Globals (transferencia selectiva)...');
    const aB1 = getBlock(aData, aOffsets, 1);
    const pB1 = getBlock(pData, pOffsets, 1);

    const aCodeSize = aData.readUInt32LE(aB1.start);
    let   pCodeSize = pData.readUInt32LE(pB1.start);
    log(`  Código: Android=${aCodeSize.toLocaleString()} bytes | PC=${pCodeSize.toLocaleString()} bytes`);

    // Opción: reemplazar el code section del template con el de otro save PC (free-roam)
    // Esto elimina cualquier thread de misión activo que pueda quedar del template.
    // Útil cuando el template fue guardado DURANTE una misión (p.ej. SYND_6, Toreno).
    if (threadsFromPath && fs.existsSync(threadsFromPath)) {
        log(`  ℹ️ Cargando threads desde: ${threadsFromPath}`);
        const tFromData = Buffer.from(fs.readFileSync(threadsFromPath));
        const tFromOffsets = findBlocks(tFromData);
        const tFromB1 = getBlock(tFromData, tFromOffsets, 1);
        const tFromCodeSize = tFromData.readUInt32LE(tFromB1.start);
        if (tFromCodeSize === pCodeSize) {
            // Mismas versiones de SCM: reemplazar code section directamente
            tFromData.copy(pData, pB1.start + 4, tFromB1.start + 4, tFromB1.start + 4 + tFromCodeSize);
            log(`  ✅ Code section (threads) reemplazado (${tFromCodeSize} bytes) desde template libre`);
        } else {
            warn(`  Tamaño de code section diferente (${tFromCodeSize} vs ${pCodeSize}) - omitiendo reemplazo de threads`);
        }
    } else if (threadsFromPath) {
        warn(`  Archivo de threads no encontrado: ${threadsFromPath} - omitiendo`);
    }


    const aGlobalsStart = aB1.start + 4 + aCodeSize;
    const pGlobalsStart = pB1.start + 4 + pCodeSize;

    const aNumVars = Math.floor((aB1.end - aGlobalsStart) / 4);
    const pNumVars = Math.floor((pB1.end - pGlobalsStart) / 4);
    log(`  Variables: Android=${aNumVars} | PC=${pNumVars}`);

    // Paso 1: Transferir variables de progreso de misiones
    let copied = 0;
    for (const [varIdxStr, varName] of Object.entries(MISSION_PROGRESS_VARS)) {
        const varIdx = parseInt(varIdxStr);
        const aOff = aGlobalsStart + varIdx * 4;
        const pOff = pGlobalsStart + varIdx * 4;
        if (aOff + 4 > aB1.end || pOff + 4 > pB1.end) continue;
        aData.copy(pData, pOff, aOff, aOff + 4);
        copied++;
    }
    log(`  Variables de misiones transferidas: ${copied}`);

    // Paso 2: Resetear variables críticas a 0 SIEMPRE (no solo con --clean-pickups)
    // Estas variables tienen valores inválidos en Android que rompen la lógica de PC.
    let reset = 0;
    for (const [varIdxStr, varName] of Object.entries(RESET_TO_ZERO_VARS)) {
        const varIdx = parseInt(varIdxStr);
        const pOff = pGlobalsStart + varIdx * 4;
        if (pOff + 4 <= pB1.end) {
            pData.writeInt32LE(0, pOff);
            reset++;
        }
    }
    log(`  Variables críticas reseteadas a 0: ${reset} (incluyendo PROPERTY_BOUGHT_FLAGS y SAVE_PICKUPS)`);


    // Log de progreso transferido
    log('  --- Progreso de misiones ---');
    for (const [varIdxStr, varName] of Object.entries(MISSION_PROGRESS_VARS).sort((a,b)=>parseInt(a)-parseInt(b))) {
        const varIdx = parseInt(varIdxStr);
        const pOff = pGlobalsStart + varIdx * 4;
        if (pOff + 4 <= pB1.end) {
            const val = pData.readInt32LE(pOff);
            if (val !== 0) log(`    $${varIdx} ${varName} = ${val}`);
        }
    }

    // ----------------------------------------------------------------
    // BLOQUE 2: Player Ped (salud, armas, ropa, grasa/músculo)
    // ----------------------------------------------------------------
    log('\n[BLOQUE 2] Jugador...');

    // Salud y armadura
    aData.copy(pData, pB2.start + 32, aB2.start + 36, aB2.start + 44);
    const health = readFloat(aData, aB2.start + 36);
    const armor  = readFloat(aData, aB2.start + 40);
    log(`  Salud: ${health.toFixed(1)} | Armadura: ${armor.toFixed(1)}`);

    // Armas (13 slots × 28 bytes = 364 bytes)
    aData.copy(pData, pB2.start + 40, aB2.start + 44, aB2.start + 408);
    log('  Armas: copiadas (13 slots)');

    // Nivel de búsqueda
    pData[pB2.start + 424] = aData[aB2.start + 448];

    // Ropa equipada (112 bytes)
    aData.copy(pData, pB2.start + 428, aB2.start + 452, aB2.start + 564);

    // Grasa y músculo
    aData.copy(pData, pB2.start + 540, aB2.start + 564, aB2.start + 572);
    const fat  = readFloat(aData, aB2.start + 564);
    const musc = readFloat(aData, aB2.start + 568);
    log(`  Grasa: ${fat.toFixed(1)} | Músculo: ${musc.toFixed(1)}`);

    // ----------------------------------------------------------------
    // BLOQUE 3: Garajes
    // ----------------------------------------------------------------
    log('\n[BLOQUE 3] Garajes...');
    const aB3 = getBlock(aData, aOffsets, 3);
    const pB3 = getBlock(pData, pOffsets, 3);
    aData.copy(pData, pB3.start, aB3.start, aB3.end);
    log('  Garajes: copiados');

    // ----------------------------------------------------------------
    // BLOQUES DIRECTOS (misma estructura en ambas plataformas)
    // ----------------------------------------------------------------
    log('\n[BLOQUES DIRECTOS]');
    const safeBlocks = [
        [4, 'Configuración simple'],
        [8, 'Ubicaciones de reinicio (Hospital/Policía)'],
        [10, 'Zonas / Territorios de Bandas'],
        [11, 'Armas de Bandas'],
        [12, 'Generadores de Coches (Parked Cars)'],
        [17, 'Set Pieces'],
        [18, 'Zonas de Mapa/IPLs'],
        [19, 'Relaciones de Peds / Respeto de Bandas'],
        [20, 'Grafitis/Tags'],
        [21, 'IPLs de Interiores'],
        [24, 'Saltos Únicos'],
        [26, 'Radio']
    ];


    for (const [idx, desc] of safeBlocks) {
        const aB = getBlock(aData, aOffsets, idx);
        const pB = getBlock(pData, pOffsets, idx);
        aData.copy(pData, pB.start, aB.start, aB.end);
        log(`  Bloque ${idx} (${desc}): copiado`);
    }

    // ----------------------------------------------------------------
    // BLOQUE 6: Pickups (limpieza / copia de disquetes limpios)
    // ----------------------------------------------------------------
    if (cleanPickupsPath) {
        log(`\n[BLOQUE 6] Copiando pickups limpios desde: ${cleanPickupsPath}`);
        const cData = Buffer.from(fs.readFileSync(cleanPickupsPath));
        const cOffsets = findBlocks(cData);
        const cB6 = getBlock(cData, cOffsets, 6);
        const pB6 = getBlock(pData, pOffsets, 6);
        cData.copy(pData, pB6.start, cB6.start, cB6.end);
        log('  Pickups limpios copiados (iconos de guardado listos para recrear)');
    }

    // ----------------------------------------------------------------
    // BLOQUE 9: Radar Blips (175 blips × 40 bytes = 7000 bytes)
    // ----------------------------------------------------------------
    log('\n[BLOQUE 9] Radar Blips...');
    const aB9 = getBlock(aData, aOffsets, 9);
    const pB9 = getBlock(pData, pOffsets, 9);
    aData.copy(pData, pB9.start, aB9.start, aB9.start + 7000);
    log('  Blips copiados');

    // ----------------------------------------------------------------
    // BLOQUES 15 & 30: Dinero
    // ----------------------------------------------------------------
    log('\n[BLOQUES 15 & 30] Dinero...');
    const aB15 = getBlock(aData, aOffsets, 15);
    const pB15 = getBlock(pData, pOffsets, 15);
    aData.copy(pData, pB15.start, aB15.start, aB15.end);
    const pB30 = getBlock(pData, pOffsets, 30);
    aData.copy(pData, pB30.start, aB15.start, aB15.end);
    const money = aData.readInt32LE(aB15.start + 4);
    log(`  Dinero: $${money.toLocaleString()}`);

    // ----------------------------------------------------------------
    // BLOQUES 16 & 31: Estadísticas
    // ----------------------------------------------------------------
    log('\n[BLOQUES 16 & 31] Estadísticas...');
    const aB16 = getBlock(aData, aOffsets, 16);
    const pB16 = getBlock(pData, pOffsets, 16);
    aData.copy(pData, pB16.start, aB16.start, aB16.end);
    const pB31 = getBlock(pData, pOffsets, 31);
    aData.copy(pData, pB31.start, aB16.start, aB16.end);
    log('  Estadísticas copiadas');

    // ----------------------------------------------------------------
    // BLOQUES 17 & 32: Set Pieces (Duplicado en PC)
    // ----------------------------------------------------------------
    log('\n[BLOQUES 17 & 32] Duplicando Set Pieces...');
    const pB32 = getBlock(pData, pOffsets, 32);
    const aB17 = getBlock(aData, aOffsets, 17);
    aData.copy(pData, pB32.start, aB17.start, aB17.end);
    log('  Set Pieces duplicadas');


    // ----------------------------------------------------------------
    // BLOQUE 22: Shopping / Propiedades compradas
    // ----------------------------------------------------------------
    // NOTA IMPORTANTE: El Bloque 22 en Android tiene nEntries=0 (la gestión de propiedades
    // en Android usa un sistema diferente basado en flags de script, no en este bloque).
    // En PC, los pickups de compra se recrean dinámicamente por el thread BUY_PROP/BUY_ASSET.
    // Con $728 PROPERTY_BOUGHT_FLAGS reseteado a 0, el jugador puede comprar propiedades
    // que ya tenía en Android (necesario para que el sistema PC funcione correctamente).
    //
    // Estructura real del Bloque 22 (PC):
    //   4 bytes: nEntries (número de propiedades registradas)
    //   160 bytes * nEntries: datos de cada propiedad
    //   restante: cloth data y otros datos de shopping
    log('\n[BLOQUE 22] Shopping / Propiedades...');
    const aB22 = getBlock(aData, aOffsets, 22);
    const pB22 = getBlock(pData, pOffsets, 22);

    const aEntries22 = aB22.body.readUInt32LE(0);
    const pEntries22 = pB22.body.readUInt32LE(0);

    // Calcular offsets después de los arrays de propiedades (160 bytes cada una)
    const PROP_ENTRY_SIZE = 160;
    const aClothOffset = 4 + aEntries22 * PROP_ENTRY_SIZE;
    const pClothOffset = 4 + pEntries22 * PROP_ENTRY_SIZE;

    log(`  Block 22: Android nEntries=${aEntries22} | PC nEntries=${pEntries22}`);
    log(`  Offsets de cloth data: Android=${aClothOffset} | PC=${pClothOffset}`);

    if (aEntries22 === 0 && pEntries22 === 0) {
        // Ambos vacíos: copiar solo la sección de ropa (cloth/shopping)
        // que viene después del array de propiedades (en offset 4 en este caso)
        const clothSize = Math.min(aB22.body.length - aClothOffset, pB22.body.length - pClothOffset);
        if (clothSize > 0) {
            aB22.body.copy(pB22.body, pClothOffset, aClothOffset, aClothOffset + clothSize);
            // Los cambios en pB22.body se reflejan en pData porque son el mismo Buffer
            log(`  Cloth/Shopping data copiada: ${clothSize} bytes`);
        }
    } else if (aEntries22 > 0) {
        // Android tiene propiedades registradas: copiar hasta el tamaño de PC
        const copySize = Math.min(aB22.body.length, pB22.body.length);
        aB22.body.copy(pB22.body, 0, 0, copySize);
        // Forzar nEntries a lo que cabe en la plantilla PC
        if (aEntries22 > pEntries22 && pEntries22 > 0) {
            pB22.body.writeUInt32LE(pEntries22, 0);
            log(`  Aviso: Android tiene más propiedades (${aEntries22}) que la plantilla PC (${pEntries22}). Truncado.`);
        }
        log(`  Propiedades copiadas desde Android`);
    } else {
        log(`  Conservando Bloque 22 de la plantilla PC (Android sin propiedades registradas)`);
    }

    // ----------------------------------------------------------------
    // CHECKSUM FINAL
    // ----------------------------------------------------------------
    log('\n[CHECKSUM] Recalculando...');
    let checksum = 0;
    for (let i = 0; i < pData.length - 4; i++) {
        checksum = (checksum + pData[i]) & 0xFFFFFFFF;
    }
    pData.writeUInt32LE(checksum, pData.length - 4);
    log(`  Checksum: 0x${checksum.toString(16).toUpperCase().padStart(8,'0')}`);

    // ----------------------------------------------------------------
    // GUARDAR ARCHIVO
    // ----------------------------------------------------------------
    if (fs.existsSync(outputPath)) {
        const backupPath = outputPath + '.bak';
        log(`\nBackup: ${backupPath}`);
        if (fs.existsSync(backupPath)) fs.unlinkSync(backupPath);
        fs.renameSync(outputPath, backupPath);
    }

    fs.writeFileSync(outputPath, pData);

    log('\n' + '='.repeat(60));
    log(`✅ CONVERSIÓN COMPLETADA: ${outputPath}`);
    log('='.repeat(60));
}

// =============================================================================
// PUNTO DE ENTRADA
// =============================================================================
const args = process.argv.slice(2);
let androidFile  = null;
let templateFile = null;
let outputFile   = null;
let keepProps    = false;
let cleanPickups = null;
let threadsFrom  = null;


for (let i = 0; i < args.length; i++) {
    if      (args[i] === '--android'          && args[i+1]) { androidFile  = args[++i]; }
    else if (args[i] === '--template'         && args[i+1]) { templateFile = args[++i]; }
    else if (args[i] === '--output'           && args[i+1]) { outputFile   = args[++i]; }
    else if (args[i] === '--keep-properties')               { keepProps    = true; }
    else if (args[i] === '--clean-pickups'    && args[i+1]) { cleanPickups = args[++i]; }
    else if (args[i] === '--threads-from'     && args[i+1]) { threadsFrom  = args[++i]; }

    // Posicionales
    else if (!androidFile)  androidFile  = args[i];
    else if (!templateFile) templateFile = args[i];
    else if (!outputFile)   outputFile   = args[i];
}

if (!androidFile || !templateFile || !outputFile) {
    console.log('GTA SA Android → PC Save Converter');
    console.log('');
    console.log('Uso:');
    console.log('  node gta_sa_android_to_pc_converter.js --android <android.b> --template <plantilla_pc.b> --output <salida.b>');
    console.log('  node gta_sa_android_to_pc_converter.js --android <android.b> --template <plantilla_pc.b> --output <salida.b> --keep-properties');
    console.log('');
    console.log('Opciones:');
    console.log('  --keep-properties   Conserva propiedades de la plantilla PC (Bloque 22)');
    console.log('  --clean-pickups <clean_template.b> Copia pickups limpios de una plantilla de inicio (Bloque 6)');
    console.log('  --threads-from <free_roam.b>       Usa los threads de script de otro save PC en free-roam');
    console.log('                                     (Necesario si el template fue guardado durante una mision)');

    process.exit(1);
}

try {
    convert(androidFile, templateFile, outputFile, keepProps, cleanPickups, threadsFrom);

} catch(e) {
    err(e.message);
    process.exit(1);
}
