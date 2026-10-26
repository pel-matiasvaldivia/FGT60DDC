# PUESTA EN MARCHA — guía de rack

**Inventario real**: 1× FortiGate 60F · 2× Dell N3024 · 3× SMC8024L2

---

## 1. La decisión: el hardware bueno donde hacen falta VLANs

Los SMC son viejos, su soporte de etiquetado 802.1Q no está confirmado y son el
punto de riesgo para terminar hoy. Los Dell son modernos y su CLI es conocido.

> **Los SMC quedan PLANOS, sin VLANs. Solo transportan puestos (VLAN 10).**
> Todo lo que necesita etiquetado —uplink al firewall, access points, IoT— va
> sobre el Dell.

Con eso, la configuración de los SMC se reduce a: reset de fábrica + una IP.
No hay tagging que pueda fallar. Es lo que permite terminar hoy.

## 2. Topología

```
                    FortiGate 60F
          internal2 │                │ internal3
         TRUNK      │                │ TRUNK
    10,30,35,50,60  │                │ 20,25
    ┌───────────────┴──┐          ┌──┴──────────────┐
    │  SW-CORE-ACC     │          │     SW-SRV      │
    │  Dell N3024 #1   │          │  Dell N3024 #2  │
    │  10.10.60.2      │          │  10.10.25.2     │
    └─┬───┬───┬────────┘          └──┬───┬───┬──────┘
      │   │   │   p5-8  AP            │   │   │
      │   │   │   p9-13 IoT         PVE-01/02/03
      │   │   │   p14-24 puestos    VLAN 20,25,90,91
      │   │   │
  ┌───┘   │   └───┐      los 3 SMC son ACCESS VLAN 10
┌─┴────┐┌─┴────┐┌─┴────┐  (el Dell les pone la etiqueta)
│SMC-01││SMC-02││SMC-03│
│ 23 p ││ 23 p ││ 23 p │  = 69 puestos
└──────┘└──────┘└──────┘
```

**Puestos**: 69 (SMC) + 11 (Dell) = **80** · **AP**: 4 · **IoT**: 5

> Entra exacto, sin reserva. Para crecer hace falta otro switch. Queda anotado,
> no frena la puesta en marcha.

## 3. Mapa de puertos — SW-CORE-ACC (Dell N3024 #1)

| Puertos | Uso | Config |
|---|---|---|
| Gi1/0/1 | **Uplink al FortiGate `internal2`** | trunk 10,30,35,50,60 · nativa 999 |
| Gi1/0/2 | Downlink a SMC-01 | **access VLAN 10** |
| Gi1/0/3 | Downlink a SMC-02 | **access VLAN 10** |
| Gi1/0/4 | Downlink a SMC-03 | **access VLAN 10** |
| Gi1/0/5–8 | 4 Access Points | trunk 30,35 tagged · **nativa 60** |
| Gi1/0/9–13 | Impresoras / CCTV / IoT | access VLAN 50 |
| Gi1/0/14–24 | 11 puestos | access VLAN 10 |

Los cables de los **AP** y de las **impresoras** tienen que patchearse al Dell.
Los de los puestos van a cualquier boca libre de cualquier switch.

## 4. Direcciones

