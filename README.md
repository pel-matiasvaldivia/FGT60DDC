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

## Dato a verificar antes de cablear (importante)

El gateway informado **209.13.181.177** no pertenece a la red del IP público asignado:

- IP/máscara: `209.13.171.178 / 255.255.255.248` → red `209.13.171.176/29`
- Rango usable: `209.13.171.177` – `209.13.171.182`
- ``209.13.181.177`` no está en esa red; el gateway correcto es casi con seguridad **209.13.171.177** (error de tipeo: 181 → 171).

Toda la documentación asume `209.13.171.177` como gateway. **Confirmar con Telefónica antes del alta.**
