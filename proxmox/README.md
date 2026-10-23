# Cluster Proxmox VE — 3× Dell PowerEdge R720

Instructivo paso a paso para montar un cluster de **3 nodos** con Dell PowerEdge R720
y la **última versión estable de Proxmox VE (serie 9.x)**.

> **Resumen del objetivo**: 3 servidores idénticos formando un cluster con quórum
> nativo (3 votos), **ZFS local con replicación entre nodos** y **Alta
> Disponibilidad (HA)** para que las VMs arranquen solas en otro nodo si cae uno.
>
> **Storage**: ZFS + replicación, no Ceph. Los R720 no tienen 10 GbE; el
> razonamiento está en §0.3 y el anexo A.

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
| RAM | 128 GB+ (ZFS usa RAM para el ARC; no escatimar) |
| Discos SO | 2× SSD en espejo (ZFS RAID1) solo para el hipervisor |
| Discos datos | **Espejo ZFS de SSD empresariales con PLP** (ver §0.3) |
| Red | 4× 1GbE onboard. **No hay 10GbE** en estos equipos (ver §0.3) |
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

### 0.3 Almacenamiento: **ZFS local + replicación** (decisión tomada)

> **Los R720 de este proyecto no tienen placas de 10 GbE**, y el switch es un
> Dell N3024 de 1 GbE. Con eso, **Ceph queda descartado**: sobre 1 GbE rinde mal
> y vuelve frágil al cluster entero. El anexo A explica por qué, para que la
> decisión quede documentada.

El esquema es: cada nodo tiene su **pool ZFS local**, y Proxmox **replica** los
discos de las VMs a otro nodo cada N minutos mediante snapshots incrementales
(`pvesr`, basado en `zfs send`).

#### Qué implica, dicho sin vueltas

| | Ceph (storage compartido real) | **ZFS + replicación (lo que vamos a hacer)** |
|---|---|---|
| Pérdida de datos si cae un nodo | Cero | **Hasta el intervalo de replicación** |
| Failover | Automático, con datos al día | Automático, desde la última réplica |
| Live migration | Instantánea | Funciona, más lenta (copia por red) |
| Red necesaria | 10 GbE dedicados | 1 GbE alcanza (solo viajan los deltas) |
| Complejidad | Alta | Baja |

**Esto hay que acordarlo por escrito con el cliente.** Con un intervalo de 15
minutos, una caída abrupta de un nodo puede costar hasta 15 minutos de trabajo
de las VMs que vivían ahí. Para muchos negocios es perfectamente aceptable; para
una base de datos transaccional, no. La respuesta define el intervalo.

#### Qué comprar

ZFS no quiere muchos discos chicos (eso era Ceph). Quiere **pocos discos buenos**:

- **Espejo (RAID1 ZFS) de 2 SSD** para datos por nodo. Con 4 discos, dos espejos
  en stripe (RAID10).
- **SSD empresariales con PLP** (*Power Loss Protection*). Los SSD de consumo
  sin PLP tienen un rendimiento pésimo en escrituras sincrónicas — que es
  justo lo que hace un hipervisor — y se desgastan rápido. Es el error más caro
  que se puede cometer acá.
- **Capacidad**: cada nodo tiene que alojar **sus propias VMs más las réplicas
  de las VMs del nodo del que es destino**. Dimensioná para los dos conjuntos,
  no solo para el propio.
- **No usar RAIDZ** para discos de VMs: penaliza las escrituras aleatorias.
  Espejos.

#### Mejora opcional y barata

Con las 4 NIC onboard ya ocupadas (mgmt, VMs, corosync, storage), si se quiere
**LACP de 2 Gbps** en la red de storage para acelerar replicación y migración,
hace falta una placa PCIe de 4 puertos 1GbE (una Intel i350-T4 sale poco). El
N3024 soporta LACP. No es imprescindible: la replicación manda solo los bloques
cambiados.

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

