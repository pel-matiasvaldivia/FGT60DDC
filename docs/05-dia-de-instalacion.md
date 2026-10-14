# 05 — Día de la instalación: qué conectar y en qué orden

El FortiGate queda configurado en el banco con
[`config/fortigate-60f-puesta-a-punto.conf`](../config/fortigate-60f-puesta-a-punto.conf).
Este documento es lo que se hace después, con el equipo ya configurado.

## 1. Mapa de conexión física

```
   ┌──────────────────────────────────────────────────────────────┐
   │                     FortiGate 60F                             │
   │                                                               │
   │  WAN1 ──── ONT Telefónica (bridge)      209.13.171.178/29     │
   │  WAN2 ──── (libre, Claro a futuro)                            │
   │  DMZ  ──── (libre, sin IP)                                    │
   │                                                               │
   │  1 ─── notebook de soporte / rescate    192.168.1.99          │
   │  2 ─── TRUNK → SW-ACCESO       VLAN 10,30,35,50,60 tagged     │
   │  3 ─── TRUNK → SW-SERVIDORES   VLAN 20,25 tagged              │
   │  4 ─── (libre)                                                │
   │  5 ─── (libre)                                                │
   │  A/B ── FortiAP/FortiSwitch si se usan (fortilink)            │
   └──────────────────────────────────────────────────────────────┘
```

## 2. Configuración que hay que hacer en los switches

El FortiGate puede estar perfecto: si el trunk del switch no deja pasar los tags
correctos, no circula nada. Es la causa número uno de "lo configuré y no anda".

### Switch de ACCESO (puerto hacia `internal2` del FortiGate)

| VLAN | Modo en el puerto del trunk | Dónde más |
|---|---|---|
| 10 USERS | tagged | access en los 80 puestos |
| 30 WIFI-CORP | tagged | tagged en los puertos de los AP |
| 35 WIFI-GUEST | tagged | tagged en los puertos de los AP |
| 50 IOT | tagged | access en impresoras, CCTV, UPS |
| 60 MGMT | tagged | **native/untagged** en los puertos de los AP y de gestión de switches |

Los puertos de los AP son un caso mixto: **trunk** con VLAN 30 y 35 tagged (los
SSID) y VLAN 60 nativa (la propia administración del AP).

### Switch de SERVIDORES (puerto hacia `internal3` del FortiGate)

| VLAN | En el trunk al FortiGate | En los puertos de los nodos |
|---|---|---|
| 20 SERVERS | tagged | tagged (tráfico de las VMs) |
| 25 PVE-MGMT | tagged | access o tagged (admin de los nodos) |
| **90 CLUSTER** | **NO incluir** | access (corosync) |
| **91 STORAGE** | **NO incluir** | access, MTU 9000 |

Las VLAN 90 y 91 **no deben estar en el trunk hacia el FortiGate**. Si alguien
las agrega "por las dudas", el tráfico de cluster empieza a tener un camino hacia
el firewall y se pierde la garantía del diseño. Ver [doc 03](03-proxmox-cluster.md).

Además, en el switch de servidores:

- `portfast` / `edge-port` en los puertos de los nodos (un STP lento al levantar
  un link puede hacer perder quorum durante un reinicio).
- Sin storm control agresivo ni rate limit en los puertos de VLAN 90.
- MTU 9000 en los puertos de VLAN 91, de punta a punta.

## 3. Orden de encendido y conexión

1. ⬜ Conectar el notebook al **puerto 1** y verificar acceso a `https://192.168.1.99`.
2. ⬜ Conectar **WAN1** al ONT de Telefónica (en modo bridge, no NAT).
   - `execute ping 209.13.171.177` → gateway
   - `execute ping 8.8.8.8` → internet
   - `diagnose sys sdwan health-check` → SLA en verde
3. ⬜ **Registrar el equipo en FortiCare y activar la licencia UTP/ATP.** Recién
   ahora hay internet para hacerlo. Sin esto, AV/IPS/WebFilter no funcionan
   aunque las políticas los referencien.
   - `diagnose autoupdate versions` → confirmar que bajan las firmas
4. ⬜ Conectar el **puerto 2** al trunk del switch de acceso. Probar con un
   notebook en un puerto access de VLAN 10: debe tomar `10.10.10.x` y navegar.
5. ⬜ Conectar el **puerto 3** al trunk del switch de servidores.
6. ⬜ Levantar los AP y probar ambos SSID, incluido el roaming entre los 4.
7. ⬜ Levantar los nodos Proxmox y armar el cluster ([doc 03](03-proxmox-cluster.md)).
8. ⬜ Levantar el túnel IPsec a SAP (si ya están los datos del proveedor).
9. ⬜ Probar **cada fila** de la matriz de tráfico, incluidos los deny.
10. ⬜ Etapa 9 del script: endurecimiento (trusthosts, puerto admin).
11. ⬜ `execute backup config flash` + backup externo por TFTP.

## 4. Pruebas que no hay que saltear

| Prueba | Resultado esperado |
|---|---|
| Invitado hacia `10.10.20.10` | Bloqueado y logueado (política 12) |
| Impresora hacia internet | Bloqueado y logueado (política 61) |
| Desktop → internet | Navega, con AV/IPS/WebFilter aplicando |
| Desktop → VM en VLAN 20 | Solo los puertos del grupo `GRP-SERVIDORES-LAN` |
| Apagar un nodo Proxmox | Cluster mantiene quorum (2/3) |
| Desconectar la NIC de corosync | Cluster sigue por ring1, sin reinicios |
| Desconectar WAN1 (con Claro activo) | Internet por WAN2 en < 15 s |

## 5. Lo que queda pendiente después de la instalación

- **Claro**: habilitar el miembro 2 de SD-WAN (bloque comentado en la ETAPA 4).
- **Segundo túnel IPsec** sobre Claro, previa autorización de la IP por el
  proveedor de SAP.
- **Deep SSL inspection**: certificado del FortiGate por GPO + exclusiones de
  SAP, homebanking y AFIP.
- **Segundo FortiGate en HA**: hoy el equipo es punto único de falla para
  internet, SAP y el ruteo entre VLANs.
- **Acotar la política 50**: `NET-USERS` completa puede administrar Proxmox;
  conviene reducirlo a un grupo de IPs de soporte.
