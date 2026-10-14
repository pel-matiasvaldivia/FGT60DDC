# 01 — Diseño y layout de conexión

## 1. Premisas del proyecto

| Ítem | Dato |
|---|---|
| Firewall | FortiGate 60F (10 x GE RJ45: WAN1, WAN2, DMZ, A, B, 1–5) |
| Usuarios | 80 desktops |
| WLAN | 4 Access Points (corporativa + invitados) |
| Aplicación | SAP accedido por túnel IPsec site-to-site |
| ISP 1 | Telefónica — **activo hoy** en WAN1, `209.13.171.178/29`, GW `209.13.171.177`, DNS `200.0.243.10` / `200.0.243.11` |
| ISP 2 | Claro — **pendiente de alta**, se reserva WAN2 (diseño ya preparado para SD-WAN) |
| Servidores | Red dedicada para cluster Proxmox VE |

### Advertencias de diseño

1. **Gateway inconsistente**: ver README. Se asume `209.13.171.177`.
2. **Un solo FortiGate 60F = punto único de falla.** Si el negocio depende de SAP,
   presupuestar un segundo 60F para HA FGCP (A-P) en una etapa 2. El diseño de
   VLANs/políticas no cambia al agregarlo.
3. **El 60F no es un switch de campus.** Los 80 puestos, los AP y los nodos Proxmox
   se conectan a switches administrables; el FortiGate sólo rutea/inspecciona entre VLANs.
4. **El tráfico de cluster (corosync/storage/migración) NO debe pasar por el FortiGate.**
   Se mantiene en VLANs sin interfaz ruteada, puro L2 en el switch. Ver doc 03.
5. **Licencia**: para AV/IPS/WebFilter/AppControl hace falta bundle UTP/ATP vigente.

---

## 2. Layout físico de conexión

```
                 ┌───────────────┐          ┌───────────────┐
                 │  TELEFONICA   │          │     CLARO     │
                 │ 209.13.171.178│          │  (pendiente)  │
                 │ /29  GW .177  │          │               │
                 └───────┬───────┘          └───────┬───────┘
                         │ ONT/Modem                │ ONT/Modem
                         │ (modo bridge)            │ (modo bridge)
                    WAN1 │                     WAN2 │
                 ┌───────┴──────────────────────────┴───────┐
                 │          FortiGate 60F                    │
                 │  SD-WAN zone "SDWAN" (wan1 primario)      │
                 │  IPsec "VPN-SAP"  ·  NGFW/UTP             │
                 │                                           │
                 │  port1(TRUNK)   port2(TRUNK)   port5(MGMT) │
                 └──────┬──────────────┬──────────────┬───────┘
                        │ 802.1Q       │ 802.1Q       │ 10.10.60.x
                        │ VLAN         │ VLAN         │ (consola/OOB)
                        │ 10,30,35,50,60              │
            ┌───────────┴───────────┐  │        ┌─────┴──────┐
            │  SW-CORE / ACCESO     │  │        │ Notebook   │
            │  (2 x 48p PoE+ ó      │  │        │ de soporte │
            │   3 x 24p, apilados)  │  │        └────────────┘
            └─┬─────────┬─────────┬─┘  │
              │         │         │    │
   ┌──────────┴──┐  ┌───┴────┐ ┌──┴──────────┐
   │ 80 Desktops │  │ 4 x AP │ │ Impresoras  │
   │  VLAN 10    │  │ PoE+   │ │ CCTV / IoT  │
   │             │  │ VLAN60 │ │  VLAN 50    │
   └─────────────┘  │ mgmt   │ └─────────────┘
                    │ SSIDs: │
                    │ V30 corp / V35 guest
                    └────────┘
                                     │
                        ┌────────────┴─────────────────────────┐
                        │   SW-SERVIDORES (L2, idealmente 10G) │
                        │   VLANs 20,25 (ruteadas por FGT)     │
                        │   VLANs 90,91 (SOLO L2, no ruteadas) │
                        └──┬──────────┬──────────┬─────────────┘
                           │          │          │
                      ┌────┴───┐ ┌────┴───┐ ┌────┴───┐
                      │ PVE-01 │ │ PVE-02 │ │ PVE-03 │   Cluster Proxmox
                      │        │ │        │ │        │   (quorum con 3 nodos)
                      └────────┘ └────────┘ └────────┘
                       VMs en VLAN 20 · mgmt VLAN 25
                       corosync VLAN 90 · storage/migración VLAN 91
```

### Asignación de puertos del FortiGate 60F