### 1.3 Controladora PERC H710/H710P — clave para ZFS
La H710 **no tiene modo HBA/IT nativo** real. Opciones:

- **Para los discos del SO**: creá un **RAID1** virtual con 2 discos → ahí instalás Proxmox.
- **Para los discos de datos (ZFS)**: ZFS quiere acceso **directo** al disco (sin RAID).
  Como la H710 no hace passthrough puro, la práctica habitual es crear un
  **RAID0 de un solo disco por cada disco** (cada disco como VD independiente).
  Deshabilitá la caché de escritura del controlador para esos VD.
  - *Alternativa recomendada*: reemplazar o flashear a una **HBA330 / H310 en
    modo IT** para tener passthrough real. ZFS necesita ver el disco de verdad
    (SMART, cache, barreras de escritura); con la H710 de por medio trabaja
    a ciegas.

> Regla de oro: **nunca** pongas discos de ZFS detrás de un RAID de hardware
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
   - **No** uses aquí los discos que vas a dedicar al pool ZFS de datos.
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

> **No hace falta el repo de Ceph**: este cluster usa ZFS (§0.3). Si el archivo
> `/etc/apt/sources.list.d/ceph.sources` existe apuntando al repo *enterprise*,
> comentalo igual o `apt update` va a dar error de autenticación.

> Nota: el nombre del *suite* (`trixie`) puede variar según la versión exacta que
> descargues. Verificá los `.sources` que crea el instalador y respetá esos nombres.

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
Corosync y la replicación son sensibles al reloj:
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

`/etc/network/interfaces` de **pve1** (cambiar el último octeto en pve2 y pve3):

```
auto lo
iface lo inet loopback

# eno1: management (puerto access VLAN 25)
auto eno1
iface eno1 inet manual

auto vmbr0
iface vmbr0 inet static
    address 10.10.25.11/24
    gateway 10.10.25.1
    bridge-ports eno1
    bridge-stp off
    bridge-fd 0
#   Interfaz web 8006, SSH y corosync ring1

# eno2: tráfico de las VMs (puerto trunk, VLAN 20 y 50)
auto eno2
iface eno2 inet manual

auto vmbr1
iface vmbr1 inet manual
    bridge-ports eno2
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
    bridge-vids 20,50
#   Sin IP: es solo el camino de las VMs. La VLAN se elige por VM.

# eno3: corosync ring0 (puerto access VLAN 90)
auto eno3
iface eno3 inet static
    address 10.10.90.11/24
#   SIN gateway. Red aislada, sin ruteo. No tocar.

# eno4: replicación ZFS y migración en vivo (puerto access VLAN 91)
auto eno4
iface eno4 inet static
    address 10.10.91.11/24
    mtu 9000
#   SIN gateway. MTU 9000 también en el puerto del switch.
```

Las cuatro NIC onboard quedan usadas. Si más adelante se quiere LACP en la red
de storage, hace falta una placa PCIe adicional (§0.3).

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

## 6. Almacenamiento: ZFS local + replicación

Cada nodo tiene su pool ZFS local y Proxmox replica los discos de las VMs al
nodo vecino con snapshots incrementales. Ver §0.3 para por qué este esquema y
no Ceph.

### 6.1 Crear el pool ZFS de datos en cada nodo

**Nodo → Disks → ZFS → Create: ZFS**

- **Name**: `datos` — **el mismo nombre en los tres nodos**. Si difiere, la
  replicación no encuentra el destino.
- **RAID Level**: `Mirror` con 2 discos, o `RAID10` con 4.
  **No uses RAIDZ** para discos de VMs: penaliza la escritura aleatoria.
- **Compression**: `on` (lz4). Es gratis en CPU y suele ganar 1.5–2×.
- **Add Storage**: dejalo **desmarcado**; la storage se agrega una sola vez en
  el paso siguiente, para los tres nodos juntos.

