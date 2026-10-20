# -*- coding: utf-8 -*-
"""Genera el diagrama de red del proyecto FT-60F-DDC en dos formatos:
   - .drawio (editable en diagrams.net, exporta a VSDX para Visio)
   - .svg    (Visio lo importa directo)
   Ambos desde la MISMA definicion de elementos."""
import html

# ---------------------------------------------------------------- paleta
C = {
    'wan'   : '#111827',
    'v10'   : '#1565C0',   # USERS
    'v20'   : '#2E7D32',   # SERVERS
    'v25'   : '#66A266',   # PVE-MGMT
    'v30'   : '#6A1B9A',   # WIFI-CORP
    'v35'   : '#AB47BC',   # WIFI-GUEST
    'v50'   : '#EF6C00',   # IOT
    'v60'   : '#455A64',   # MGMT
    'clu'   : '#C62828',   # VLAN 90/91
    'sap'   : '#00838F',   # IPsec
    'box'   : '#FFFFFF',
    'ink'   : '#1F2933',
    'muted' : '#9AA5B1',
}

nodes, edges, zones = [], [], []

def N(i,x,y,w,h,label,fill='#FFFFFF',stroke=C['ink'],shape='rect',fs=11,bold=False,dash=False):
    nodes.append(dict(id=i,x=x,y=y,w=w,h=h,label=label,fill=fill,stroke=stroke,
                      shape=shape,fs=fs,bold=bold,dash=dash))

def Z(i,x,y,w,h,label,stroke,fill='none'):
    zones.append(dict(id=i,x=x,y=y,w=w,h=h,label=label,stroke=stroke,fill=fill))

def E(a,b,label='',color=C['ink'],width=2,dash=False,pts=None,lx=None,ly=None):
    edges.append(dict(a=a,b=b,label=label,color=color,width=width,dash=dash,
                      pts=pts or [],lx=lx,ly=ly))

# ---------------------------------------------------------------- zonas
Z('z_isp'  ,  30,  20,1120,250,'PROVEEDORES DE INTERNET'          ,C['muted'])
Z('z_sap'  ,1190,  20, 460,250,'SAP (proveedor externo)'          ,C['sap'])
Z('z_acc'  ,  30, 600, 760,412,'RED DE ACCESO'                    ,C['muted'])
Z('z_srv'  , 820, 600, 600,412,'RED DE SERVIDORES'                ,C['muted'])
Z('z_clu'  , 852, 876, 536,112,'VLAN 90 (corosync) + VLAN 91 (storage) — SOLO L2, NO LLEGAN AL FORTIGATE',C['clu'])

# ---------------------------------------------------------------- nubes
N('internet', 430, 50,220,110,'INTERNET','#F3F4F6',C['ink'],'cloud',13,True)
N('sap'     ,1250, 50,340,110,'SAP\nRed remota: a definir\nPuertos 32xx / 33xx / 36xx / 443',
   '#E0F2F1',C['sap'],'cloud',11,True)

# ISPs
N('ont1',  90,190,300,60,'ONT Telefónica  (bridge)\n209.13.171.178/29 · GW .177\nDNS 200.0.243.10 / .11',
   '#FFFFFF',C['wan'],'rect',10)
N('ont2', 700,190,380,60,'ONT Claro  (bridge) — PENDIENTE DE ALTA\nSD-WAN ya preparado: solo habilitar miembro 2',
   '#F9FAFB',C['muted'],'rect',10)

# ---------------------------------------------------------------- FortiGate
N('fgt', 230,320,880,180,'','#FFFFFF',C['ink'],'rect')
N('fgt_t',250,332,840,34,'FortiGate 60F — FT-60F-DDC — FortiOS 7.2.6',
   'none','none','label',14,True)
N('fgt_s',250,364,840,24,'Zona SD-WAN · IPsec a SAP · NGFW (AV/IPS/WebFilter/AppCtrl) · DHCP · 13 políticas',
   'none','none','label',10)

