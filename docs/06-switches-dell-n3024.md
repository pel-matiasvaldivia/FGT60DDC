# 06 — Switches Dell N3024: diseño, dimensionamiento y notas

> **Alcance (actualizado 2026-10)**: el acceso se resuelve con 4 × SMC8024L2
> (ver [doc 08](08-switches-smc8024l2.md)). Este documento aplica al **switch de
> servidores** (puerto 3 / `internal3` del FortiGate). La sección de
> dimensionamiento del acceso queda como referencia histórica.

Archivos de configuración:
[`config/switches/dell-n3024-acceso.cfg`](../config/switches/dell-n3024-acceso.cfg) ·
[`config/switches/dell-n3024-servidores.cfg`](../config/switches/dell-n3024-servidores.cfg)

## 1. Verificar primero el modelo

"N324" no es un código Dell exacto. Las configuraciones asumen la **serie N3000
con Dell Networking OS6** (N3024, N3024P, N3024F o N3048). El CLI es el mismo en
toda la serie; lo que cambia es la cantidad de puertos, si tienen PoE y el tipo
de uplink.

```
show version
show switch
show system
```

Si resultara ser serie **N1100/N1500** el CLI es prácticamente idéntico. Si fuera
**S-series con OS9/OS10**, la sintaxis es otra y hay que rehacer los archivos.

## 2. Dimensionamiento — faltan puertos

| Concepto | Cantidad |
|---|---|
| Desktops | 80 |
| Access Points | 4 |
| Impresoras / IoT (estimado) | 4–6 |
| **Total bocas de acceso** | **~88–90** |
| 3 × N3024 | 72 ← **no alcanza** |
| **4 × N3024** | **96** ← alcanza, con ~7% de reserva |

Siete por ciento de reserva es poco para tres años de vida. Si el presupuesto lo
permite, un N3048 (48 puertos) más un N3024 da 72+24 = 96 en dos equipos, menos
unidades que mantener y menos puertos de stack consumidos.

Aparte va el **switch de servidores**, que no debe compartirse con el acceso.

## 3. PoE para los 4 AP

| Modelo | PoE | Qué hacer |
|---|---|---|
| N3024**P** | Sí, 802.3at | Nada, se alimentan del switch |
| N3024 / N3024F | **No** | Inyectores 802.3at, uno por AP |

Un AP 802.11ax consume 15–20 W. Si son N3024P, descomentar el bloque
`power inline auto` del archivo de acceso.

## 4. Stack sí, pero no todo junto

**Recomendado**: los 4 switches de acceso en un stack, y el de servidores
**separado**.

Motivos:

- Un stack es un único dispositivo lógico: una falla de software o una
  actualización mal salida afecta a todos sus miembros a la vez. Separar los
  servidores deja el cluster Proxmox fuera de ese dominio de falla.
- Las VLAN 90 y 91 quedan físicamente contenidas en un equipo que no toca
  ningún puesto de usuario.
- El switch de servidores es el candidato natural a 10 GbE si más adelante se
  evalúa Ceph (hoy descartado: los R720 no tienen placas de 10 GbE).

Si igualmente se stackean todos, la configuración funciona, **siempre que los
dos uplinks al FortiGate lleven conjuntos de VLAN disjuntos**: uno 10/30/35/50/60
y el otro 20/25. Al ser disjuntos no hay bucle y el spanning-tree no bloquea
ninguno. Si se solapan, STP bloquea un uplink y se pierde la mitad del ancho de
banda hacia el firewall — que es justamente lo que los dos trunks separados
querían evitar.

## 5. Mapa de VLANs por puerto

### Switch de acceso → FortiGate `internal2`

| Puerto | Modo | VLAN |
|---|---|---|
| Gi1/0/24 | trunk | 10,30,35,50,60 tagged · nativa 999 |
| Puestos | access | 10 |
| Access Points | trunk | 30,35 tagged · **60 nativa (sin tag)** |
| Impresoras / IoT | access | 50 |