Por CLI:
```bash
zpool create -o ashift=12 datos mirror /dev/disk/by-id/<disco1> /dev/disk/by-id/<disco2>
zfs set compression=lz4 datos
zpool status
```

> Usá siempre `/dev/disk/by-id/...` y no `/dev/sdX`: las letras cambian de orden
> entre arranques y podés terminar armando el pool con el disco equivocado.

### 6.2 Agregar la storage al datacenter (una sola vez)

**Datacenter → Storage → Add → ZFS**

- **ID**: `zfs-datos`
- **ZFS Pool**: `datos`
- **Nodes**: los **tres** nodos
- **Content**: Disk image, Container
- **Thin provision**: activado

### 6.3 Limitar el ARC de ZFS (recomendado)

ZFS usa RAM para caché. Por defecto puede tomar hasta la mitad, y en un
hipervisor eso compite con las VMs. Con 128 GB, limitarlo a 16–32 GB es sensato:

```bash
echo "options zfs zfs_arc_max=17179869184" > /etc/modprobe.d/zfs.conf   # 16 GB
update-initramfs -u
reboot
```

### 6.4 Configurar la replicación

Por cada VM o contenedor: **VM → Replication → Add**

- **Target**: el otro nodo (ej. las VMs de pve1 replican a pve2).
- **Schedule**: `*/15` (cada 15 minutos) es un buen punto de partida.
  `*/5` si el negocio lo necesita y el volumen de cambio lo permite.
- **Rate limit**: dejar vacío salvo que la replicación moleste a otro tráfico.

Por CLI:
```bash
pvesr create-local-job 100-0 pve2 --schedule '*/15'
pvesr status
pvesr list
```

**Repartí los destinos** en lugar de mandar todo a un solo nodo: las VMs de
pve1 → pve2, las de pve2 → pve3, las de pve3 → pve1. Así la carga de réplicas
queda pareja y ningún nodo necesita el doble de disco que los otros.

> La **primera** replicación copia el disco entero y puede tardar. Las
> siguientes mandan solo los bloques cambiados, por eso 1 GbE alcanza.

### 6.5 Red de migración y replicación

Forzar que usen la VLAN 91 y no la de management:
```bash
# /etc/pve/datacenter.cfg
migration: secure,network=10.10.91.0/24
```

### 6.6 Almacenamiento para ISOs y plantillas

Sin Ceph no hay CephFS. Opciones:
- Un **NFS** desde el NAS o desde el Proxmox Backup Server.
- O el almacenamiento `local` de cada nodo (hay que subir la ISO en cada uno).

## 7. Alta Disponibilidad (HA)

### 7.1 (Recomendado) Grupos HA
**Datacenter → HA → Groups → Create**: agrupá los 3 nodos y opcionalmente asigná
prioridades (dónde preferís que corra cada VM).

### 7.2 Agregar VMs/CTs a HA
**Datacenter → HA → Resources → Add** → elegí la VM/CT y el grupo.
Ante la caída de un nodo, el **HA Manager** reinicia esas VMs en otro nodo con quórum.

