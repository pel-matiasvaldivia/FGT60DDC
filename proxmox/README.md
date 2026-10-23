# Cluster Proxmox VE — 3× Dell PowerEdge R720

Instructivo paso a paso para montar un cluster de **3 nodos** con Dell PowerEdge R720
y la **última versión estable de Proxmox VE (serie 9.x)**.

> **Resumen del objetivo**: 3 servidores idénticos formando un cluster con quórum
> nativo (3 votos), almacenamiento compartido y **Alta Disponibilidad (HA)** para que
> las VMs migren solas si cae un nodo.

> **Direccionamiento corregido (2026-10)**: este documento usa el plan de red del
> proyecto FT-60F-DDC. Las subredes del borrador original (`10.10.10.0/24` para
> corosync y `10.10.20.0/24` para Ceph) **colisionaban** con la VLAN 10 (USERS) y la
> VLAN 20 (SERVERS) del FortiGate. Ver `docs/07-proxmox-direccionamiento.md`.

---

## 0. Antes de empezar — planificación

### 0.1 Inventario recomendado por nodo (R720)

| Componente | Recomendación |
|---|---|
| CPU | 2× Xeon E5-2600 v1/v2 (los 3 nodos, misma familia para live-migration) |
| RAM | 128 GB+ (mínimo 64 GB si vas a usar Ceph) |
| Discos SO | 2× SSD/HDD en espejo (ZFS RAID1) solo para el hipervisor |
| Discos datos | 2–6 discos **dedicados** por nodo |
| Red | 4× 1GbE onboard **+ 2× 10GbE** si se va a usar Ceph (ver §0.3) |
| Controladora | PERC H710/H710P (ver nota HBA en §1.3) |
| iDRAC | iDRAC 7 Enterprise (acceso remoto y consola virtual) |

### 0.2 Plan de red — **valores definitivos del proyecto**

| Red | Uso | Subred | VLAN | ¿Ruteada por el FortiGate? |
|---|---|---|---|---|
| **Management** | Interfaz web 8006, SSH, corosync ring1 | `10.10.25.0/24` | 25 | **Sí** — GW `10.10.25.1` |
| **VMs** | Tráfico de las máquinas virtuales | `10.10.20.0/24` | 20 | **Sí** — GW `10.10.20.1` |
| **Corosync** | Latido del cluster, ring0 | `10.10.90.0/24` | 90 | **No** — sin gateway |
| **Storage / Ceph** | Replicación, migración en vivo | `10.10.91.0/24` | 91 | **No** — sin gateway |

Direcciones por nodo:

| Nodo | Hostname | Mgmt (VLAN 25) | Corosync (VLAN 90) | Storage (VLAN 91) | iDRAC (VLAN 60) |
|---|---|---|---|---|---|
| 1 | `pve1` | `10.10.25.11/24` | `10.10.90.11/24` | `10.10.91.11/24` | `10.10.60.31/24` |
| 2 | `pve2` | `10.10.25.12/24` | `10.10.90.12/24` | `10.10.91.12/24` | `10.10.60.32/24` |
| 3 | `pve3` | `10.10.25.13/24` | `10.10.90.13/24` | `10.10.91.13/24` | `10.10.60.33/24` |

- Gateway **solo** en la red de management: `10.10.25.1` (el FortiGate).
- DNS: `10.10.25.1` hasta que exista el DC/AD; después, la IP del DC en VLAN 20.
- **Corosync y storage NO llevan gateway**: esas VLANs no existen en el FortiGate.
  No tienen interfaz, ni IP, ni ruta. Viven solo en el switch de servidores. Es
  intencional: corosync es sensible al jitter y un firewall ocupado hace que los
  nodos se reinicien por watchdog.

> **Importante**: definí hostnames y `/etc/hosts` ANTES de crear el cluster.
> Cambiar el hostname de un nodo ya unido al cluster es problemático.

### 0.3 Decisión previa: Ceph o ZFS — **definir antes de comprar discos**

El switch del proyecto es un **Dell N3024, de 1 GbE**. Ceph sobre 1 GbE anda mal y
vuelve frágil al cluster. Hay tres caminos:

| Opción | Cuándo | Qué hace falta |
|---|---|---|
| **A · Ceph con malla full-mesh** ⭐ | 3 nodos, sin planes de crecer | 2× 10GbE por nodo + **3 cables DAC**. Sin switch. |
| **B · Ceph con switch 10G** | Si el cluster puede crecer a 4+ nodos | Switch SFP+ de 8–12 puertos dedicado |
| **C · ZFS + replicación** | Si no hay (ni habrá) 10 GbE | Nada extra. Espejo ZFS decente por nodo |

La decisión cambia la compra: **Ceph quiere muchos discos chicos por nodo; ZFS
quiere un espejo bueno.**

En la **opción A**, los tres nodos se conectan directo entre sí:

```
          pve1
         /    \
   DAC  /      \  DAC
       /        \
    pve2 ────── pve3
          DAC
```

Cada nodo usa sus dos puertos de 10G, uno hacia cada vecino. Es un escenario
documentado por Proxmox (*Full Mesh Network for Ceph Server*). **No escala a un
cuarto nodo**: con 4 nodos hay que ir a la opción B.

En la opción A la VLAN 91 del switch queda como camino de respaldo y para el
tráfico de backup hacia el PBS; Ceph y la migración van por la malla.

En la **opción C**, saltear todo el capítulo 6 (Ceph) y usar replicación ZFS (§6.7).

---

## 1. Preparación del hardware (los 3 servidores)

### 1.1 Actualizar firmware (recomendado)
Desde iDRAC o con **Dell Lifecycle Controller** (F10 al arrancar), actualizá:
BIOS, iDRAC, firmware de PERC y de las NICs. Firmware viejo del R720 da problemas
de estabilidad y de rendimiento con NVMe/SSD.

### 1.2 Configuración de BIOS (F2 → System BIOS)
- **Virtualization Technology**: `Enabled` (Intel VT-x; en el R720 habilita también
  la IOMMU que necesita el passthrough PCI).
- **Boot Mode**: `UEFI` — el mismo en los 3 nodos.
- **System Profile**: `Performance` (evita throttling de CPU).
- **Logical Processor** (Hyper-Threading): `Enabled`.
- **SR-IOV Global Enable**: `Enabled` solo si vas a usar SR-IOV; si no, dejalo apagado.

> Estos valores se pueden aplicar de una sola vez con el **Server Configuration
> Profile** de iDRAC. Ver la carpeta `scp/` de este repositorio.

### 1.3 Controladora PERC H710/H710P — clave para Ceph/ZFS
La H710 **no tiene modo HBA/IT nativo** real. Opciones:

- **Para los discos del SO**: creá un **RAID1** virtual con 2 discos → ahí instalás Proxmox.
- **Para discos de Ceph/ZFS**: Ceph y ZFS quieren acceso **directo** al disco (sin RAID).
  Como la H710 no hace passthrough puro, la práctica habitual es crear un
  **RAID0 de un solo disco por cada disco** (cada disco como VD independiente).
  Deshabilitá la caché de escritura del controlador para esos VD.
  - *Alternativa recomendada si vas en serio con Ceph*: reemplazar o flashear a una
    **HBA330 / H310 en modo IT** para tener passthrough real de discos.

> Regla de oro: **nunca** pongas discos de Ceph/ZFS detrás de un RAID de hardware
> con caché con batería activa — corrompe la lógica de replicación y el scrubbing.

### 1.4 iDRAC
Configurá la IP del puerto iDRAC dedicado en la **VLAN 60** (`10.10.60.31/.32/.33`,
GW `10.10.60.1`). Te va a servir para:
- Montar la ISO de Proxmox de forma remota (Virtual Media).
- Consola remota (Virtual Console) durante la instalación.
- Encender/apagar/reiniciar nodos para probar HA.
- Aplicar el perfil de configuración XML de `scp/`.

El puerto iDRAC va a un puerto **access de VLAN 60** del switch de servidores
(ver `docs/06-switches-dell-n3024.md`).

---

## 2. Descargar la última versión de Proxmox VE

1. Entrá a **https://www.proxmox.com/downloads** → *Proxmox VE ISO Installer*.
2. Descargá la última ISO estable (serie **9.x**, basada en Debian 13 "Trixie").
3. **Verificá el checksum SHA256** que publica Proxmox junto a la ISO.

