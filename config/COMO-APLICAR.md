# Cómo bajarle la configuración al FortiGate 60F

## 1. `.conf` de script vs `.conf` de backup — no son lo mismo

| | Script CLI (este archivo) | Backup/restore de FortiGate |
|---|---|---|
| Qué es | Lista de comandos CLI que se pegan o se ejecutan | Volcado completo con header de firmware, modelo y número de serie |
| Cómo se aplica | Consola / SSH / `System > Scripts` | `System > Configuration > Restore` |
| Riesgo | Bajo: se aplica por partes y se verifica | Alto: reemplaza TODA la config; si el header no coincide con el equipo, lo rechaza o queda inconsistente |
| Reusable entre equipos | Sí | No (atado al serial/firmware) |

Por eso el entregable es **script CLI**. Un archivo de restore no se puede
fabricar a mano de forma confiable: hay que generarlo desde el propio equipo con
`execute backup config` una vez configurado.

## 2. Preparación

1. **Acceso al equipo.** En *este* FortiGate la interfaz `internal` es de tipo
   *VLAN Switch* y tiene un solo miembro (`internal1`, 192.168.1.99), así que
   `internal2` a `internal5` ya están libres: **la ETAPA 2 no es destructiva y
   alcanza con SSH o GUI por `internal1`**. Tené igual el cable de consola
   (RJ45-serial, PuTTY 9600 8N1) a mano por las dudas.
   Verificar antes con: `show system virtual-switch` y
   `get system interface physical | grep -A1 internal`.
2. Actualizar firmware a la última *mature* de la rama 7.4 **antes** de configurar.
3. Registrar el equipo en FortiCare y activar la licencia UTP/ATP. Sin licencia,
   los perfiles AV/IPS/WebFilter no se aplican (hay que quitar esas líneas de las
   políticas; está indicado en la ETAPA 6).
4. Si el equipo tiene configuración previa: `execute factoryreset` (confirma con `y`).
5. Reemplazar los placeholders. Están todos listados en la **ETAPA 0** del script.

## 3. Aplicación

### Opción A — Consola/SSH, etapa por etapa (recomendado)

Abrir el `.conf`, copiar **una etapa** y pegarla en la terminal. Verificar con los
comandos del bloque `VERIFICAR` al final de cada etapa, y recién después seguir.

```
FGT60F # execute backup config flash        <- antes y después de cada etapa
```

Si una línea falla, FortiOS imprime el error, **saltea esa línea y sigue con la
siguiente**. No asumas que todo entró: leé la salida.

### Opción B — Subir como script desde la GUI

`System > Scripts` (si no aparece: `System > Feature Visibility` → activar *Scripts*).
Permite subir el archivo completo y ejecutarlo. Viable en este equipo, ya que
ninguna etapa corta la sesión de administración por `internal1`. Aun así conviene
ir por etapas: si una línea falla en medio de un script largo, es más difícil
darse cuenta.

### Opción C — TFTP

```
execute restore config tftp <archivo> <ip-del-tftp>
```
Esto es para archivos de **backup**, no para scripts. No aplica acá.

## 4. Si algo sale mal

```
execute backup config flash                 # backup a la memoria flash
execute restore config flash <revision>     # volver a una revisión anterior
execute revision list config                # ver revisiones guardadas
```

El 60F guarda revisiones de configuración en flash. Siempre que hagas
`execute backup config flash` antes de una etapa, tenés punto de retorno.

Reset total (último recurso, con consola conectada):

```
execute factoryreset
```

## 5. Orden de las etapas y qué corta cada una

| Etapa | Qué hace | ¿Corta servicio? |
|---|---|---|
| 1 | Hostname, DNS, NTP, admin, WAN1, logs | No |
| 2 | Crea VLANs sobre internal2/internal3 y DHCP | No (en este equipo los puertos ya están libres) |
| 3 | SD-WAN + ruta default | Breve (segundos) |
| 4 | Objetos: direcciones, servicios, shapers | No |
| 5 | Túnel IPsec a SAP | No |
| 6 | Verificación de perfiles de seguridad | No (solo chequeos) |
| 7 | Políticas de firewall | Sí, habilita el tráfico |
| 8 | Backup y verificación final | No |

## 6. Dependencias entre etapas (no saltear orden)

```
ETAPA 1  base + WAN
   └─ ETAPA 2  VLANs      (las políticas referencian estas interfaces)
        └─ ETAPA 3  SD-WAN (las políticas referencian la zona SDWAN)
             └─ ETAPA 4  objetos (las políticas referencian direcciones y grupos)
                  └─ ETAPA 5  IPsec (la política 30 referencia la interfaz VPN-SAP)
                       └─ ETAPA 7  políticas
```