N('p_wan1' , 255,400,120,44,'WAN1\nTelefónica'       ,'#FFF7ED',C['wan'],'rect',10,True)
N('p_wan2' , 385,400,120,44,'WAN2\nClaro (futuro)'   ,'#F9FAFB',C['muted'],'rect',10)
N('p_dmz'  , 515,400,110,44,'DMZ\nlibre'             ,'#F9FAFB',C['muted'],'rect',10)
N('p_int1' , 635,400,120,44,'internal1\nGESTIÓN'     ,'#ECEFF1',C['v60'],'rect',10,True)
N('p_int2' , 765,400,120,44,'internal2\nTRUNK ACC.'  ,'#E3F2FD',C['v10'],'rect',10,True)
N('p_int3' , 895,400,110,44,'internal3\nTRUNK SRV.'  ,'#E8F5E9',C['v20'],'rect',10,True)
N('p_ab'   ,1015, 400, 85,44,'A+B\nfortilink'        ,'#F9FAFB',C['muted'],'rect',10)

# notebook de rescate
N('mgmt',  60,540,190,70,'Notebook de soporte\n192.168.1.x (DHCP)\nGUI https://192.168.1.99',
   '#ECEFF1',C['v60'],'rect',10)

# ---------------------------------------------------------------- switches
N('sw_acc',  70,660,680,80,
  'SW-ACCESO — 4 × Dell N3024 en stack  (10.10.60.2)\n'
  'Trunk: VLAN 10,30,35,50,60 tagged · nativa 999 · no ip routing',
  '#E3F2FD',C['v10'],'rect',11,True)

N('sw_srv', 860,660,520,80,
  'SW-SERVIDORES — Dell N3024  (10.10.25.2)\n'
  'Trunk al FGT: SOLO VLAN 20,25 · VLAN 90/91 no salen de acá',
  '#E8F5E9',C['v20'],'rect',11,True)

# ---------------------------------------------------------------- acceso
N('pcs',  70,800,200,90,'80 DESKTOPS\nVLAN 10 — USERS\n10.10.10.0/24\nDHCP .50–.230',
  '#E3F2FD',C['v10'],'rect',10,True)
N('aps', 290,800,230,90,'4 ACCESS POINTS\nPuerto mixto: VLAN 30+35 tagged\nVLAN 60 nativa (mgmt del AP)\nSSID corp / invitados',
  '#F3E5F5',C['v30'],'rect',10,True)
N('iot', 540,800,210,90,'IMPRESORAS / CCTV / IoT\nVLAN 50 — 10.10.50.0/24\nSin salida a internet',
  '#FFF3E0',C['v50'],'rect',10,True)

# ---------------------------------------------------------------- nodos PVE
for k,(i,x) in enumerate([('pve1',876),('pve2',1046),('pve3',1216)]):
    N(i,x,790,150,80,f'PVE-0{k+1}\nmgmt 10.10.25.1{k+1}\nVMs VLAN 20',
      '#E8F5E9',C['v20'],'rect',10,True)
    N(i+'_c',x,906,150,64,f'eno3 → VLAN 90\n10.10.90.1{k+1}\neno4 → VLAN 91 · MTU 9000\n10.10.91.1{k+1}',
      '#FFEBEE',C['clu'],'rect',8)

# ---------------------------------------------------------------- aristas
E('internet','ont1','',C['wan'],2)
E('internet','ont2','',C['muted'],2,dash=True)
E('ont1','p_wan1','209.13.171.178/29',C['wan'],3)
E('ont2','p_wan2','pendiente',C['muted'],2,dash=True)
E('p_int1','mgmt','192.168.1.99 — rescate',C['v60'],2)
E('p_int2','sw_acc','TRUNK 802.1Q\n10,30,35,50,60',C['v10'],4)
E('p_int3','sw_srv','TRUNK 802.1Q\n20,25',C['v20'],4)
E('fgt','sap','IPsec IKEv2 sobre WAN1\nAES256/SHA256 · DH14',C['sap'],3,dash=True,lx=1180,ly=300)
E('sw_acc','pcs','VLAN 10',C['v10'],2)
E('sw_acc','aps','VLAN 30/35 + 60',C['v30'],2)
E('sw_acc','iot','VLAN 50',C['v50'],2)
E('sw_srv','pve1','',C['v20'],2)
E('sw_srv','pve2','VLAN 20 / 25',C['v20'],2)
E('sw_srv','pve3','',C['v20'],2)
E('pve1_c','pve2_c','',C['clu'],3)
E('pve2_c','pve3_c','',C['clu'],3)