```bash
sha256sum proxmox-ve_9.x.iso
# Comparar con el valor publicado en la web oficial
```

Formas de bootear la ISO en el R720:
- **iDRAC → Virtual Media** (montar la ISO por red, la más cómoda). O
- Pendrive booteable creado con `dd` o **balenaEtcher / Rufus (modo DD)**.

```bash
# Ejemplo creación de USB en Linux (¡cuidado con el /dev/sdX correcto!)
sudo dd if=proxmox-ve_9.x.iso of=/dev/sdX bs=1M status=progress oflag=direct
sync
```

---

## 3. Instalar Proxmox VE en cada nodo

Repetí esto en `pve1`, `pve2` y `pve3`.

1. Booteá desde la ISO → elegí **Install Proxmox VE (Graphical)**.
2. Aceptá la licencia (EULA).
3. **Target disk**: elegí el disco/VD del SO. Click en **Options** para elegir
   filesystem:
   - **`zfs (RAID1)`** si tenés 2 discos para el SO (recomendado: snapshots y
     resiliencia del hipervisor).
   - `ext4`/`xfs` si es un solo disco.
   - **No** uses aquí los discos que vas a dedicar a Ceph/ZFS de datos.
4. **Location & Time Zone**: Argentina, `America/Argentina/Buenos_Aires`, teclado `es`.
5. **Password + Email**: contraseña de root y un email real (para alertas).
6. **Management network** — acá van los valores corregidos:

   | Campo | pve1 | pve2 | pve3 |
   |---|---|---|---|
   | Interfaz | la 1ª NIC 1GbE (`eno1`) | `eno1` | `eno1` |
   | FQDN | `pve1.midominio.local` | `pve2...` | `pve3...` |
   | IP / CIDR | `10.10.25.11/24` | `10.10.25.12/24` | `10.10.25.13/24` |
   | Gateway | `10.10.25.1` | `10.10.25.1` | `10.10.25.1` |
   | DNS | `10.10.25.1` | `10.10.25.1` | `10.10.25.1` |

7. Revisá el resumen → **Install**. Al terminar, reiniciá y quitá la ISO.

Accedé a la interfaz web de cada nodo:
```
https://10.10.25.11:8006
```
(usuario `root`, realm **Linux PAM**).

> Si el puerto del switch todavía no está en VLAN 25, no vas a llegar. Verificá
> primero la configuración del switch de servidores.

---

## 4. Configuración post-instalación (los 3 nodos)

### 4.1 Repositorios: quitar el Enterprise, activar el No-Subscription
Sin suscripción, hay que apuntar al repo *no-subscription* o `apt update` falla.
En Proxmox VE 9 los repos usan el formato **deb822** (`.sources`).

```bash
# Deshabilitar repos enterprise (PVE y Ceph): comentá o eliminá sus líneas
nano /etc/apt/sources.list.d/pve-enterprise.sources
nano /etc/apt/sources.list.d/ceph.sources
```

Crear el repo **no-subscription** de PVE:
```bash
cat > /etc/apt/sources.list.d/pve-no-subscription.sources <<'EOF'
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
EOF
```

Y el repo **no-subscription de Ceph** (solo si vas con Ceph; elegí el release que
instale Proxmox, ej. `squid`):
```bash
cat > /etc/apt/sources.list.d/ceph.sources <<'EOF'
Types: deb
URIs: http://download.proxmox.com/debian/ceph-squid
Suites: trixie
Components: no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
EOF
```

> Nota: el nombre del *suite* (`trixie`) y el release de Ceph pueden variar según
> la versión exacta que descargues. Verificá los `.sources` que crea el instalador
> y respetá esos nombres.

> Si `apt update` no sale a internet: la salida de los nodos está permitida por la
> política 40 del FortiGate (`SERVERS->INTERNET`), limitada a DNS/HTTP/HTTPS/NTP.
> Empezá a mirar por ahí.

### 4.2 Actualizar el sistema
```bash
apt update && apt full-upgrade -y
reboot
```

