# -*- coding: utf-8 -*-
import html

C = {'wan':'#111827','v10':'#1565C0','v20':'#2E7D32','mgmt':'#455A64',
     'libre':'#9AA5B1','ink':'#1F2933','clu':'#C62828','ap':'#6A1B9A','iot':'#EF6C00'}

W,H = 1500, 1080
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
   'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
   f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>']

def box(x,y,w,h,fill='#FFF',stroke=C['ink'],sw=2,rx=7,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def txt(x,y,s,size=12,anchor='middle',bold=False,fill=C['ink'],mono=False):
    f=' font-family="Consolas,monospace"' if mono else ''
    b=' font-weight="700"' if bold else ''
    for i,l in enumerate(str(s).split('\n')):
        o.append(f'<text x="{x}" y="{y+i*(size+3)}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"{b}{f}>{html.escape(l)}</text>')
def cable(pts,color,wdt=4,dash=None,label=None,lx=None,ly=None):
    d=' stroke-dasharray="8 5"' if dash else ''
    p=' '.join(f'{x},{y}' for x,y in pts)
    o.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{wdt}"{d} stroke-linejoin="round" stroke-linecap="round"/>')
    if label:
        o.append(f'<rect x="{lx-62}" y="{ly-13}" width="124" height="20" rx="3" fill="#FFF" opacity="0.95"/>')
        txt(lx,ly+2,label,10,'middle',True,color)

# ============================ FORTIGATE ============================
FX,FY,FW,FH = 420, 40, 660, 150
box(FX,FY,FW,FH,'#FFFFFF',C['ink'],2.5)
txt(FX+FW/2, FY+28, 'FortiGate 60F — FT-60F-DDC', 16, 'middle', True)
txt(FX+FW/2, FY+48, '209.13.181.178/28 · GW 209.13.181.177', 10)

ports=[('WAN1','Telefónica',C['wan'],1),('WAN2','Claro (futuro)',C['libre'],0),
       ('DMZ','libre',C['libre'],0),('int1','GESTIÓN',C['mgmt'],1),
       ('int2','TRUNK acceso',C['v10'],1),('int3','TRUNK servid.',C['v20'],1),
       ('int4','libre',C['libre'],0),('int5','libre',C['libre'],0)]
pw,gap = 72,8
px0 = FX + (FW - (len(ports)*pw + (len(ports)-1)*gap))/2
pcx={}
for i,(n,sub,col,act) in enumerate(ports):
    x=px0+i*(pw+gap); y=FY+72
    box(x,y,pw,52,'#FFFFFF' if act else '#F6F7F8',col,2 if act else 1.2,5)
    txt(x+pw/2,y+20,n,11,'middle',True,col)
    txt(x+pw/2,y+36,sub,8,'middle',False,'#4B5563')
    pcx[n]=(x+pw/2, y+52)

# ============================ SW-CORE-ACC ============================
AX,AY,AW,AH = 60, 300, 620, 120
box(AX,AY,AW,AH,'#E3F2FD',C['v10'],2.5)
txt(AX+AW/2,AY+26,'SW-CORE-ACC  ·  Dell N3024  ·  10.10.60.2',14,'middle',True)
txt(AX+AW/2,AY+44,'raíz de spanning tree (priority 4096)',9,'middle',False,'#4B5563')
grupos=[('1','UPLINK',C['v10']),('2-4','a los SMC',C['v10']),('5-8','AP',C['ap']),
        ('9-13','IoT',C['iot']),('14-24','11 puestos',C['v10'])]
gw_,gg = 108,10
gx0 = AX + (AW-(len(grupos)*gw_+(len(grupos)-1)*gg))/2
gcx={}
for i,(n,sub,col) in enumerate(grupos):
    x=gx0+i*(gw_+gg); y=AY+58
    box(x,y,gw_,46,'#FFFFFF',col,1.8,5)
    txt(x+gw_/2,y+19,f'Gi1/0/{n}',10,'middle',True,col)
    txt(x+gw_/2,y+34,sub,8,'middle',False,'#4B5563')
    gcx[n]=(x+gw_/2,y)
    if n in ('2-4',): gcx[n+'_b']=(x+gw_/2,y+46)

# ============================ SW-SRV ============================
SX,SY,SW_,SH = 870, 300, 570, 120
box(SX,SY,SW_,SH,'#E8F5E9',C['v20'],2.5)
txt(SX+SW_/2,SY+26,'SW-SRV-01  ·  Dell N3024  ·  10.10.25.2',14,'middle',True)
txt(SX+SW_/2,SY+44,'VLAN 90 y 91 NO salen por el uplink',9,'middle',False,C['clu'])
gs=[('24','UPLINK',C['v20']),('1-12','3 nodos PVE',C['v20']),
    ('13-20','servidores',C['v20']),('21-23','iDRAC',C['mgmt'])]
gw2=128
gx2 = SX + (SW_-(len(gs)*gw2+(len(gs)-1)*gg))/2
scx={}
for i,(n,sub,col) in enumerate(gs):
    x=gx2+i*(gw2+gg); y=SY+58
    box(x,y,gw2,46,'#FFFFFF',col,1.8,5)
    txt(x+gw2/2,y+19,f'Gi1/0/{n}',10,'middle',True,col)
    txt(x+gw2/2,y+34,sub,8,'middle',False,'#4B5563')
    scx[n]=(x+gw2/2,y)

# ============================ SMC ============================
smc=[]
for i,(nom,ip) in enumerate([('SMC-01','10.10.10.2'),('SMC-02','10.10.10.3'),('SMC-03','10.10.10.4')]):
    x=70+i*205; y=540
    box(x,y,185,96,'#F6F7F8',C['libre'],2)
    txt(x+92,y+24,nom,13,'middle',True)
    txt(x+92,y+41,ip,9,'middle',False,'#4B5563',mono=True)
    box(x+16,y+52,70,32,'#FFFFFF',C['v10'],1.6,4)
    txt(x+51,y+72,'p24 ↑',10,'middle',True,C['v10'])
    box(x+99,y+52,70,32,'#FFFFFF',C['v10'],1.6,4)
    txt(x+134,y+72,'p1-23',10,'middle',True,C['v10'])
    txt(x+134,y+92,'23 puestos',8,'middle',False,'#4B5563')
    smc.append((x+51,y))

# ============================ CABLES ============================
# WAN1
cable([pcx['WAN1'],(pcx['WAN1'][0],250),(300,250),(300,215)],C['wan'],4)
box(170,165,260,50,'#FFFFFF',C['wan'],2,6)
txt(300,186,'ONT Telefónica',12,'middle',True)
txt(300,203,'modo bridge',9,'middle',False,'#4B5563')

# internal1 -> notebook
cable([pcx['int1'],(pcx['int1'][0],235),(1240,235),(1240,190)],C['mgmt'],3)
box(1120,120,240,70,'#ECEFF1',C['mgmt'],2,6)
txt(1240,146,'Notebook soporte',12,'middle',True)
txt(1240,163,'192.168.1.99',9,'middle',False,'#4B5563',mono=True)
txt(1240,178,'puerto de rescate',8,'middle',False,'#4B5563')

# internal2 -> SW-CORE-ACC Gi1/0/1
cable([pcx['int2'],(pcx['int2'][0],255),(gcx['1'][0],255),gcx['1']],C['v10'],5,
      label='VLAN 10,30,35,50,60', lx=600, ly=252)
# internal3 -> SW-SRV Gi1/0/24
cable([pcx['int3'],(pcx['int3'][0],272),(scx['24'][0],272),scx['24']],C['v20'],5,
      label='VLAN 20,25', lx=1010, ly=269)
# Dell acceso -> 3 SMC
for i,(sx,sy) in enumerate(smc):
    bx,by = gcx['2-4_b']
    cable([(bx,by),(bx,470+i*12),(sx,470+i*12),(sx,sy)],C['v10'],3)
o.append('<rect x="415" y="498" width="330" height="22" rx="3" fill="#FFF" opacity="0.95"/>')
txt(580,513,'3 cables · access VLAN 10 · el Dell pone la etiqueta',10,'middle',True,C['v10'])

# ============================ TABLA ============================
TX,TY = 60, 700
box(TX,TY,1380,300,'#FFFFFF',C['ink'],1.5,8,'8 6')
txt(TX+16,TY+26,'TABLA DE CABLEADO',12,'start',True)
cols=[(TX+20,'ORIGEN'),(TX+330,'DESTINO'),(TX+660,'TIPO'),(TX+900,'LLEVA')]
for x,t in cols: txt(x,TY+52,t,10,'start',True,'#4B5563')
o.append(f'<line x1="{TX+16}" y1="{TY+60}" x2="{TX+1364}" y2="{TY+60}" stroke="#D1D5DB"/>')
filas=[
 ('FortiGate  WAN1','ONT Telefónica','UTP recto','Internet 209.13.181.178/28',C['wan']),
 ('FortiGate  internal1','Notebook de soporte','UTP recto','Gestión 192.168.1.99 — rescate',C['mgmt']),
 ('FortiGate  internal2','SW-CORE-ACC  Gi1/0/1','UTP recto','TRUNK: VLAN 10,30,35,50,60',C['v10']),
 ('FortiGate  internal3','SW-SRV-01  Gi1/0/24','UTP recto','TRUNK: VLAN 20,25',C['v20']),
 ('SW-CORE-ACC  Gi1/0/2','SMC-01  puerto 24','UTP recto','Access VLAN 10',C['v10']),
 ('SW-CORE-ACC  Gi1/0/3','SMC-02  puerto 24','UTP recto','Access VLAN 10',C['v10']),
 ('SW-CORE-ACC  Gi1/0/4','SMC-03  puerto 24','UTP recto','Access VLAN 10',C['v10']),
 ('SW-CORE-ACC  Gi1/0/5-8','4 AP (vía inyector PoE)','UTP recto','VLAN 30/35 tagged + 60 nativa',C['ap']),
 ('SW-CORE-ACC  Gi1/0/9-13','Impresoras / CCTV','UTP recto','Access VLAN 50',C['iot']),
 ('SW-CORE-ACC  Gi1/0/14-24','11 puestos','UTP recto','Access VLAN 10',C['v10']),
 ('SMC-01/02/03  p1-23','69 puestos','UTP recto','Sin VLAN — switches planos',C['v10']),
 ('SW-SRV-01  Gi1/0/1-12','3 nodos Proxmox','UTP recto','VLAN 25/20/90/91 (4 NIC por nodo)',C['v20']),
]
for i,(a,b,c,d,col) in enumerate(filas):
    y=TY+82+i*18
    o.append(f'<rect x="{TX+16}" y="{y-13}" width="8" height="10" rx="2" fill="{col}"/>')
    txt(TX+34,y,a,9.5,'start',True); txt(TX+330,y,b,9.5,'start')
    txt(TX+660,y,c,9.5,'start',False,'#4B5563'); txt(TX+900,y,d,9.5,'start',False,col)

o.append('</svg>')
open('/home/user/FGT60DDC/diagramas/cableado-rack.svg','w',encoding='utf-8').write('\n'.join(o))
print('SVG generado')
