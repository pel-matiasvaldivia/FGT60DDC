# 07 — Direccionamiento del cluster Proxmox: correcciones al README

Revisión del `README.md` del cluster (3× Dell PowerEdge R720, Proxmox VE 9.x)
contra el plan de red del proyecto FT-60F-DDC.

## 1. Veredicto: hay que cambiar las IPs

| Red en el README | Subred | Estado |
|---|---|---|
| Management / VMs | `192.168.10.0/24` | **Cambiar** — no existe en el plan; el FortiGate no la rutea |
| **Corosync** | `10.10.10.0/24` | **COLISIÓN** — es la VLAN 10 USERS (FortiGate `10.10.10.1`) |
| **Ceph** | `10.10.20.0/24` | **COLISIÓN** — es la VLAN 20 SERVERS (FortiGate `10.10.20.1`) |

Las dos colisiones son con redes que el FortiGate **ya tiene configuradas como
gateway**. Si se levanta el cluster con esos valores:

- Los nodos se creen en la misma red L2 que los 80 puestos de trabajo y que las
  VMs, pero están en una VLAN distinta: el ARP no resuelve y corosync no forma
  quórum. El síntoma es un cluster que "a veces" anda.
- Cualquier VM en VLAN 20 con IP `10.10.20.11` duplica la IP de Ceph de `pve1`.
- El FortiGate rechaza crear interfaces con subredes superpuestas, así que el
  error aparecería recién en el nodo, no en el firewall.

## 2. Mapeo correcto

| Función | README original | **Valor correcto** | VLAN | ¿Ruteada por el FGT? |
|---|---|---|---|---|
| Management de los nodos | `192.168.10.x` | **`10.10.25.x`** | 25 | Sí — GW `10.10.25.1` |
| Tráfico de las VMs | (mezclado con mgmt) | **`10.10.20.x`** | 20 | Sí — GW `10.10.20.1` |
| Corosync ring0 | `10.10.10.x` | **`10.10.90.x`** | 90 | **No** — sin gateway |
| Ceph / storage / migración | `10.10.20.x` | **`10.10.91.x`** | 91 | **No** — sin gateway |

Direcciones por nodo:

| Nodo | Mgmt (VLAN 25) | Corosync (VLAN 90) | Ceph/Storage (VLAN 91) |
|---|---|---|---|
| `pve1` | `10.10.25.11/24` GW `.1` | `10.10.90.11/24` sin GW | `10.10.91.11/24` sin GW |
| `pve2` | `10.10.25.12/24` GW `.1` | `10.10.90.12/24` sin GW | `10.10.91.12/24` sin GW |
| `pve3` | `10.10.25.13/24` GW `.1` | `10.10.90.13/24` sin GW | `10.10.91.13/24` sin GW |

El último octeto `.11/.12/.13` del README se conserva: solo cambian los
prefijos, así que la tabla es fácil de trasladar.

### Por qué corosync y Ceph no llevan gateway

No es un olvido. Las VLAN 90 y 91 **no existen en el FortiGate**: no tienen
interfaz, ni IP, ni ruta. Viven solo en el switch de servidores. Poner un
gateway ahí haría que el tráfico de cluster busque un camino que no existe.
Ver [doc 03](03-proxmox-cluster.md) y [doc 06](06-switches-dell-n3024.md).

## 3. Reemplazos concretos en el README

```diff
- | **Management / VMs** | Interfaz web, tráfico de VMs | `192.168.10.0/24` |
- | **Corosync** (cluster) | Latido del cluster | `10.10.10.0/24` |
- | **Ceph** (storage) | Replicación de datos, 10GbE | `10.10.20.0/24` |
+ | **Management** | Interfaz web de los nodos (VLAN 25) | `10.10.25.0/24` |
+ | **VMs**        | Tráfico de las máquinas virtuales (VLAN 20) | `10.10.20.0/24` |
+ | **Corosync**   | Latido del cluster (VLAN 90, sin gateway) | `10.10.90.0/24` |
+ | **Ceph**       | Replicación de datos (VLAN 91 o malla 10G) | `10.10.91.0/24` |
```

Sección 3.6 del README, instalador — **Management network**:

```
IP      10.10.25.11/24     (.12 en pve2, .13 en pve3)
Gateway 10.10.25.1
DNS     10.10.25.1         (el FortiGate, hasta que exista el DC/AD)
FQDN    pve1.midominio.local
```

Sección 4.3 — `/etc/hosts` en los tres nodos:

```
127.0.0.1      localhost
10.10.25.11    pve1.midominio.local pve1
10.10.25.12    pve2.midominio.local pve2
10.10.25.13    pve3.midominio.local pve3
```

Sección 5.1 y 5.2 — creación del cluster, **con los dos anillos**:

```bash
# en pve1
pvecm create cluster-r720 --link0 10.10.90.11 --link1 10.10.25.11

# en pve2
pvecm add 10.10.90.11 --link0 10.10.90.12 --link1 10.10.25.12

# en pve3
pvecm add 10.10.90.11 --link0 10.10.90.13 --link1 10.10.25.13
```

El README solo usa `--link0`. El `--link1` por la red de management es el que
hace que el cluster sobreviva a un cable de corosync cortado sin reiniciar
nodos. Agregarlo después de creado el cluster se puede, pero implica editar
`corosync.conf` a mano, que es una operación delicada: conviene hacerlo bien
desde el principio.

Sección 6.2 — configuración de Ceph:

```
Public Network   10.10.91.0/24
Cluster Network  10.10.91.0/24
```

Sección 6.6 / migración — forzar que la migración en vivo use la red rápida:

```
# /etc/pve/datacenter.cfg
migration: secure,network=10.10.91.0/24
```

## 4. El problema que el README no ve: Ceph necesita 10 GbE y el switch no los tiene

El README pide, con razón, **2× 10GbE dedicados para Ceph**. Pero el switch del
proyecto es un **Dell N3024: 24 puertos de 1 GbE**. Sus dos puertos SFP+ (si el
módulo está presente) se usan para uplink o stacking, no alcanzan para 6 bocas
de 10G.

Tres caminos:

> **RESUELTO (2026-10): los R720 no tienen placas de 10 GbE.** Se descarta Ceph
> y se va por la opción (c), ZFS + replicación. Las opciones (a) y (b) quedan
> documentadas por si en el futuro se compra el hardware.

### a) Malla full-mesh entre los 3 nodos

Con exactamente 3 nodos y 2 puertos de 10G por nodo, se conectan **directo entre
sí con cables DAC**, sin switch: cada nodo a los otros dos.

```
        pve1
        /  \
   DAC /    \ DAC
      /      \
   pve2 ──── pve3
        DAC
```

- Costo: 3 cables DAC SFP+. Cero switch.
- Es un escenario documentado por Proxmox ("Full Mesh Network for Ceph Server").
- El método más simple es el **bond en modo broadcast**: los 3 nodos quedan en
  la misma subred `10.10.91.0/24` y cada uno habla con los otros dos. Existe
  también una variante ruteada con direcciones punto a punto, más eficiente pero
  más compleja de mantener.
- Limitación: **no escala a un cuarto nodo**. Si el cliente puede crecer, hay
  que ir por la opción (b).

En este esquema, la VLAN 91 del switch pasa a ser opcional: sirve para el
tráfico de backup hacia un PBS o como camino de respaldo, pero Ceph y la
migración van por la malla.

### b) Switch de 10 GbE dedicado

Un switch SFP+ de 8–12 puertos solo para Ceph. Es lo correcto si el cluster
puede crecer, y lo que hay que cotizar si el cliente quiere Ceph "en serio".

### c) Sin 10 GbE: **no usar Ceph**

Si los R720 no tienen NICs de 10G y no se van a comprar, Ceph sobre 1 GbE anda
mal y se vuelve frágil. La alternativa real es **ZFS local + replicación**
(`pvesr`) cada 5–15 minutos: da HA con pérdida de datos acotada al intervalo de
replicación, en lugar de cero. Ya estaba planteado en el [doc 03](03-proxmox-cluster.md).

**Esto hay que definirlo antes de comprar discos**, porque cambia el plan:
Ceph quiere muchos discos chicos por nodo, ZFS quiere un espejo decente.

## 5. Otras observaciones sobre el README

| # | Observación | Severidad |
|---|---|---|
| 1 | §4.5 dice crear **bridges** para corosync y Ceph. No va: esas interfaces llevan IP directa, sin bridge. Un bridge agrega overhead y lógica de STP donde no hace falta. Bridge solo para `vmbr0` (mgmt) y `vmbr1` (VMs). | Media |
| 2 | No menciona **MTU 9000** en la red de Ceph/storage. Con 10G es una diferencia real de rendimiento. Tiene que ser de punta a punta: NIC, switch (o DAC) y todos los nodos. Verificar con `ping -M do -s 8972 10.10.91.12`. | Media |
| 3 | No menciona el **tagging de VLAN**. Con la config de switch del [doc 06](06-switches-dell-n3024.md), los puertos de mgmt, corosync y storage son *access*: los nodos no necesitan tags. El único que lleva tags es `vmbr1` (VMs), que va **vlan-aware** sobre un puerto trunk. | Media |
| 4 | La VM que haga de **DNS/AD** va en VLAN 20 (`10.10.20.10`). Mientras no exista, los nodos pueden usar `10.10.25.1` (el FortiGate) como DNS. | Baja |
| 5 | §9 recomienda PBS "en otra máquina": vale reforzarlo. Un backup que vive dentro del mismo cluster no es un backup. | Baja |
| 6 | Los nodos necesitan salir a internet para repos y actualizaciones: ya está contemplado en la política 40 del FortiGate (`SERVERS->INTERNET`, solo DNS/HTTP/HTTPS/NTP). Si `apt update` falla, mirar ahí primero. | Informativa |
| 7 | §1.3 sobre la PERC H710 está bien planteado, incluida la recomendación de pasar a HBA330/H310 en modo IT. Si se va a Ceph, es el camino correcto, no el RAID0-por-disco. | Correcta |
| 8 | §5.3 "no hace falta QDevice con número impar de nodos": correcto. | Correcta |

## 6. Resumen de qué cambiar

1. **Obligatorio**: las tres subredes del §0.2 y todas las tablas que las usan
   (§0.2, §3.6, §4.3, §5.1, §5.2, §6.2).
2. **Obligatorio**: agregar `--link1` a los comandos de creación del cluster.
3. **Decisión previa a comprar**: Ceph con malla 10G, Ceph con switch 10G, o ZFS
   con replicación. Define cuántos discos comprar por nodo.
4. **Recomendado**: quitar los bridges de corosync y Ceph, agregar MTU 9000 en
   la red de storage y aclarar que `vmbr1` va vlan-aware.
