# 08 — Switches de acceso SMC8024L2: diseño y advertencias

Configuración: [`config/switches/smc8024l2-acceso.cfg`](../config/switches/smc8024l2-acceso.cfg)

Los switches de acceso (los que van al **puerto 2 / `internal2`** del FortiGate)
son **4 × SMC TigerSwitch SMC8024L2**, de 24 puertos gigabit, capa 2
administrable. El switch de servidores (puerto 3 / `internal3`) sigue siendo el
Dell N3024 del [doc 06](06-switches-dell-n3024.md).

## 1. Lo primero: verificar qué firmware tienen

El SMC8024L2 usa un CLI de base **Accton**, parecido al de Cisco pero no igual, y
**cambia entre versiones de firmware**. La configuración que entrego está escrita
en ese dialecto, pero es una plantilla, no un volcado de tus equipos.

```
show version
show system
show running-config
```

Probá **un comando de cada bloque** antes de pegar el bloque entero. Donde hay
variantes conocidas las dejé anotadas como `ALTERNATIVA` dentro del archivo.

Si el CLI difiere mucho, estos switches tienen **interfaz web** y el orden lógico
es el mismo: crear las VLANs → asignar los puertos → poner la IP de gestión.

## 2. Problema de capacidad: no sobra ni un puerto

| Concepto | Puertos |
|---|---|
| 80 desktops | 80 |
| 4 access points | 4 |
| Impresoras / CCTV / IoT | 5 |
| Uplink al FortiGate | 1 |
| Downlinks entre switches | 3 |
| **Total ocupado** | **93** |
| Disponible (4 × 24) | 96 |
| **Reserva real** | **3 puertos** |

Y esos 3 están repartidos, no juntos. En la práctica: **cero margen**.

Qué significa en el día a día: no hay boca para un visitante, para un equipo
nuevo, para un switch de escritorio en una sala de reuniones, ni para mover un
puesto sin desconectar otro. Y si un switch falla, 24 personas quedan sin red y
no hay dónde reubicarlas.

Tres salidas, en orden de preferencia:

1. **Un quinto switch** (24 puertos más de reserva). Es lo sensato.
2. **Usar los puertos SFP/combo** para los uplinks entre switches, si estos
   equipos los tienen —verificar con `show interfaces status`—, lo que libera 4
   bocas de cobre.
3. **Aceptarlo y dejarlo documentado**, avisando al cliente que cualquier
   crecimiento requiere hardware.

## 3. Topología: estrella, no cascada

```
                   FortiGate internal2
                          │ TRUNK 10,30,35,50,60
                   ┌──────┴──────┐
                   │  SW-ACC-01  │  p24 uplink · p21-23 downlink
                   └──┬────┬────┬┘  p1-16 puestos · p17-20 AP
          ┌───────────┘    │    └───────────┐
    ┌─────┴─────┐    ┌─────┴─────┐    ┌─────┴─────┐
    │ SW-ACC-02 │    │ SW-ACC-03 │    │ SW-ACC-04 │
    └───────────┘    └───────────┘    └───────────┘
```

Con la misma cantidad de puertos que una cascada, la estrella es mejor: si cae
`SW-ACC-03`, quedan sin red **sus** 23 puestos y nada más. En cascada, todo lo
que cuelga detrás cae también.

`SW-ACC-01` concentra el uplink y los AP. Por eso se lo fuerza como **raíz del
spanning tree** (`spanning-tree priority 4096`): si la raíz quedara en otro
switch, el tráfico hacia el firewall daría vueltas de más.

## 4. Riesgos de estos equipos, dichos claro

El SMC8024L2 es un switch **descontinuado hace años**. Vale ponerlo por escrito
antes de montarlo como base de la red de 80 personas:

| Riesgo | Detalle |
|---|---|
| **Sin PoE** | Los 4 AP necesitan **inyectores 802.3at**. Un AP 802.11ax usa 15–20 W |
| **Sin stack** | Cada switch se administra y se actualiza por separado: 4 IPs, 4 configs, 4 backups |
| **Sin repuestos** | SMC Networks ya no da soporte. Fuentes y ventiladores sin reemplazo oficial |
| **Sin actualizaciones** | No hay firmware nuevo: los bugs que tenga, quedan |
| **RSTP incierto** | Según firmware puede soportar solo 802.1D clásico (converge en ~30 s en vez de ~2 s) |
| **Edad** | Son equipos de hace más de 15 años; los capacitores de la fuente son el punto débil típico |