# ---------------------------------------------------------------- leyenda
LEG = [
    ('VLAN 10 · USERS'      ,'10.10.10.0/24' ,'80 desktops'                 ,C['v10']),
    ('VLAN 20 · SERVERS'    ,'10.10.20.0/24' ,'VMs del cluster'             ,C['v20']),
    ('VLAN 25 · PVE-MGMT'   ,'10.10.25.0/24' ,'Admin de los nodos'          ,C['v25']),
    ('VLAN 30 · WIFI-CORP'  ,'10.10.30.0/24' ,'SSID corporativo'            ,C['v30']),
    ('VLAN 35 · WIFI-GUEST' ,'10.10.35.0/24' ,'Invitados — solo internet'   ,C['v35']),
    ('VLAN 50 · IOT-PRINT'  ,'10.10.50.0/24' ,'Sin salida a internet'       ,C['v50']),
    ('VLAN 60 · MGMT'       ,'10.10.60.0/24' ,'Switches, AP, iDRAC'         ,C['v60']),
    ('VLAN 90 · CLUSTER'    ,'10.10.90.0/24' ,'corosync — NO ruteada'       ,C['clu']),
    ('VLAN 91 · STORAGE'    ,'10.10.91.0/24' ,'migración — NO ruteada'      ,C['clu']),
    ('GESTIÓN / RESCATE'          ,'192.168.1.0/24','internal1 — rescate'         ,C['v60']),
]
LEG_X, LEG_Y = 1190, 320
Z('z_leg', LEG_X, LEG_Y, 460, 250, 'PLAN DE DIRECCIONAMIENTO', C['ink'])

NOTAS = "\n".join([
 "PUNTOS CLAVE DEL DISEÑO",
 "1.  El FortiGate es el ÚNICO punto de ruteo entre VLANs. Los switches son capa 2 pura (no ip routing): si no hay política escrita, no pasa.",
 "2.  Las VLAN 90 y 91 NO existen en el FortiGate: no tienen interfaz, ni IP, ni ruta; viven solo en el switch de servidores.",
 "—   corosync es sensible al jitter, y un firewall ocupado hace que los nodos se reinicien por watchdog.",
 "3.  Dos trunks separados (internal2 acceso / internal3 servidores): así un backup hacia los servidores no degrada la navegación de los 80 puestos.",
 "4.  Las políticas apuntan a la ZONA SD-WAN, no a wan1. Cuando llegue Claro se habilita el miembro 2 y no se toca ninguna política.",
 "5.  internal1 (192.168.1.99) queda siempre como puerto de gestión y rescate, fuera del diseño de VLANs.",
 "",
 "PENDIENTES",
 "·  Confirmar el gateway de Telefónica: 209.13.171.177. El informado (209.13.181.177) no pertenece a la red 209.13.171.176/29.",
 "·  Datos del túnel IPsec de SAP  ·  Alta de Claro y autorización de su IP pública por parte de SAP  ·  Zona horaria del FortiGate.",
 "·  Sin un segundo FortiGate en HA, el equipo es punto único de falla para internet, SAP y el ruteo entre VLANs.",
])

# ================================================================ DRAW.IO
def esc(t): return html.escape(t).replace('\n','&#10;')

