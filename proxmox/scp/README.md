# Despliegue de los nodos: perfiles XML de Dell (SCP) y respuestas de instalación

| Archivo | Nodo | iDRAC |
|---|---|---|
| `pve1-scp.xml` | pve1 | `10.10.60.31` |
| `pve2-scp.xml` | pve2 | `10.10.60.32` |
| `pve3-scp.xml` | pve3 | `10.10.60.33` |

Cada uno aplica, en una sola pasada, la configuración de **BIOS** (§1.2 del
README) y de **iDRAC** (§1.4) del nodo correspondiente.

---

## Advertencia que conviene leer antes

**Los nombres de atributo del SCP cambian entre versiones de firmware de iDRAC.**
Estos archivos son una **plantilla**, no un perfil exportado de tus equipos. El
procedimiento confiable es:

1. Configurar **un** nodo a mano (BIOS + iDRAC), siguiendo el README.
2. Exportar su SCP real:
   ```bash
   racadm -r 10.10.60.31 -u root -p <pass> get -f pve1-real.xml -t xml
   ```
3. Comparar ese archivo con la plantilla y quedarse con **los nombres de
   atributo del equipo real**.
4. Clonar para los otros dos nodos cambiando solo lo que es por nodo:
   la IP del iDRAC y el `DNSRacName`.

Si importás la plantilla directo, hacelo **primero en modo preview**: los
atributos que el firmware no reconozca se reportan y se ignoran, no rompen nada.

Requisitos: **iDRAC 7 Enterprise** con firmware reciente y el **Lifecycle
Controller habilitado**. Con firmware viejo de iDRAC7 el import de SCP puede no
estar disponible — ahí hay que actualizar primero (§1.1 del README).

---

## Qué NO hacen estos archivos

- **No configuran el RAID.** La creación de discos virtuales por SCP es
  específica de cada controladora y **destructiva** si se equivoca el FQDD.
  Hacelo a mano en la PERC (`Ctrl+R` al arrancar), como dice el §1.3.
- **No instalan Proxmox.** Para eso está `../answer/`.
- **No cambian la password del iDRAC.** El bloque está al final de cada XML,
  comentado. Dejar `calvin` en un equipo con IP de gestión es entregar el
  control del hardware: el iDRAC permite apagar, reinstalar y montar medios.

---

## Cómo importarlos

### Opción A — iDRAC web

`Configuration → Server Configuration Profile → Import`, subir el XML,
elegir componentes `BIOS, iDRAC` y tipo de apagado **Graceful**.

### Opción B — racadm (remoto)

```bash
# 1. PREVIEW: valida sin aplicar nada
racadm -r 10.10.60.31 -u root -p <pass> set -f pve1-scp.xml -t xml --preview

# 2. Ver el resultado del preview
racadm -r 10.10.60.31 -u root -p <pass> jobqueue view

# 3. Aplicar de verdad
racadm -r 10.10.60.31 -u root -p <pass> set -f pve1-scp.xml -t xml -b Graceful -w 1200

# 4. Seguir el avance (un cambio de BIOS implica reinicio)
racadm -r 10.10.60.31 -u root -p <pass> jobqueue view
```

### Opción C — Lifecycle Controller (sin red de gestión todavía)

`F10` al arrancar → *Configuration Services* → *Import Server Profile*,
desde un USB o un share de red.

---

## Orden recomendado por nodo

1. Actualizar firmware (BIOS, iDRAC, PERC, NICs) — §1.1 del README.
2. Configurar la IP del iDRAC a mano, lo mínimo para llegarle por red.
3. Importar el SCP del nodo → se reinicia y queda con BIOS + iDRAC listos.
4. Crear el RAID1 del SO en la PERC, a mano.
5. Crear los VD de datos (RAID0 por disco) o pasar a HBA en modo IT.
6. Instalar Proxmox (§3 del README, o `../answer/` para desatendido).

---

## Verificación posterior

```bash
racadm -r 10.10.60.31 -u root -p <pass> get BIOS.ProcSettings.ProcVirtualization
racadm -r 10.10.60.31 -u root -p <pass> get BIOS.BiosBootSettings.BootMode
racadm -r 10.10.60.31 -u root -p <pass> get iDRAC.NIC.Selection
racadm -r 10.10.60.31 -u root -p <pass> getsysinfo
```

Desde la red, lo más simple: `ping 10.10.60.31` y entrar a
`https://10.10.60.31`. Si no llega, revisar que el puerto del switch esté
**access en VLAN 60** (ver `docs/06-switches-dell-n3024.md`).