Si ejecutás la ETAPA 7 antes de la 5, las políticas 30 y 31 fallan con
*"interface VPN-SAP not found"* y el resto entra bien. No es grave, pero hay que
volver a correr esas dos.

---

# Anexo — Aplicación sobre la configuración existente (FT-60F-DDC)

A partir del backup `FT-60F-DDC_7-2_1575_202610141133` se detectó que el equipo
**no** estaba vacío. Estado real al 2026-10-14:

| Interfaz | Estado | Decisión |
|---|---|---|
| `internal` (hard-switch, miembro `internal1`) | 192.168.1.99/24, HTTPS+SSH, DHCP .110–.210 | **Acceso de gestión — no se toca** |
| `internal2` | VLAN 100 "LAN-ETH" 172.16.0.1/24 + DHCP 3 | No se toca |
| `internal3` | "LAN-WIFI" 10.10.1.1/24 + DHCP 4 | No se toca |
| `internal4`, `internal5` | Libres | **Trunks del proyecto** |
| `dmz` | 10.10.10.1/24, sin DHCP ni políticas | **IP liberada** (chocaba con VLAN 10) |
| `a` + `b` → `fortilink` | 10.255.1.1/24 + DHCP 2 | Se mantiene (FortiSwitch/FortiAP) |
| `wan1`, `wan2` | Modo DHCP | wan1 pasa a estática |
| Políticas | Una sola: `internal → wan1, ALL, NAT` | Se reemplaza por `internal → SDWAN` |

## Dos entregables

| Archivo | Qué es | Recomendado |
|---|---|---|
| `fortigate-60f-delta.conf` | Script CLI que aplica **sólo los cambios** sobre lo que ya existe | **Sí** |
| `FT-60F-DDC-modificado.conf.yaml` | El backup con el diseño ya integrado | Sólo si se confirma que el equipo restaura YAML |

### Por qué el delta y no el restore

1. Una restauración **reemplaza toda la configuración y reinicia** el equipo.
   Cualquier error deja el FortiGate inaccesible y obliga a ir al sitio.
2. El archivo del cliente está en **formato YAML**. El backup YAML de FortiOS es
   un formato de lectura y auditoría; hay que verificar en el propio equipo que
   acepte restaurarlo antes de depender de él. Un `.conf` CLI generado por el
   mismo equipo con `execute backup config` sí se restaura siempre.
3. El delta no toca ninguna interfaz existente, así que el acceso por
   192.168.1.99 está garantizado durante todo el procedimiento.

## El único momento delicado del delta: la sección C

La política 1 actual apunta a `wan1` directamente. FortiOS no permite agregar
`wan1` a SD-WAN mientras exista esa referencia, así que el script la borra y la
recrea apuntando a la zona.

- **Sí** se interrumpe: la salida a internet de la red 192.168.1.x, unos segundos.
- **No** se interrumpe: el acceso a la GUI y SSH por 192.168.1.99 (es tráfico
  local a la interfaz, no pasa por políticas de firewall).

## Conflicto de subred resuelto

`dmz` tenía 10.10.10.1/24, la misma red que la VLAN 10 del diseño. FortiOS
rechaza subredes superpuestas. Como el `dmz` no tiene DHCP, ni políticas, ni
objetos que lo referencien, se libera su IP. Rollback de una línea:

```
config system interface
    edit "dmz"
        set ip 10.10.10.1 255.255.255.0
    next
end
```

Alternativa si se prefiere conservar el `dmz`: renumerar la VLAN de usuarios a
`10.10.110.0/24` (cambiar `10.10.10.` por `10.10.110.` en la interfaz, el DHCP
10, el objeto `NET-USERS` y el phase2 `VPN-SAP-P2-USR`).

## Lo que queda pendiente de completar

| Placeholder | Dónde | Dato |
|---|---|---|
| `<IP-DNS-INTERNO>` | DHCP 10 y 30 | IP del DC/DNS interno (si no existe aún, usar 10.10.10.1) |
| `<IP-PEER-SAP>` `<PSK-SAP>` | phase1 `VPN-SAP` | Proveedor SAP |
| `<RED-SAP>` `<MASK-SAP>` | objeto `NET-SAP`, phase2 y ruta 2 | Proveedor SAP |
| Zona horaria | `system global`, hoy en `04` | Verificar con `set timezone ?` |

## Endurecimiento final (NO antes de validar todo)

Los `trusthost` del usuario `admin` quedaron deliberadamente **sin aplicar**: es
la causa número uno de bloqueos. Aplicarlos recién al final, con consola a mano,
y **siempre incluyendo la red de gestión actual**:

```
config system admin
    edit "admin"
        set trusthost1 192.168.1.0 255.255.255.0     # NO SACAR
        set trusthost2 10.10.60.0 255.255.255.0
        set trusthost3 10.10.10.0 255.255.255.0
    next
end
```