| Puerto | Rol | Configuración |
|---|---|---|
| WAN1 | ISP Telefónica | `209.13.171.178/29`, GW `209.13.171.177`, miembro SD-WAN prioridad 1 |
| WAN2 | ISP Claro (futuro) | reservado, miembro SD-WAN prioridad 2 |
| DMZ | Servicios publicados (opcional) | `10.10.70.1/24` si se publica algo a internet |
| internal1 | **Puerto de rescate** — queda en la interfaz `internal` de fábrica | `192.168.1.99/24`, se reconfigura al final |
| internal2 | **Trunk 802.1Q** a SW-CORE | VLANs 10, 30, 35, 50, 60 |
| internal3 | **Trunk 802.1Q** a SW-SERVIDORES | VLANs 20, 25 |
| internal4–5 | Libres / crecimiento / 2º link LACP | — |
| A / B | FortiLink (si se usan FortiSwitch) | opcional |

> **Verificado en el equipo del proyecto (FortiOS 7.2.6):** la interfaz `internal`
> es de tipo *VLAN Switch* y su único miembro es `internal1`. Los puertos
> `internal2` a `internal5` ya están libres, así que **no hay que desarmar ningún
> switch ni cortar servicio** para crear las VLANs. Confirmar con
> `show system virtual-switch` y `get system interface physical | grep -A1 internal`.

---

## 3. Plan de VLANs y direccionamiento

Plan base **10.10.0.0/16**, una /24 por VLAN (fácil de leer, sobra espacio).

| VLAN | Nombre | Subred | Gateway (FGT) | DHCP | Uso |
|---:|---|---|---|---|---|
| 10 | USERS | 10.10.10.0/24 | 10.10.10.1 | 10.10.10.50–230 | 80 desktops |
| 20 | SERVERS | 10.10.20.0/24 | 10.10.20.1 | no (fijo) | VMs: SAP GUI/router, AD/DNS, file, apps |
| 25 | PVE-MGMT | 10.10.25.0/24 | 10.10.25.1 | no (fijo) | Interfaz web/SSH de los nodos Proxmox |
| 30 | WIFI-CORP | 10.10.30.0/24 | 10.10.30.1 | 10.10.30.50–230 | SSID corporativo (WPA2/3-Enterprise o PSK) |
| 35 | WIFI-GUEST | 10.10.35.0/24 | 10.10.35.1 | 10.10.35.50–230 | SSID invitados, **sólo internet** |
| 50 | IOT-PRINT | 10.10.50.0/24 | 10.10.50.1 | reserva por MAC | Impresoras, CCTV, control de acceso, UPS |
| 60 | MGMT | 10.10.60.0/24 | 10.10.60.1 | no (fijo) | Switches, AP, iLO/iDRAC, FortiGate OOB |
| 70 | DMZ | 10.10.70.0/24 | 10.10.70.1 | no | Sólo si se publica algún servicio |
| 90 | PVE-CLUSTER | 10.10.90.0/24 | **sin gateway** | no | corosync ring0 — **L2 puro, no ruteada** |
| 91 | PVE-STORAGE | 10.10.91.0/24 | **sin gateway** | no | Storage/replicación/migración — **L2 puro** |

Direcciones fijas sugeridas (ejemplo):

| Host | IP |
|---|---|
| PVE-01 / 02 / 03 (mgmt) | 10.10.25.11 / .12 / .13 |
| PVE-01/02/03 corosync | 10.10.90.11 / .12 / .13 |
| PVE-01/02/03 storage | 10.10.91.11 / .12 / .13 |
| DC / DNS interno | 10.10.20.10 |
| SAP router / app local | 10.10.20.20 |
| Switch core / servidores | 10.10.60.2 / .3 |
| AP 1–4 | 10.10.60.21–.24 |

### Reglas de no-superposición con SAP

Antes de cerrar el plan, confirmar con el proveedor SAP qué redes anuncia por el túnel.
Si SAP usa 10.10.x.x, cambiar el plan local a **172.21.0.0/16** (mismo esquema, mismo
tercer octeto por VLAN). Un solapamiento obliga a NAT dentro del túnel y complica todo.

---

## 4. Matriz de tráfico (qué se permite)

