# Proyecto FortiGate 60F — Diseño de red (80 desktops / 4 AP / SAP por IPsec / Cluster Proxmox)

Documentación de diseño e implementación del borde de red con FortiGate 60F,
doble proveedor de internet (Telefónica + Claro), WLAN corporativa, VPN IPsec
hacia SAP y una red dedicada de servidores para un cluster Proxmox VE.

## Contenido

| Archivo | Contenido |
|---|---|
| [docs/01-diseno-y-layout.md](docs/01-diseno-y-layout.md) | Layout físico, VLANs, direccionamiento, matriz de tráfico |
| [docs/02-fortigate-config.md](docs/02-fortigate-config.md) | Explicación de la configuración por bloques |
| [config/fortigate-60f.conf](config/fortigate-60f.conf) | Script CLI completo, listo para adaptar y pegar |
| [docs/03-proxmox-cluster.md](docs/03-proxmox-cluster.md) | Red del cluster Proxmox (corosync, migración, storage) |
| [docs/04-checklist.md](docs/04-checklist.md) | Checklist de puesta en marcha y datos a pedir |

## Direccionamiento WAN (confirmado 2026-10)

| Dato | Valor |
|---|---|
| IP pública | `209.13.181.178` |
| Máscara | `255.255.255.240` (/28) |
| Red | `209.13.181.176/28` |
| Rango usable | `209.13.181.177` – `209.13.181.190` (14 IPs) |
| **Gateway** | `209.13.181.177` |
| Broadcast | `209.13.181.191` |
| DNS | `200.0.243.10` / `200.0.243.11` |

Los datos iniciales del proyecto tenían la IP como `209.13.171.178/29`. El valor
correcto es `209.13.181.178/28`: con esa corrección el gateway `209.13.181.177`
queda dentro de la red y todo es coherente.

**Quedan 12 IPs públicas libres** (`.179` a `.190`) para publicar servicios por
DNAT/VIP más adelante, si el cliente lo necesita.

## Índice de documentación ampliado

| Archivo | Contenido |
|---|---|
| [docs/05-dia-de-instalacion.md](docs/05-dia-de-instalacion.md) | Mapa de conexión física, config de los switches, orden de encendido |
| [docs/06-switches-dell-n3024.md](docs/06-switches-dell-n3024.md) | Switches Dell N3024: diseño, dimensionamiento y decisiones |
| [config/fortigate-60f-puesta-a-punto.conf](config/fortigate-60f-puesta-a-punto.conf) | **Script vigente** para el equipo nuevo, en 9 etapas |
| [config/temporal-internet-internal4.conf](config/temporal-internet-internal4.conf) | Acceso temporal a internet por el puerto 4 |
| [config/switches/](config/switches/) | Config de los Dell N3024 (acceso y servidores) |
| [diagramas/](diagramas/) | Diagrama de red: .drawio, .svg y .png |
