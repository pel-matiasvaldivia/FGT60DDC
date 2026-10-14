# 02 — Configuración del FortiGate, bloque por bloque

El script completo está en [`../config/fortigate-60f.conf`](../config/fortigate-60f.conf).
Acá va el *por qué* de cada bloque y el orden de ejecución.

> **Nota de versión**: el script ahora está dividido en **ETAPAS 0 a 8** para
> aplicarlo por partes. La correspondencia con los "bloques" de este documento es:
> ETAPA 1 = bloques 2–3 (sistema + WAN) · ETAPA 2 = bloques 1, 4, 5 (puertos, VLANs, DHCP) ·
> ETAPA 3 = bloque 6 (SD-WAN) · ETAPA 4 = objetos (direcciones, servicios, shapers) ·
> ETAPA 5 = bloque 7 (IPsec) · ETAPA 6 = perfiles · ETAPA 7 = políticas · ETAPA 8 = cierre.
> Se usa el perfil SSL de fábrica `certificate-inspection` (no se crea uno propio).


## Orden de trabajo recomendado

1. **Consola serie** (no SSH): el bloque 1 rompe el switch interno y te deja afuera.
2. Firmware: actualizar a la última versión *mature* de la rama 7.4 antes de configurar.
3. Registrar el equipo en FortiCare y activar licencias (sin eso, AV/IPS/WebFilter no corren).
4. Aplicar bloques 1–5 → verificar VLANs y DHCP con un notebook.
5. Aplicar 6–7 (SD-WAN + IPsec) → validar internet y túnel.
6. Aplicar 8–11 (perfiles, políticas, shapers) → probar cada flujo de la matriz.
7. `execute backup config flash` y backup externo.

## Bloque 1 — Liberar puertos del hardware switch

En el 60F los puertos 1–5 vienen en un *virtual switch* llamado `internal`. No se
pueden crear VLANs 802.1Q sobre un miembro del grupo, así que hay que sacar
`internal1` e `internal2`. Verificar primero:

```
show system virtual-switch
get hardware nic internal1
```

Si el equipo ya tiene políticas/DHCP asociados a `internal`, FortiOS rechaza el
`delete` hasta que se borren esas referencias. Por eso conviene hacerlo en un equipo
recién salido de fábrica o tras un `execute factoryreset`.

## Bloque 2 — Global, DNS, NTP, admin

- `admin-sport 8443` libera 443 para otros usos y reduce escaneo automatizado.
- Los DNS de Telefónica van en el FortiGate; **los clientes apuntan al DNS interno**
  (AD en 10.10.20.10) y ese reenvía. Si no hay AD, los clientes van al FortiGate.
- NTP correcto es requisito para IPsec (y para Kerberos/AD y para los logs).
- `strong-crypto enable` deshabilita cifrados débiles en la administración.

## Bloque 3 — WAN

`estimated-upstream/downstream-bandwidth` no limita nada: lo usa SD-WAN para
calcular utilización. Poner los valores reales del servicio contratado.

WAN2 queda definida pero `status down` para no generar alarmas hasta que Claro exista.

## Bloque 4 — VLANs

Dos trunks separados (puerto 1 → acceso, puerto 2 → servidores) para que el tráfico
de usuarios y el de servidores no compitan por el mismo uplink de 1 Gbps. Si el
switch soporta LACP, se puede agregar un segundo link por trunk (`config system
interface` → `type aggregate`).

`allowaccess` sólo tiene `ping` en las VLANs de producción. La administración vive
en VLAN 60.

**Las VLANs 90 y 91 no existen en el FortiGate.** Es el punto clave del diseño del
cluster: sin interfaz ruteada, no hay forma de que ese tráfico salga del switch.

## Bloque 5 — DHCP

Rangos .50–.230 en cada VLAN: deja .2–.49 para equipos fijos y .231–.254 para
reservas futuras. Los servidores y los nodos Proxmox van con IP fija (o reserva
por MAC, nunca dinámica pura).

## Bloque 6 — SD-WAN

Se crea la zona con un solo miembro activo. **Las políticas apuntan a la zona
`SDWAN`, no a `wan1`**: eso es lo que permite sumar Claro después sin reescribir
nada. Health-check a tres destinos para distinguir "se cayó el ISP" de "se cayó el
destino".

Para activar Claro:

```
config system sdwan
    config members
        edit 2
            set status enable
            set gateway <GW-CLARO>
        next
    end
end
config system interface
    edit "wan2"
        set status up
    next
end
```

## Bloque 7 — IPsec a SAP

Túnel *route-based* (interfaz virtual + ruta estática), que es lo que permite
después hacer failover y monitoreo. Datos a pedir al proveedor de SAP:

| Dato | Valor |
|---|---|
| IP pública del peer | |
| IKE versión (1/2) y modo | |
| Cifrado/hash/DH fase 1 | |
| Cifrado/hash/PFS/DH fase 2 | |
| Lifetimes fase 1 / fase 2 | |
| Redes locales a anunciar (las nuestras) | |
| Redes remotas (de SAP) | |
| PSK o certificado | |
| ¿Requiere NAT de nuestra fuente a una IP específica? | |
| ¿Autoriza una segunda IP pública (Claro) para redundancia? | |

Si SAP exige que lleguemos con una única IP de origen (muy común), se agrega un
IP pool y NAT en la política 30:

```
config firewall ippool
    edit "NAT-TO-SAP"
        set startip <IP-ASIGNADA-POR-SAP>
        set endip <IP-ASIGNADA-POR-SAP>
    next
end
config firewall policy
    edit 30
        set nat enable
        set ippool enable
        set poolname "NAT-TO-SAP"
    next
end
```

## Bloques 8–9 — Perfiles y políticas

Arrancar con `certificate-inspection` (inspecciona SNI/certificado sin romper TLS).
La *deep inspection* se deja para una segunda etapa, con el certificado del
FortiGate distribuido por GPO, y **siempre con exclusión del tráfico de SAP, banca
y AFIP** para no romper pinning.

Puntos de orden importantes:

- El deny de invitados hacia RFC1918 va **antes** del permit a internet.
- La política 31 (SAP → LAN) está en `ALL` sólo como punto de partida: acotarla a lo
  que SAP realmente inicie, o eliminarla si el tráfico es siempre saliente.
- La política 999 de deny con log no cambia el comportamiento (ya hay deny
  implícito) pero deja rastro de lo que se bloquea, que es lo que vas a necesitar
  cuando algo "no funcione".

## Verificación

```
diagnose sys sdwan health-check            # SLA de cada ISP
diagnose vpn ike gateway list              # fase 1
diagnose vpn tunnel list                   # fase 2 y contadores
get router info routing-table all
diagnose sniffer packet any 'host <IP-SAP>' 4 0 a
execute ping-options source 10.10.20.1 ; execute ping <IP-EN-SAP>
diagnose debug flow trace start 20         # para depurar una política que no matchea
```