| Origen | Destino | Servicios | Inspección | Nota |
|---|---|---|---|---|
| USERS (10) | Internet (SDWAN) | HTTP/S, DNS, NTP + general | AV, IPS, WebFilter, AppCtrl, DNSFilter, SSL cert-inspection | NAT overload |
| USERS (10) | SERVERS (20) | SMB, RDP(ctrl), HTTP/S, LDAP/Kerberos, DNS, 3200/3300/3299 | IPS | Lo mínimo necesario |
| USERS (10) | VPN-SAP | Puertos SAP (3200/3299/3300, 443, 8000, 44300, 50000-50099) | IPS | Según lo que publique el proveedor |
| SERVERS (20) | VPN-SAP | Según integración (RFC, DB, HTTPS) | IPS | Interfaces/BW de SAP |
| SERVERS (20) | Internet | HTTP/S, DNS, NTP (lista blanca) | AV, IPS | Updates y licencias; no navegación libre |
| WIFI-CORP (30) | = USERS | igual que USERS | igual | Opcional: sólo internet + apps web |
| WIFI-GUEST (35) | Internet | HTTP/S, DNS | WebFilter, AppCtrl, shaper | **Deny** a toda red interna |
| IOT-PRINT (50) | USERS/SERVERS | 9100/631/515, HTTP/S del DVR | — | **Deny** a internet (salvo NVR específico) |
| MGMT (60) | FGT/switches/AP | SSH, HTTPS, SNMP, CAPWAP | — | Acceso admin sólo desde acá |
| Cualquiera | VLAN 90/91 | — | — | **No ruteadas: sin política = sin acceso** |
| VPN-SAP | SERVERS/USERS | sólo lo que SAP necesite iniciar | IPS | Normalmente muy acotado o nada |

Todo lo no listado queda en el **deny implícito con logging** al final.

---

## 5. Doble ISP — estrategia

**Hoy (sólo Telefónica):** se crea igual la zona SD-WAN con wan1 como único miembro.
Cuando llegue Claro, se agrega wan2 como miembro y las políticas **no se tocan**
(apuntan a la zona, no a la interfaz).

- Health-check por ICMP/HTTPS a `200.0.243.10`, `1.1.1.1` y `8.8.8.8` (más de un
  destino para no confundir caída de ISP con caída de un destino).
- Regla de servicio en modo *priority*: wan1 primero, wan2 standby (Claro suele ser
  el enlace económico/respaldo). Si Claro termina siendo mejor, se puede pasar a
  balanceo por SLA para navegación y dejar SAP siempre por el enlace estable.
- **Rutas default**: una por miembro, misma distancia (10), SD-WAN decide.

### IPsec a SAP con doble ISP

El túnel se monta sobre **wan1**. El peer remoto autoriza por IP pública, así que:

1. Pedir al proveedor de SAP que autorice **también** la IP pública de Claro.
2. Montar un **segundo túnel** `VPN-SAP-BKP` sobre wan2, mismas propuestas.
3. Rutas estáticas a las redes de SAP: distancia 10 por el túnel primario,
   distancia 20 por el de respaldo (o SD-WAN rule con los dos túneles como miembros).

Si el proveedor sólo acepta una IP, SAP queda sin redundancia de enlace — hay que
decírselo al cliente por escrito.

---

## 6. WLAN (4 AP)

Dos opciones:

- **FortiAP** (recomendado por integración): el 60F es el controlador. AP en VLAN 60
  con `allowaccess capwap` o descubrimiento por FortiLink. SSIDs en modo *tunnel*
  (tráfico al FGT) o *bridge* con VLAN 30/35 (menos carga en el FGT, preferido para
  80 usuarios con 1 Gbps).
- **AP de terceros** (UniFi, Omada, etc.): el FGT sólo rutea. Los SSID se mapean a
  VLAN 30 y 35 en el AP; el puerto del switch va como trunk con VLAN 60 nativa.

SSIDs sugeridos:

| SSID | VLAN | Seguridad | Notas |
|---|---|---|---|
| `CLIENTE-CORP` | 30 | WPA2/3-Enterprise (RADIUS/NPS contra AD) o PSK fuerte | Equipos de la empresa |
| `CLIENTE-WIFI` | 35 | WPA2-PSK + portal cautivo | Aislamiento de clientes, shaper 20/10 Mbps |

PoE: 4 AP → switch PoE+ (802.3at) o inyectores. Un AP 802.11ax ronda 15–20 W.

---

## 7. Seguridad de administración del FortiGate

- Cambiar `admin`, crear usuario nominal por administrador, MFA (FortiToken) si es posible.
- Puerto HTTPS admin en 8443, **HTTP y Telnet deshabilitados**.
- `trusthost` restringido a 10.10.60.0/24 y 10.10.10.0/24.
- **Nunca** `allowaccess https/ssh` en wan1. Para acceso remoto: IPsec dial-up o
  SSL-VPN con MFA, nunca la GUI expuesta.
- Backup de configuración antes y después de cada cambio (`execute backup config`).
- Logging a disco + FortiAnalyzer/syslog si existe; NTP a `ar.pool.ntp.org`.