No es un impedimento para arrancar: funcionan y hacen VLANs, que es lo que el
diseño necesita. Pero conviene que el cliente sepa que **son el eslabón más
viejo de toda la instalación**, y presupuestar su reemplazo como una etapa 2 —
antes de que falle uno y haya que resolverlo con urgencia.

## 5. Mapa de VLANs por puerto

| Puerto | Modo | VLAN |
|---|---|---|
| Uplink al FortiGate (`SW-ACC-01` p24) | trunk | 10,30,35,50,60 tagged · nativa 999 |
| Downlinks entre switches (p21-23) | trunk | idem |
| Puestos | access | 10 untagged |
| Access points | hybrid | **60 untagged (nativa)** + 30,35 tagged |
| Impresoras / IoT | access | 50 untagged |
| Gestión del switch | — | IP en VLAN 60 (`.11` a `.14`) |

### El puerto del AP es el único raro

Los SSID viajan **etiquetados** (VLAN 30 y 35) porque el AP decide a qué VLAN
pertenece cada cliente según el SSID al que se asoció. La administración del
propio AP va **sin etiqueta** en la VLAN 60: así toma IP apenas se enchufa, sin
configuración previa.

## 6. Dos detalles del CLI que rompen cosas

**El orden de los comandos de VLAN importa.** Siempre:

```
switchport allowed vlan add 10 untagged     ← primero agregar
switchport native vlan 10
switchport allowed vlan remove 1            ← después sacar la 1
```

Si se invierte, el puerto se queda sin ninguna VLAN y el enlace se corta. En el
puerto por el que estás conectado, eso significa perder la sesión.

**Mover la gestión de VLAN 1 a VLAN 60 te desconecta.** Es el último paso de la
configuración y conviene hacerlo **por consola serie**. Después del cambio, el
switch solo responde desde la VLAN 60 o a través del FortiGate.

## 7. IPs de gestión

| Equipo | IP |
|---|---|
| SW-ACC-01 | `10.10.60.11` |
| SW-ACC-02 | `10.10.60.12` |
| SW-ACC-03 | `10.10.60.13` |
| SW-ACC-04 | `10.10.60.14` |
| AP 1–4 | `10.10.60.21` – `.24` |
| iDRAC PVE-01/02/03 | `10.10.60.31` – `.33` |
| Gateway (FortiGate) | `10.10.60.1` |

## 8. Orden de puesta en marcha

1. ⬜ `show version` en los 4 → anotar firmware y confirmar el dialecto del CLI.
2. ⬜ Backup de la config actual de cada uno (`show running-config` y guardarlo).
3. ⬜ Bloques 1 y 2 (VLANs + STP) en los 4, por consola.
4. ⬜ Bloque 3 en `SW-ACC-01`, bloque 4 en los otros tres.
5. ⬜ Cablear los downlinks p21-23 de `SW-ACC-01` a los p24 de los otros.
6. ⬜ Cablear el p24 de `SW-ACC-01` al **puerto 2 del FortiGate**.
7. ⬜ Probar: notebook en un puerto de puestos → IP `10.10.10.x` y navegación.
8. ⬜ IPs de gestión (último paso, por consola).
9. ⬜ Bloque 5 (contraseñas, HTTPS, SNTP, logs).
10. ⬜ `copy running-config startup-config` en los 4. **Sin esto se pierde todo
    al reiniciar.**

## 9. Prueba que no hay que saltear

Desconectá y reconectá un downlink mientras alguien navega. La red tiene que
seguir, y `show spanning-tree` no debe mostrar puertos bloqueados que no
correspondan. Si el firmware solo tiene 802.1D, la reconvergencia puede tardar
~30 segundos: es esperable, pero conviene saberlo antes de que pase en
producción y parezca una falla.
