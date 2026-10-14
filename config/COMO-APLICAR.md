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
