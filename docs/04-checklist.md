# 04 — Checklist de implementación y datos faltantes

## A. Datos que hay que conseguir antes de empezar

| # | Dato | A quién | Estado |
|---|---|---|---|
| 1 | **Confirmar gateway de Telefónica** (¿209.13.171.177?) | Telefónica | ⬜ |
| 2 | ¿El ONT/módem de Telefónica entrega el /29 en bridge o hace NAT? | Telefónica | ⬜ |
| 3 | Ancho de banda real contratado (subida/bajada) | Telefónica | ⬜ |
| 4 | IP pública, máscara y GW de Claro + fecha de alta | Claro | ⬜ |
| 5 | Datos completos del túnel IPsec (ver tabla en doc 02) | Proveedor SAP | ⬜ |
| 6 | Redes que anuncia SAP (para descartar solape con 10.10.x.x) | Proveedor SAP | ⬜ |
| 7 | ¿SAP acepta una segunda IP pública para failover? | Proveedor SAP | ⬜ |
| 8 | Marca/modelo de los switches y si son administrables + PoE | Cliente | ⬜ |
| 9 | Marca/modelo de los 4 AP (FortiAP o terceros) | Cliente | ⬜ |
| 10 | ¿Hay Active Directory? IP del DC/DNS | Cliente | ⬜ |
| 11 | Cantidad de nodos Proxmox, NICs por nodo, discos | Cliente | ⬜ |
| 12 | ¿Hay NAS/cabina de storage existente? | Cliente | ⬜ |
| 13 | Licencia del FortiGate: ¿UTP/ATP contratada? | Distribuidor | ⬜ |

## B. Hardware a verificar / cotizar

- ⬜ Switch de acceso: 80 puestos + 4 AP → 2 × 48p PoE+ o 3 × 24p (dejar 20% libre).
- ⬜ Switch de servidores: idealmente 10 GbE si se piensa en Ceph; si no, 1 GbE
  administrable con soporte de jumbo frames.
- ⬜ PoE+ para los 4 AP (switch PoE o inyectores).
- ⬜ UPS para FortiGate + switches + nodos Proxmox (el cluster es muy sensible a
  cortes; un apagón sin UPS puede corromper el storage).
- ⬜ Segundo FortiGate 60F para HA (etapa 2, recomendado si SAP es crítico).

## C. Puesta en marcha — orden

1. ⬜ Firmware del FortiGate actualizado + registro FortiCare + licencias activas.
2. ⬜ `execute factoryreset` si el equipo viene con config previa.
3. ⬜ Bloques 1–2 del script por **consola serie**.
4. ⬜ WAN1: `execute ping 209.13.171.177` y `execute ping 8.8.8.8`.
5. ⬜ VLANs del FortiGate + VLANs y trunks en los switches.
6. ⬜ DHCP: probar un notebook en cada VLAN (IP, GW, DNS, internet).
7. ⬜ SD-WAN: `diagnose sys sdwan health-check`.
8. ⬜ AP: adopción, SSIDs, VLAN tagging, prueba de roaming entre los 4 AP.
9. ⬜ Túnel SAP: fase 1 y fase 2 arriba, prueba de conectividad end-to-end.
10. ⬜ Políticas: validar **cada fila** de la matriz de tráfico del doc 01, incluyendo
    los deny (invitados → LAN, IoT → internet).
11. ⬜ Nodos Proxmox: red, `pvecm status` con 3 votos, prueba de migración en vivo.
12. ⬜ Prueba de corte: desconectar una NIC de cluster y verificar que el quorum
    sobrevive por ring1.
13. ⬜ Migración de los 80 puestos (por tandas, no todos el mismo día).
14. ⬜ Backups: config del FortiGate, PBS del cluster, prueba de **restore**.
15. ⬜ Documentar: planilla de IPs, credenciales en gestor de contraseñas, diagrama final.

## D. Pruebas de failover (hacer antes de entregar)

| Prueba | Resultado esperado |
|---|---|
| Desconectar WAN1 (con Claro activo) | Internet sigue por WAN2 en < 15 s; túnel SAP cae y vuelve si hay túnel de respaldo |
| Reconectar WAN1 | Vuelve a WAN1 por prioridad |
| Apagar un nodo Proxmox | Cluster mantiene quorum (2/3); VMs con HA arrancan en otro nodo |
| Desconectar NIC de corosync (eno3) | Cluster sigue por ring1, sin reinicio de nodos |
| Cliente invitado intentando llegar a 10.10.20.10 | Bloqueado y logueado |
| Impresora intentando salir a internet | Bloqueado y logueado |

## E. Pendientes conocidos del diseño

- **Un solo firewall**: sin HA, una falla del 60F deja sin internet, sin SAP y sin
  ruteo entre VLANs a toda la empresa. Dejarlo asentado por escrito con el cliente.
- **SAP sobre un solo ISP** hasta que el proveedor autorice la IP de Claro.
- **Deep SSL inspection** pospuesta a etapa 2 (requiere distribución de certificado
  por GPO y lista de exclusiones).
- **Ceph descartado** con 1 GbE; si el cliente lo quiere, cotizar 10 GbE dedicado.