### 4.3 Resolución de nombres — `/etc/hosts` en los 3 nodos
Cada nodo tiene que resolver a los otros dos:
```
127.0.0.1      localhost
10.10.25.11    pve1.midominio.local pve1
10.10.25.12    pve2.midominio.local pve2
10.10.25.13    pve3.midominio.local pve3
```
Verificá: `ping pve2`, `ping pve3` desde `pve1`, etc.

### 4.4 Hora sincronizada (crítico para el cluster)
Corosync y Ceph son sensibles al reloj:
```bash
timedatectl
timedatectl set-ntp true
```
El FortiGate (`10.10.25.1`) puede actuar de servidor NTP si hace falta.

### 4.5 Red: configurar las interfaces separadas

**Corosync y storage NO van sobre bridges.** Llevan IP directa sobre la interfaz
física. Un bridge agrega overhead y lógica de STP donde no hace falta. Solo
`vmbr0` (management) y `vmbr1` (VMs) son bridges.

Confirmá primero los nombres reales de tus NICs:
```bash
ip -br link
```

#### Variante A — con 10 GbE para Ceph (malla full-mesh)

`/etc/network/interfaces` de **pve1** (cambiar el último octeto en pve2/pve3):

```
auto lo
iface lo inet loopback

# --- eno1: management (VLAN 25 access) --------------------------------
auto eno1
iface eno1 inet manual

auto vmbr0
iface vmbr0 inet static
    address 10.10.25.11/24
    gateway 10.10.25.1
    bridge-ports eno1
    bridge-stp off
    bridge-fd 0
#   Management + interfaz web 8006 + corosync ring1

# --- eno2: tráfico de las VMs (puerto trunk, VLAN 20 y 50) ------------
auto eno2
iface eno2 inet manual

auto vmbr1
iface vmbr1 inet manual
    bridge-ports eno2
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 20,50
#   Sin IP: es solo el camino de las VMs. La VLAN se define por VM.

# --- eno3: corosync ring0 (VLAN 90 access) ----------------------------
auto eno3
iface eno3 inet static
    address 10.10.90.11/24
#   SIN gateway. Red aislada, sin ruteo. No tocar.

# --- 10GbE: malla full-mesh para Ceph ---------------------------------
auto bond0
iface bond0 inet static
    address 10.10.91.11/24
    bond-slaves ens2f0 ens2f1
    bond-mode broadcast
    mtu 9000
#   Un puerto a cada vecino, con cables DAC. Modo broadcast: los tres
#   nodos quedan en la misma subred sin necesidad de switch.

# --- eno4: libre / respaldo / backup hacia el PBS (VLAN 91 access) ----
#auto eno4
#iface eno4 inet static
#    address 10.10.91.111/24
```

#### Variante B — solo 1 GbE (sin Ceph, con ZFS + replicación)

Igual que la A, pero **sin el `bond0`** y con `eno4` activo:

```
auto eno4
iface eno4 inet static
    address 10.10.91.11/24
    mtu 9000
#   Storage / replicación / migración. SIN gateway.
#   MTU 9000 también en el puerto del switch.
```

Aplicar los cambios:
```bash
ifreload -a          # o reboot si cambiaste mucho
ip -br addr
```

### 4.6 Verificar MTU 9000 extremo a extremo (solo en la red de storage)

Un solo eslabón en 1500 genera fragmentación y caídas intermitentes muy difíciles
de diagnosticar. Verificá desde pve1:
```bash
ping -M do -s 8972 10.10.91.12
ping -M do -s 8972 10.10.91.13
```
Si no responde, falta subir el MTU en algún lado: NIC, puerto del switch o el
otro nodo.

### 4.7 VLANs: quién etiqueta qué

Con la configuración de switch del proyecto, los puertos de management, corosync
y storage son **access**: los nodos no manejan tags ahí. El único puerto con tags
es el de `vmbr1` (VMs), que es **trunk** y por eso el bridge va `vlan-aware`: la
VLAN se elige por VM desde la GUI.

---

## 5. Crear el cluster

### 5.1 En el nodo 1 (`pve1`) — crear el cluster

**Dos anillos desde el principio.** Ring0 por la red dedicada de corosync, ring1
por management como respaldo. Si se corta el cable de corosync, el cluster sigue
por el ring1 en lugar de perder quórum.

```bash
pvecm create cluster-r720 --link0 10.10.90.11 --link1 10.10.25.11
```

