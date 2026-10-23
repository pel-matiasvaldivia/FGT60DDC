# 03 — Red del cluster Proxmox VE

## Principio de diseño

El FortiGate 60F rutea a 1 Gbps por puerto. Si el tráfico de corosync, de
replicación o de migración en vivo pasa por el firewall, el cluster se vuelve
inestable en cuanto hay carga: **corosync es sensible a la latencia, no al ancho
de banda**, y un firewall saturado introduce jitter que provoca pérdida de quorum
y nodos reiniciándose por watchdog.

Por eso: **corosync y storage/migración viven en VLANs sin interfaz en el FortiGate**
(VLAN 90 y 91). Son dominios L2 puros en el switch de servidores. El firewall
sólo interviene para administrar los nodos (VLAN 25) y para el tráfico de las VMs
(VLAN 20).

## Cantidad de nodos

**Tres nodos como mínimo.** Con dos nodos no hay quorum real: si cae uno, el otro
se bloquea (o hay que forzar `pvecm expected 1` a mano, con riesgo de split-brain).
Si el presupuesto sólo alcanza dos, agregar un **QDevice** (un dispositivo externo
liviano, puede ser una VM o una Raspberry corriendo `corosync-qnetd`) en VLAN 90.

## Interfaces por nodo

Escenario ideal por nodo (4 NICs):

| NIC | VLAN | Uso | IP ejemplo (PVE-01) |
|---|---|---|---|
| eno1 | 25 (access) o trunk | Mgmt `vmbr0` — GUI 8006, SSH, corosync ring1 | 10.10.25.11/24 GW 10.10.25.1 |
| eno2 | 20 (trunk) | `vmbr1` — tráfico de las VMs | sin IP (bridge) |
| eno3 | 90 (access) | corosync ring0 **dedicado** | 10.10.90.11/24 sin GW |
| eno4 | 91 (access) | Storage + migración (MTU 9000) | 10.10.91.11/24 sin GW |

Con 2 NICs (mínimo viable): NIC1 = trunk con VLAN 25 (mgmt) + 20 (VMs);
NIC2 = trunk con VLAN 90 + 91. No mezclar corosync con migración en el mismo
enlace sin QoS: una migración en vivo satura el link y tira el quorum.

Ejemplo `/etc/network/interfaces` (PVE-01, 4 NICs):

```
auto lo
iface lo inet loopback

auto eno1
iface eno1 inet manual

auto vmbr0
iface vmbr0 inet static
    address 10.10.25.11/24
    gateway 10.10.25.1
    bridge-ports eno1
    bridge-stp off
    bridge-fd 0

auto eno2
iface eno2 inet manual

auto vmbr1
iface vmbr1 inet manual
    bridge-ports eno2
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 20,50

auto eno3
iface eno3 inet static
    address 10.10.90.11/24
    # corosync ring0 - sin gateway, red aislada

auto eno4
iface eno4 inet static
    address 10.10.91.11/24
    mtu 9000
    # storage / migracion - sin gateway, MTU 9000 extremo a extremo
```

> Si usás `vmbr1` vlan-aware, en cada VM se define la VLAN tag (20, 50, etc.)
> desde la GUI. Es más flexible que un bridge por VLAN.

## Corosync: dos anillos

```
# /etc/pve/corosync.conf  (editar SIEMPRE con cuidado, se replica solo)
nodelist {
  node { name: pve-01  nodeid: 1  quorum_votes: 1
         ring0_addr: 10.10.90.11  ring1_addr: 10.10.25.11 }
  node { name: pve-02  nodeid: 2  quorum_votes: 1
         ring0_addr: 10.10.90.12  ring1_addr: 10.10.25.12 }
  node { name: pve-03  nodeid: 3  quorum_votes: 1
         ring0_addr: 10.10.90.13  ring1_addr: 10.10.25.13 }
}
totem {
  cluster_name: cliente-pve
  transport: knet
  interface { linknumber: 0 }
  interface { linknumber: 1 }
}
```

Ring0 dedicado (VLAN 90), ring1 por mgmt (VLAN 25) como respaldo. Al crear el
cluster se puede pasar directamente:

```
# en el primer nodo
pvecm create cliente-pve --link0 10.10.90.11 --link1 10.10.25.11
# en los demas
pvecm add 10.10.90.11 --link0 10.10.90.12 --link1 10.10.25.12
```

## Storage

Con uplinks de 1 Gbps, elegir según el caso:

**Decidido (2026-10): ZFS local + replicación.** Los R720 del proyecto no tienen
placas de 10 GbE y el switch es de 1 GbE, así que Ceph queda descartado. Ver
`proxmox/README.md` §0.3 y su anexo A.

| Opción | Estado | Nota |
|---|---|---|
| **ZFS local + replicación** | **ELEGIDA** | Replicación cada 5–15 min. HA con pérdida acotada a ese intervalo, no cero |
| Ceph | Descartada | Sin 10 GbE rinde mal y vuelve frágil al cluster |
| NFS/iSCSI a un NAS | No evaluada | El NAS pasaría a ser punto único de falla |

Red de migración: forzarla a VLAN 91 para que no toque mgmt ni las VMs.

```
# /etc/pve/datacenter.cfg
migration: secure,network=10.10.91.0/24
```

## MTU 9000

Sólo en VLAN 91 y **de punta a punta**: NIC de los nodos, puertos del switch y el
NAS si existe. Un solo eslabón en 1500 genera fragmentación y caídas intermitentes
muy difíciles de diagnosticar. Verificar:

```
ping -M do -s 8972 10.10.91.12
```

## Configuración del switch de servidores

```
VLAN 20  SERVERS       -> trunk a nodos (tagged), trunk al FortiGate port2
VLAN 25  PVE-MGMT      -> access o tagged a nodos, trunk al FortiGate port2
VLAN 90  PVE-CLUSTER   -> access a nodos. NO en el trunk al FortiGate.
VLAN 91  PVE-STORAGE   -> access a nodos, MTU 9000. NO en el trunk al FortiGate.
```

Recomendaciones del switch:

- IGMP snooping habilitado (corosync/knet usa unicast en PVE 6+, pero otros
  servicios del cluster agradecen el snooping).
- **No** habilitar storm control agresivo ni limitadores en los puertos de VLAN 90.
- Habilitar `portfast`/`edge-port` en los puertos de los nodos: un STP lento al
  levantar un link puede provocar pérdida de quorum durante un reinicio.
- Si el switch es apilable, distribuir los nodos entre miembros distintos del stack.

## Lo que el FortiGate sí hace por el cluster

1. Permite administrar los nodos (8006/SSH) sólo desde VLAN 60 y VLAN 10 — política 50.
2. Rutea el tráfico de las VMs (VLAN 20) a usuarios, a internet y al túnel SAP.
3. Deja salir a los nodos a internet para repos/actualizaciones (política 40).
4. **No** ve ni rutea VLAN 90/91. Si algún día aparece tráfico de cluster en los
   logs del firewall, es que alguien cableó mal.

## Backup

Proxmox Backup Server (PBS) en una VM/host aparte o un NFS, con la interfaz de
backup en VLAN 91 para no castigar mgmt. Backups del FortiGate y del cluster
fuera del cluster — un backup que vive sólo dentro del cluster no es un backup.
