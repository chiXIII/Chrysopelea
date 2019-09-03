from chrysopelea import *

V = 30

back = 19
h = 15
front = 5

hlist = []
cllist = []
back = 29
cs_start = 8
cs_len = 2.5
web = 4
for h in [4.8]:
    front = 20-2/math.sqrt(3)*h
    nose = 20*math.sqrt(3)/2 - h
    print('h',h)
#    
    s = Surface('Wing')
    n = naca(position=(0,0,0),chord=nose+h+web)
    s.add_section(n)
    m = naca()

    if cs_start-front/2 < -1:
    	m = naca(position=(cs_start*math.sqrt(3),cs_start-0.1,0),chord=nose+h+web-cs_start*math.sqrt(3))
    	s.add_section(m)
    	n = naca(position=(cs_start*math.sqrt(3),cs_start,0),chord=nose+h+cs_len-cs_start*math.sqrt(3))
    	n.add_control(Control('elevon',xhinge=cs_len/(nose+h+cs_len-cs_start*math.sqrt(3)) ))
    	s.add_section(n)
    	n = naca(position=(nose,front/2,0),chord=h+cs_len)
    elif -1 <= cs_start-front/2 <= 1:
    	n = naca(position=(nose,front/2-0.1,0),chord=h+web)
    	s.add_section(n)
    	n = naca(position=(nose,front/2,0),chord=h+cs_len)
    else:
    	n = naca(position=(nose,front/2,0),chord=h+web)

    if cs_start-front/2 <= 1:
    	n.add_control(Control('elevon',xhinge=cs_len/(h+cs_len)))
    s.add_section(n)

    if cs_start-front/2 > 1:
    	m = naca(position=(nose+(cs_start-front/2)*h*2/front,cs_start-0.1,0),chord=h*(back/2-cs_start)/(back/2-front/2)+web)
    	s.add_section(m)
    	n = naca(position=(nose+(cs_start-front/2)*h*2/front,cs_start,0),chord=h*(back/2-cs_start)/(back/2-front/2)+cs_len)
    	n.add_control(Control('elevon',xhinge=cs_len/(h*(back/2-cs_start)/(back/2-front/2)+cs_len)))
    	s.add_section(n)

    n = naca(position=(nose+h,back/2,0),chord=cs_len)
    n.add_control(Control('elevon',xhinge=1))
    s.add_section(n)

    a = avl()
    a.xyzref = (0, 0, 0)
    a.add_surface(s)

    """
    t0 = Surface('vstab0')
    c = 2.5
    height = 3
    sweep = 30*math.pi/180
    vstabloc = cs_start
    n = naca(position=(nose+h,vstabloc,0),chord=c)
    t0.add_section(n)
    z = math.sqrt(height**2-c**2)
    n = naca(position=(nose+h+z*math.sin(sweep),vstabloc,z),chord=c)
    t0.add_section(n)
    z =  height
    n = naca(position=(nose+h+z*math.sin(sweep),vstabloc,z),chord=0)
    t0.add_section(n)
    a.add_surface(t0)

    t1 = Surface('vstab1')
    vstabloc = back/2
    n = naca(position=(nose+h,vstabloc,0),chord=c)
    t1.add_section(n)
    z = math.sqrt(height**2-c**2)
    n = naca(position=(nose+h+z*math.sin(sweep),vstabloc,z),chord=c)
    t1.add_section(n)
    z =  height
    n = naca(position=(nose+h+z*math.sin(sweep),vstabloc,z),chord=0)
    t1.add_section(n)
    a.add_surface(t1)
    """

    a.set_nspan(5)
    a.set_nchord(10)
    m.nspan = 1
#

    a.draw()
    print('area',a.area)
    print('cs_start',cs_start)
    print('cs_len',cs_len)
    a.set_attitude(alpha=0)
    print('xac',a.xac)
    a.xyzref = (a.xac-0.1*(h+nose),0,0)
    print('xcg',a.xyzref[0])

    S = a.area/144
    rho = imperial_dynamic.rho
    print(rho)
    L = 9/16
    CL_req = L/(0.5*rho*V**2*S)

    #a.set_attitude(alpha=0)
    a.set_attitude(cl = CL_req)
    con = a.control_variables()['elevon']
    a.set(con,'pm 0')
    print('cl',a.CL)
    print('alpha', a.alpha)
    print('cdi',a.CDi)
    print('cl/cdi',a.CL/a.CDi)
    print('def',a.get_output('elevon'))
    print('Cnb',a.Cn_beta)
    cllist.append(a.CL)
    hlist.append(h)
plt.plot(hlist,cllist)
plt.xlabel('h')
plt.ylabel('cl')
#plt.show()