Por interfaz web: **Datacenter → Cluster → Create Cluster**, con
**Link 0** = `10.10.90.11` y **Link 1** = `10.10.25.11`.

Verificar:
```bash
pvecm status
```

> Agregar el segundo anillo *después* de creado el cluster implica editar
> `/etc/pve/corosync.conf` a mano, que es una operación delicada y puede tirar el
> cluster si se hace mal. Hacelo bien desde el principio.

### 5.2 Unir nodo 2 y nodo 3

Necesitás la **Join Information** de `pve1`:
**Datacenter → Cluster → Join Information → Copy**.

Por CLI, desde cada nodo (cada uno usa **sus propias** IPs):
```bash
# en pve2
pvecm add 10.10.90.11 --link0 10.10.90.12 --link1 10.10.25.12

# en pve3
pvecm add 10.10.90.11 --link0 10.10.90.13 --link1 10.10.25.13
```

### 5.3 Verificar el cluster (desde cualquier nodo)
```bash
pvecm status      # 3 nodos, Quorum: OK (3 votos, esperados 3)
pvecm nodes
corosync-cfgtool -s   # los DOS anillos deben figurar activos
```
Con 3 nodos hay quórum tolerante a la caída de **1 nodo** (2 de 3 = mayoría).
No hace falta QDevice con número impar de nodos.

---

## 6. Almacenamiento

### Si elegiste ZFS + replicación (opción C), saltá a §6.7

### 6.1 Instalar Ceph en los 3 nodos
**Datacenter → Nodo → Ceph** → *Install Ceph* (elegí el release ofrecido, ej. `squid`).
Repetí en los 3 nodos. Por CLI:
```bash
pveceph install --repository no-subscription
```

### 6.2 Configuración inicial (una vez, en pve1)
En **Ceph → Configuration**:
- **Public Network**: `10.10.91.0/24`
- **Cluster Network**: `10.10.91.0/24`

### 6.3 Crear los Monitors y Managers
- **Ceph → Monitor**: un **MON** en cada nodo (3 en total → tolera 1 caída).
- Un **MGR** en cada nodo (al menos 2).

### 6.4 Crear los OSDs (discos de datos)
Por cada disco dedicado en cada nodo: **Ceph → OSD → Create: OSD**.
- Si tenés SSD/NVMe chicos, podés usarlos como **DB/WAL** de OSDs de HDD.
- Objetivo: varios OSDs distribuidos parejo entre los 3 nodos.

```bash
ceph -s          # HEALTH_OK cuando terminó el balanceo
ceph osd tree
```

### 6.5 Crear el Pool y la Storage RBD
**Ceph → Pools → Create**:
- **Size = 3**, **Min Size = 2** (3 copias; sigue operando con 2 disponibles).
- **PG Autoscale = on**.

Proxmox agrega automáticamente una storage **RBD** al datacenter, compartida por
los 3 nodos → ahí van los discos de las VMs.

### 6.6 (Opcional) CephFS para ISOs / backups compartidos
**Ceph → CephFS → Create** da un filesystem compartido para plantillas, ISOs y
snippets accesible desde los 3 nodos.

### 6.7 Alternativa: ZFS local + replicación (opción C)

Sin 10 GbE, esta es la opción correcta. No es storage compartido real: la
replicación es asíncrona, así que ante la caída de un nodo se pierde lo ocurrido
desde la última réplica.

1. En cada nodo, crear un pool ZFS con los discos de datos:
   **Nodo → Disks → ZFS → Create: ZFS** (ej. `rpool-data`, RAID1 o RAIDZ).
   Usar **el mismo nombre de pool en los 3 nodos**.
2. Agregar la storage ZFS al datacenter: **Datacenter → Storage → Add → ZFS**,
   marcando los 3 nodos.
3. Por cada VM: **VM → Replication → Add**, destino el otro nodo, intervalo
   `*/15` (cada 15 minutos) o `*/5` si el cambio de datos lo permite.

```bash
pvesr status
pvesr list
```

### 6.8 Red de migración en vivo

Forzar que la migración use la red rápida y no la de management:
```bash
# /etc/pve/datacenter.cfg
migration: secure,network=10.10.91.0/24
```

---

## 7. Alta Disponibilidad (HA)