> **Importante**: con ZFS + replicación, el failover funciona, pero la VM
> arranca desde la **última réplica**. Si el nodo cayó 14 minutos después de la
> última copia, se pierden esos 14 minutos. Es la contrapartida acordada en
> §0.3. Agregá a HA solo las VMs donde ese costo sea aceptable.

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
pvecm status                      # 3 nodos, Quorum OK
corosync-cfgtool -s               # los 2 anillos activos
zpool status                      # pool "datos" ONLINE, sin errores
pvesr status                      # replicaciones al día, sin fallas
ha-manager status                 # servicio HA activo
ping -M do -s 8972 10.10.91.12    # jumbo frames OK
```

Pruebas recomendadas:
1. **Live migration**: mové una VM de `pve1` a `pve2` sin apagarla.
2. **Test de HA**: apagá `pve3` desde iDRAC → las VMs HA deben reiniciar en otro nodo.
3. **Test de replicación**: `pvesr status` en los tres nodos; todas las tareas
   con estado OK y una fecha reciente. Una replicación fallando en silencio
   deja el failover sin datos útiles, y no avisa sola.
4. **Test del anillo de corosync**: desconectá el cable de `eno3` en un nodo → el
   cluster debe seguir por el ring1, **sin** que el nodo se reinicie. Si se
   reinicia, el ring1 no está bien configurado.
5. **Test de aislamiento**: desde una VM en VLAN 20, intentá llegar a
   `10.10.90.11` → **debe fallar**. Si responde, las VLAN de cluster se filtraron
   al trunk del FortiGate y el diseño está roto.
6. **Test de pérdida de datos real**: escribí un archivo con la hora dentro de
   una VM con HA, apagá el nodo a lo bruto desde iDRAC y mirá, cuando la VM
   levante en otro nodo, cuánto se perdió. Es el número que hay que mostrarle
   al cliente, no una estimación.

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
- **Vigilá la replicación**: configurá alerta por mail ante fallas de `pvesr`.
  Una réplica rota es un failover sin datos.
- **Scrub mensual** del pool ZFS: `zpool scrub datos` (Proxmox ya programa uno).
- **Documentá** IPs, credenciales de iDRAC y el mapa de discos/OSDs.

---

## 10. Despliegue automatizado

| Carpeta | Qué hay |
|---|---|
| `scp/` | Perfiles XML de Dell (Server Configuration Profile) para aplicar BIOS + iDRAC a cada nodo desde el Lifecycle Controller |
| `answer/` | Archivos de respuesta para la instalación desatendida de Proxmox VE |

Ver `scp/README.md` para el procedimiento y sus advertencias.

---

## Anexo A — Por qué no Ceph en este cluster

Queda documentado para que la decisión no se reabra sin datos nuevos.

Ceph fue la primera opción del borrador, y es la correcta cuando el hardware
acompaña: storage compartido real, failover sin pérdida de datos, escalable.
Acá no acompaña:

1. **Los R720 no tienen placas de 10 GbE.** Ceph replica cada escritura a los
   otros nodos de forma sincrónica: la latencia y el ancho de banda de la red
   *son* el rendimiento del storage. Sobre 1 GbE compartido el resultado es un
   cluster lento y propenso a `HEALTH_WARN` bajo carga.
2. **El switch es un Dell N3024, de 1 GbE.** Sus dos SFP+ se usan para uplink o
   stacking: no alcanzan para 6 bocas de 10G.
3. **La malla full-mesh tampoco aplica**, porque requiere igualmente 2 puertos
   de 10 GbE por nodo, que es lo que falta.
4. **Ceph quiere varios OSD por nodo.** Con pocos discos no reparte bien y la
   caída de un disco pesa mucho más.

Qué haría falta para reconsiderarlo:

- 3 placas de 10 GbE de doble puerto (una por nodo) **y** 3 cables DAC para la
  malla, o un switch SFP+ dedicado.
- Varios discos de datos por nodo.

Si en algún momento se compra ese hardware, migrar de ZFS a Ceph es posible sin
rehacer el cluster: se instala Ceph, se crea el pool y se mueven los discos de
las VMs con *Move disk*, una por una y en caliente.

---

## Referencias oficiales

- Proxmox VE Administration Guide: https://pve.proxmox.com/pve-docs/
- Cluster Manager (pvecm): https://pve.proxmox.com/wiki/Cluster_Manager
- ZFS on Linux (PVE): https://pve.proxmox.com/wiki/ZFS_on_Linux
- High Availability: https://pve.proxmox.com/wiki/High_Availability
- Storage Replication (pvesr): https://pve.proxmox.com/wiki/Storage_Replication
- Automated Installation: https://pve.proxmox.com/wiki/Automated_Installation
- Descargas + checksums: https://www.proxmox.com/downloads