### Switch de servidores → FortiGate `internal3`

| Puerto | Modo | VLAN |
|---|---|---|
| Gi1/0/24 | trunk | **solo 20,25** · nativa 999 |
| PVE NIC1 (mgmt) | access | 25 |
| PVE NIC2 (VMs) | trunk | 20,50 tagged |
| PVE NIC3 (corosync) | access | **90** |
| PVE NIC4 (storage) | access | **91**, MTU 9216 |
| iDRAC / IPMI | access | 60 (ver nota en el archivo) |

## 6. Decisiones de la configuración y por qué

### VLAN 999 como nativa de los trunks

Por defecto la VLAN nativa de un trunk es la 1. Cualquier trama sin etiqueta que
llegue al trunk cae ahí. Usando una VLAN 999 vacía, una trama sin etiqueta no
termina en una red con datos reales. Cuesta una línea y cierra una clase entera
de errores de configuración.

### El puerto del AP es mixto, no un access

Los SSID viajan **etiquetados** (VLAN 30 y 35) porque el AP decide a qué VLAN
pertenece cada cliente según el SSID al que se asoció. La administración del
propio AP va **sin etiqueta** en la VLAN 60: así el AP toma IP de gestión apenas
se enchufa, sin configuración previa.

### `portfast` en los puertos de los nodos Proxmox, y por qué importa

Sin portfast, un puerto tarda unos 30 segundos en pasar a *forwarding* cuando el
link se levanta. En un reinicio de nodo ese retardo alcanza para que el cluster
lo dé por muerto y lo expulse. Es una de las causas más comunes de clusters
"inestables" que en realidad tienen un problema de switch.

### `bpduguard` sí en los puestos, **no** en los servidores

En un puesto de trabajo, bpduguard apaga el puerto si alguien enchufa un router
o un switch casero — exactamente lo que querés. En un hipervisor, los bridges
pueden generar tráfico que lo dispare y te apaga el puerto de un servidor en
producción. No va.

### Sin storm control en las VLAN de cluster

Un limitador descartando paquetes de corosync produce nodos que se reinician
solos. Si el firmware trae storm control activo por defecto en algún puerto, hay
que sacarlo explícitamente de los puertos de VLAN 90 y 91.

### `no ip routing` en ambos switches

Los N3000 pueden rutear. Si lo hacen, el tráfico entre VLANs esquiva el FortiGate
y todas las políticas de firewall dejan de aplicarse — sin ningún error visible,
simplemente deja de haber seguridad entre segmentos. La línea es barata.

### La gestión del switch de servidores va en VLAN 25, no en la 60

Para que ese switch sea administrable sin depender de que la VLAN 60 llegue hasta
el rack de servidores. Un switch que solo se administra por una VLAN que viaja
por otro switch es un switch que no vas a poder tocar justo cuando lo necesites.

## 7. Placeholders a completar

| Placeholder | Dónde |
|---|---|
| `<PASSWORD>` | usuario `admin` de cada switch |
| `<PASSWORD-ENABLE>` | modo privilegiado |
| `<COMUNIDAD-SNMP>` | solo si se va a monitorear por SNMP |

Las contraseñas con `encrypted` esperan un hash. Para poner texto plano y que el
switch lo cifre, sacar la palabra `encrypted` de la línea.

## 8. Antes de dar por terminado

```
show vlan
show interfaces switchport Gi1/0/24
show interfaces status
show spanning-tree brief
show mac address-table vlan 10
copy running-config startup-config      <- sin esto se pierde al reiniciar
```

En el switch de servidores, la verificación que más importa:

```
show interfaces switchport Gi1/0/24
    -> NO deben aparecer las VLAN 90 ni 91
show vlan id 90
    -> solo Gi1/0/3, Gi1/0/7 y Gi1/0/11
```

Si las VLAN 90 o 91 aparecen en el uplink, el diseño del cluster está roto
aunque todo parezca funcionar.