### 7.1 (Recomendado) Grupos HA
**Datacenter → HA → Groups → Create**: agrupá los 3 nodos y opcionalmente asigná
prioridades (dónde preferís que corra cada VM).

### 7.2 Agregar VMs/CTs a HA
**Datacenter → HA → Resources → Add** → elegí la VM/CT y el grupo.
Ante la caída de un nodo, el **HA Manager** reinicia esas VMs en otro nodo con quórum.

> Con ZFS + replicación (§6.7), el failover funciona pero la VM arranca desde la
> última réplica. Con Ceph, arranca con los datos al día.

### 7.3 Fencing / Watchdog
Proxmox usa un **watchdog por software** por defecto para el fencing. Para
producción crítica, considerá el **watchdog por hardware iTCO** del R720 o fencing
vía iDRAC/IPMI.
```bash
ha-manager status
```

---

## 8. Verificación final

```bash
pvecm status            # 3 nodos, Quorum OK
corosync-cfgtool -s     # 2 anillos activos
ceph -s                 # HEALTH_OK   (solo si usás Ceph)
pvesr status            # replicaciones al día (solo si usás ZFS)
ha-manager status       # servicio HA activo
ping -M do -s 8972 10.10.91.12    # jumbo frames OK
```

Pruebas recomendadas:
1. **Live migration**: mové una VM de `pve1` a `pve2` sin apagarla.
2. **Test de HA**: apagá `pve3` desde iDRAC → las VMs HA deben reiniciar en otro nodo.
3. **Test de storage**: apagá un nodo → `ceph -s` sigue operativo (degradado); al
   volver, se re-balancea solo.
4. **Test del anillo de corosync**: desconectá el cable de `eno3` en un nodo → el
   cluster debe seguir por el ring1, **sin** que el nodo se reinicie. Si se
   reinicia, el ring1 no está bien configurado.
5. **Test de aislamiento**: desde una VM en VLAN 20, intentá llegar a
   `10.10.90.11` → **debe fallar**. Si responde, las VLAN de cluster se filtraron
   al trunk del FortiGate y el diseño está roto.

---

## 9. Recomendaciones de producción

- **Backups**: instalá **Proxmox Backup Server** en una máquina **fuera** del
  cluster. Un backup que vive dentro del cluster no es un backup.
- **Monitoreo**: activá alertas por email; integrá métricas (InfluxDB/Grafana)
  desde **Datacenter → Metric Server**.
- **Actualizaciones**: actualizá **un nodo a la vez**, migrando sus VMs antes
  (rolling upgrade). Nunca los 3 a la vez.
- **UPS**: los 3 nodos + switches en UPS, con apagado ordenado configurado. El
  cluster es muy sensible a cortes: un apagón sin UPS puede corromper el storage.
- **Red redundante**: bonding LACP en management si el switch lo soporta.
- **No mezcles** discos de RAID de hardware con OSDs de Ceph.
- **Documentá** IPs, credenciales de iDRAC y el mapa de discos/OSDs.

---

## 10. Despliegue automatizado

| Carpeta | Qué hay |
|---|---|
| `scp/` | Perfiles XML de Dell (Server Configuration Profile) para aplicar BIOS + iDRAC a cada nodo desde el Lifecycle Controller |
| `answer/` | Archivos de respuesta para la instalación desatendida de Proxmox VE |

Ver `scp/README.md` para el procedimiento y sus advertencias.

---

## Referencias oficiales

- Proxmox VE Administration Guide: https://pve.proxmox.com/pve-docs/
- Cluster Manager (pvecm): https://pve.proxmox.com/wiki/Cluster_Manager
- Deploy Hyper-Converged Ceph: https://pve.proxmox.com/wiki/Deploy_Hyper-Converged_Ceph_Cluster
- Full Mesh Network for Ceph: https://pve.proxmox.com/wiki/Full_Mesh_Network_for_Ceph_Server
- High Availability: https://pve.proxmox.com/wiki/High_Availability
- Storage Replication (pvesr): https://pve.proxmox.com/wiki/Storage_Replication
- Automated Installation: https://pve.proxmox.com/wiki/Automated_Installation
- Descargas + checksums: https://www.proxmox.com/downloads