def drawio():
    o = ['<mxfile host="app.diagrams.net" type="device">',
         '<diagram name="FT-60F-DDC">',
         '<mxGraphModel dx="1600" dy="1200" grid="1" gridSize="10" page="1" '
         'pageWidth="1700" pageHeight="1320" math="0" shadow="0"><root>',
         '<mxCell id="0"/><mxCell id="1" parent="0"/>']
    for z in zones:
        st = (f'rounded=1;arcSize=4;fillColor={z["fill"]};strokeColor={z["stroke"]};'
              'dashed=1;dashPattern=8 6;verticalAlign=top;align=left;spacingLeft=10;'
              'spacingTop=4;fontSize=11;fontStyle=1;fontColor=' + z['stroke'] + ';')
        o.append(f'<mxCell id="{z["id"]}" value="{esc(z["label"])}" style="{st}" vertex="1" parent="1">'
                 f'<mxGeometry x="{z["x"]}" y="{z["y"]}" width="{z["w"]}" height="{z["h"]}" as="geometry"/></mxCell>')
    for n in nodes:
        if n['shape'] == 'cloud':
            base = 'ellipse;shape=cloud;'
        elif n['shape'] == 'label':
            base = 'text;html=1;'
        else:
            base = 'rounded=1;arcSize=8;html=1;'
        st = (base + f'fillColor={n["fill"]};strokeColor={n["stroke"]};whiteSpace=wrap;'
              f'fontSize={n["fs"]};fontColor={C["ink"]};verticalAlign=middle;align=center;'
              + ('fontStyle=1;' if n['bold'] else '')
              + ('dashed=1;' if n['dash'] else 'dashed=0;'))
        o.append(f'<mxCell id="{n["id"]}" value="{esc(n["label"])}" style="{st}" vertex="1" parent="1">'
                 f'<mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry"/></mxCell>')
    # leyenda
    for k,(a,b,c,col) in enumerate(LEG):
        y = LEG_Y + 34 + k*21
        o.append(f'<mxCell id="lg{k}" value="" style="fillColor={col};strokeColor=none;" vertex="1" parent="1">'
                 f'<mxGeometry x="{LEG_X+14}" y="{y+4}" width="22" height="12" as="geometry"/></mxCell>')
        o.append(f'<mxCell id="lt{k}" value="{esc(a)}" style="text;html=1;align=left;fontSize=10;fontStyle=1;" '
                 f'vertex="1" parent="1"><mxGeometry x="{LEG_X+44}" y="{y}" width="150" height="20" as="geometry"/></mxCell>')
        o.append(f'<mxCell id="lu{k}" value="{esc(b)}" style="text;html=1;align=left;fontSize=10;fontFamily=Courier New;" '
                 f'vertex="1" parent="1"><mxGeometry x="{LEG_X+190}" y="{y}" width="110" height="20" as="geometry"/></mxCell>')
        o.append(f'<mxCell id="lv{k}" value="{esc(c)}" style="text;html=1;align=left;fontSize=10;fontColor=#4B5563;" '
                 f'vertex="1" parent="1"><mxGeometry x="{LEG_X+300}" y="{y}" width="160" height="20" as="geometry"/></mxCell>')
    # notas
    o.append(f'<mxCell id="notas" value="{esc(NOTAS)}" style="rounded=1;fillColor=#FFFBEB;strokeColor=#D97706;'
             'align=left;verticalAlign=top;spacingLeft=14;spacingTop=10;fontSize=11;whiteSpace=wrap;html=1;" '
             'vertex="1" parent="1"><mxGeometry x="30" y="1050" width="1620" height="230" as="geometry"/></mxCell>')
    # aristas
    for k,e in enumerate(edges):
        st = (f'edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor={e["color"]};'
              f'strokeWidth={e["width"]};endArrow=none;fontSize=10;fontColor={e["color"]};'
              'labelBackgroundColor=#FFFFFF;' + ('dashed=1;dashPattern=6 4;' if e['dash'] else ''))
        o.append(f'<mxCell id="e{k}" value="{esc(e["label"])}" style="{st}" edge="1" parent="1" '
                 f'source="{e["a"]}" target="{e["b"]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    o.append('</root></mxGraphModel></diagram></mxfile>')
    return '\n'.join(o)

# ================================================================ SVG
def clip(n, tx, ty):
    """punto del borde del rect n en direccion a (tx,ty)"""
    cx, cy = n['x']+n['w']/2, n['y']+n['h']/2
    dx, dy = tx-cx, ty-cy
    if dx == 0 and dy == 0: return cx, cy
    sx = (n['w']/2)/abs(dx) if dx else 1e9
    sy = (n['h']/2)/abs(dy) if dy else 1e9
    s = min(sx, sy)
    return cx+dx*s, cy+dy*s

def svg():
    by = {n['id']: n for n in nodes}
    W, H = 1700, 1310
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
         '<style>text{fill:%s}.t{font-size:11px}.b{font-weight:600}.s{font-size:10px}'
         '.m{font-family:Consolas,monospace;font-size:10px}</style>' % C['ink']]
    def txt(x,y,s,size=11,anchor='middle',bold=False,fill=None):
        for i,l in enumerate(str(s).split('\n')):
            o.append(f'<text x="{x:.0f}" y="{y+i*(size+3):.0f}" font-size="{size}" '
                     f'text-anchor="{anchor}"{" font-weight=\"600\"" if bold else ""}'
                     f'{f" fill=\"{fill}\"" if fill else ""}>{html.escape(l)}</text>')
    for z in zones:
        o.append(f'<rect x="{z["x"]}" y="{z["y"]}" width="{z["w"]}" height="{z["h"]}" rx="8" fill="none" '
                 f'stroke="{z["stroke"]}" stroke-dasharray="8 6" stroke-width="1.5" opacity="0.8"/>')
        txt(z['x']+12, z['y']+18, z['label'], 11, 'start', True, z['stroke'])
    for e in edges:
        a, b = by[e['a']], by[e['b']]
        acx, acy = a['x']+a['w']/2, a['y']+a['h']/2
        bcx, bcy = b['x']+b['w']/2, b['y']+b['h']/2
        x1,y1 = clip(a,bcx,bcy); x2,y2 = clip(b,acx,acy)
        da = ' stroke-dasharray="7 5"' if e['dash'] else ''
        o.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{e["color"]}" '
                 f'stroke-width="{e["width"]}"{da} stroke-linecap="round"/>')
        if e['label']:
            mx, my = (e['lx'], e['ly']) if e['lx'] else ((x1+x2)/2, (y1+y2)/2)
            lines = e['label'].split('\n')
            wmax = max(len(l) for l in lines)*5.6+12
            o.append(f'<rect x="{mx-wmax/2:.0f}" y="{my-9*len(lines):.0f}" width="{wmax:.0f}" '
                     f'height="{16*len(lines)+2}" rx="3" fill="#FFFFFF" opacity="0.92"/>')
            txt(mx, my-9*len(lines)+12, e['label'], 10, 'middle', False, e['color'])
    for n in nodes:
        if n['shape'] == 'label':
            txt(n['x']+n['w']/2, n['y']+16, n['label'], n['fs'], 'middle', n['bold']); continue
        if n['shape'] == 'cloud':
            o.append(f'<ellipse cx="{n["x"]+n["w"]/2}" cy="{n["y"]+n["h"]/2}" rx="{n["w"]/2}" ry="{n["h"]/2}" '
                     f'fill="{n["fill"]}" stroke="{n["stroke"]}" stroke-width="2"/>')
        else:
            o.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" rx="7" '
                     f'fill="{n["fill"]}" stroke="{n["stroke"]}" stroke-width="2"/>')
        ls = n['label'].split('\n')
        y0 = n['y']+n['h']/2 - (len(ls)-1)*(n['fs']+3)/2 + n['fs']/3
        txt(n['x']+n['w']/2, y0, n['label'], n['fs'], 'middle', n['bold'])
    # leyenda
    o.append(f'<rect x="{LEG_X}" y="{LEG_Y}" width="460" height="250" rx="8" fill="#FFFFFF" '
             f'stroke="{C["ink"]}" stroke-dasharray="8 6"/>')
    txt(LEG_X+12, LEG_Y+18, 'PLAN DE DIRECCIONAMIENTO', 11, 'start', True)
    for k,(a,b,c,col) in enumerate(LEG):
        y = LEG_Y+34+k*21
        o.append(f'<rect x="{LEG_X+14}" y="{y+4}" width="22" height="12" rx="2" fill="{col}"/>')
        txt(LEG_X+44,  y+14, a, 10, 'start', True)
        o.append(f'<text x="{LEG_X+190}" y="{y+14}" class="m">{html.escape(b)}</text>')
        txt(LEG_X+300, y+14, c, 10, 'start', False, '#4B5563')
    # notas
    o.append('<rect x="30" y="1050" width="1620" height="230" rx="8" fill="#FFFBEB" stroke="#D97706"/>')
    yy = 1074
    for line in NOTAS.split('\n'):
        if not line.strip(): yy += 8; continue
        bold = line.strip().isupper() or line.startswith('PENDIENTES')
        # wrap manual a ~185 caracteres
        while len(line) > 185:
            cut = line.rfind(' ', 0, 185)
            o.append(f'<text x="46" y="{yy}" font-size="11"{" font-weight=\"600\"" if bold else ""}>'
                     f'{html.escape(line[:cut])}</text>'); yy += 17; line = '    '+line[cut+1:]
        o.append(f'<text x="46" y="{yy}" font-size="11"{" font-weight=\"600\"" if bold else ""}>'
                 f'{html.escape(line)}</text>'); yy += 17
    o.append('</svg>')
    return '\n'.join(o)

open('/home/user/FGT60DDC/diagramas/red-FT-60F-DDC.drawio','w',encoding='utf-8').write(drawio())
open('/home/user/FGT60DDC/diagramas/red-FT-60F-DDC.svg','w',encoding='utf-8').write(svg())
print("drawio + svg generados")
