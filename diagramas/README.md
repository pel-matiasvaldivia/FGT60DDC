# Diagrama de red — FT-60F-DDC

| Archivo | Para qué sirve |
|---|---|
| `red-FT-60F-DDC.drawio` | **Editable**. Se abre en [app.diagrams.net](https://app.diagrams.net) (gratis, sin instalar) o en la app de escritorio. Es el archivo del que salen los demás. |
| `red-FT-60F-DDC.svg` | Vectorial. **Visio lo importa directo**: `Insertar → Imágenes → Este dispositivo`, y después `Clic derecho → Grupo → Desagrupar` para editar las formas. |
| `red-FT-60F-DDC.png` | Para pegar en un informe, un mail o una presentación. |
| `generar-diagrama.py` | Genera el `.drawio` y el `.svg` desde una sola definición. Si cambia el diseño, se edita acá y se regeneran los dos. |

## Cómo obtener un .vsdx nativo de Visio

1. Abrir `red-FT-60F-DDC.drawio` en [app.diagrams.net](https://app.diagrams.net).
2. `File → Export as → VSDX`.
3. El archivo que baja se abre en Visio con las formas editables.

Es el camino confiable: un `.vsdx` generado a mano, fuera de Visio o de una
herramienta que lo soporte de verdad, suele abrir con formas rotas o no abrir.

## Qué muestra

- Los dos proveedores (Telefónica activo, Claro preparado en SD-WAN)
- El FortiGate 60F con la asignación real de cada puerto
- El túnel IPsec hacia SAP
- Los dos trunks 802.1Q separados: acceso (`internal2`) y servidores (`internal3`)
- Los switches Dell N3024 con su configuración resumida
- Los 80 puestos, los 4 AP con su esquema de VLANs mixto, impresoras/IoT
- Los 3 nodos Proxmox y **las VLAN 90/91 encerradas fuera del alcance del FortiGate**
- El puerto de gestión/rescate `internal1` (192.168.1.99)
- El plan de direccionamiento completo y los pendientes del proyecto

## Regenerar

```
pip install cairosvg          # solo si se quiere exportar el PNG
python3 generar-diagrama.py
```