| Equipo | IP | VLAN |
|---|---|---|
| FortiGate (gateway de usuarios) | 10.10.10.1 | 10 |
| FortiGate (gestión) | 10.10.60.1 | 60 |
| SW-CORE-ACC (Dell #1) | **10.10.60.2** | 60 |
| SW-SRV (Dell #2) | **10.10.25.2** | 25 |
| SMC-01 / 02 / 03 | **10.10.10.2 / .3 / .4** | 10 |
| AP 1–4 | 10.10.60.21–.24 | 60 |

> Los SMC quedan administrados **dentro de la VLAN 10**, junto con los usuarios.
> No es lo ideal y conviene corregirlo más adelante; hoy es el precio de dejar
> los SMC sin configuración de VLANs. Poneles contraseña fuerte.

---

# SECUENCIA DE TRABAJO

Cada bloque termina con una verificación. **No avances si la verificación falla.**

## PASO 0 · Preparación (10 min)

- [ ] Cable de consola a mano para los dos Dell.
- [ ] Notebook con IP fija `192.168.1.50/24` para el FortiGate (puerto 1).
- [ ] Confirmar si los Dell son **N3024P** (con PoE). Si no lo son, los 4 AP
      necesitan **inyectores 802.3at**.
- [ ] Energía: los 6 equipos en UPS, no en zapatilla.

## PASO 1 · FortiGate (20 min)

- [ ] Conectar la notebook al **puerto 1** → `https://192.168.1.99`
- [ ] `execute backup config flash`
- [ ] Pegar `config/APLICAR-AHORA.conf` por secciones.
- [ ] Verificar:

```
execute ping 209.13.181.177
execute ping 8.8.8.8
diagnose sys sdwan health-check
show firewall policy | grep -e "edit " -e "set name"
```

✅ **Checkpoint**: el FortiGate llega a internet y la política 999 es la última.

## PASO 2 · SW-CORE-ACC — Dell N3024 #1 (20 min)

- [ ] Por consola: pegar `config/switches/dell-n3024-core-acceso.cfg`
- [ ] `copy running-config startup-config`
- [ ] Cablear **Gi1/0/1 → puerto 2 del FortiGate**
- [ ] Enchufar la notebook en **Gi1/0/14** (puesto)

✅ **Checkpoint**: la notebook toma `10.10.10.x` por DHCP y **navega**.

> Si no toma IP: `show vlan` en el Dell, y en el FortiGate
> `diagnose sniffer packet internal2 'vlan 10' 4 0 a`

## PASO 3 · Los 3 SMC (15 min — los tres juntos)

Lo mínimo posible, a propósito.

- [ ] **Reset de fábrica** en cada uno. Por web: `SYSTEM → Factory Default`.
      Esto borra el `10.10.60.11` y la VLAN 10 que ya tocaste: es lo que
      queremos, quedan planos.
- [ ] Reconectar por la IP de fábrica (suele ser `192.168.2.10`, ver etiqueta).
- [ ] `SYSTEM → IP Configuration`:
      - SMC-01 → `10.10.10.2` / `255.255.255.0` / GW `10.10.10.1`
      - SMC-02 → `10.10.10.3` · SMC-03 → `10.10.10.4`
- [ ] `RSTP` → **Enabled** (dejar prioridad por defecto; la raíz es el Dell).
- [ ] `SECURITY → User Accounts` → cambiar la contraseña de `admin`.
- [ ] **Guardar** (`Save Configuration` / `Copy running to startup`).
- [ ] Cablear el **puerto 24** de cada SMC a **Gi1/0/2, 3 y 4** del Dell.

✅ **Checkpoint**: notebook en el puerto 1 de cada SMC → toma `10.10.10.x` y
navega. Desde ahí, `ping 10.10.10.2`, `.3` y `.4`.

> **No configures VLANs en los SMC.** Si en algún momento ves una pantalla de
> VLAN, salí. El Dell hace todo el trabajo de etiquetado.

## PASO 4 · Access Points e impresoras (15 min)

- [ ] Patchear los 4 AP a **Gi1/0/5–8** (con inyector PoE si los Dell no son P).
- [ ] Patchear impresoras/CCTV a **Gi1/0/9–13**.
- [ ] En cada AP: SSID corporativo → VLAN **30**, SSID invitados → VLAN **35**.
      La administración del AP queda sin etiqueta y toma IP `10.10.60.x`.

✅ **Checkpoint**: cliente en el SSID corporativo toma `10.10.30.x` y navega.
Cliente en invitados toma `10.10.35.x`, navega y **no** llega a `10.10.10.x`.

## PASO 5 · Puestos (30 min)

- [ ] Patchear los 80 puestos: 69 en los SMC (puertos 1–23), 11 en el Dell
      (Gi1/0/14–24).
- [ ] Probar 4 o 5 al azar, de switches distintos.

✅ **Checkpoint**: todos toman IP y navegan.

## PASO 6 · Cierre del día (15 min)

- [ ] `copy running-config startup-config` en los dos Dell.
- [ ] Guardar config en los 3 SMC.
- [ ] En el FortiGate: `execute backup config flash` y backup externo.
- [ ] Desarmar el acceso temporal del puerto 4 (sección 11 de `APLICAR-AHORA.conf`).
- [ ] Anotar en papel qué puesto quedó en qué switch y puerto.

## PASO 7 · Servidores — cuando lleguen los R720 (no es para hoy)

- [ ] `config/switches/dell-n3024-servidores.cfg` en el Dell #2
- [ ] Cablear Gi1/0/24 → **puerto 3 del FortiGate**
- [ ] Seguir `proxmox/README.md`

---

# SI ALGO NO ANDA

| Síntoma | Primero mirá |
|---|---|
| Un puesto no toma IP | ¿El puerto del Dell es access VLAN 10? `show vlan` |
| Nadie toma IP | El uplink Gi1/0/1: `show interfaces switchport Gi1/0/1`. En el FortiGate: `diagnose sniffer packet internal2 'vlan 10' 4 0 a` |
| Toma IP pero no navega | `diagnose sys sdwan health-check` y la política 10 |
| Toma IP pero resuelve mal | DNS del scope: apunta a `10.10.10.1` hasta que exista el AD |
| El WiFi corporativo no anda | ¿El AP etiqueta la VLAN 30? ¿El puerto del Dell permite 30 tagged? |
| Todo lento o intermitente | Bucle. `show spanning-tree` en el Dell: ¿aparece un puerto bloqueado inesperado? |
| Perdiste acceso al FortiGate | Puerto 1, `192.168.1.99`. Nunca se toca. |

**Comando que más sirve en el FortiGate**, para ver por qué un paquete no pasa:

```
diagnose debug reset
diagnose debug flow filter addr 10.10.10.50
diagnose debug flow show function-name enable
diagnose debug flow trace start 20
diagnose debug enable
   ... generar tráfico ...
diagnose debug disable
```

---

# LO QUE QUEDA PENDIENTE (anotarlo, no frena hoy)

1. **Cero puertos de reserva.** Entra exacto. Cualquier crecimiento necesita otro switch.
2. **Los SMC se administran en la VLAN 10**, junto con los usuarios. Corregible más adelante.
3. **Zona horaria del FortiGate** sigue sin definir: `set timezone ?`
4. **Licencia UTP**: registrar en FortiCare ahora que hay internet.
5. **Datos del túnel SAP** pendientes del proveedor.
6. **Claro**: cuando esté, habilitar el miembro 2 de SD-WAN.
7. **Sin segundo FortiGate**, el equipo es punto único de falla.
8. **Los SMC son el eslabón más viejo**: presupuestar reemplazo.
