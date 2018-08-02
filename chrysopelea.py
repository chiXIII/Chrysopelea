import math
import subprocess
from collections import OrderedDict
import re
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import time

########## AVL Class ##################

avl_path = "/home/micaiah/Avl/bin/avl"

class avl(object):
	"""
	class for performing AVL simulations
	"""
	text = ""
	output = None

	def __init__(self,file=None):
		self.surfaces = {}
		if file != None:
			file_obj = open(file)
			text = file_obj.read()
			file_obj.close()

			text = re.sub('#.*','',text)
			stexts = re.split('SURFACE\n',text)[1:]
			for stext in stexts:
				self.add_surface(Surface.from_text(stext))

	def __repr__(self):
		return "AVL interface object with surfaces {}".format(self.surfaces)

	def __str__(self):
		text = """
Advanced
#MACH
0
#IYsym		IZsym		Zsym		Vehicle Symmetry
0 	0 	0
#Sref		Cref		Bref		Reference Area and Lengths
{}		{}		{}
#Xref	 	Yref	 	Zref	 	Center of Gravity Location
0 		0	 	0
""".format(self.area,self.mean_chord,self.span)
		for s in list(self.surfaces):
			text += str(self.surfaces[s])
		return text

	@property
	def area(self,ref_surf_name='Wing'):
		if ref_surf_name in self.surfaces.keys():
			return self.surfaces[ref_surf_name].area
		else:
			return 1
	@property
	def mean_chord(self,ref_surf_name='Wing'):
		if ref_surf_name in self.surfaces.keys():
			return self.surfaces[ref_surf_name].mean_chord
		else:
			return 1
	@property
	def span(self,ref_surf_name='Wing'):
		if ref_surf_name in self.surfaces.keys():
			return self.surfaces[ref_surf_name].span
		else:
			return 1

	@property
	def ar(self,ref_surf_name='Wing'):
		if ref_surf_name in self.surfaces.keys():
			return self.surfaces[ref_surf_name].ar
		else:
			return 1

	def add_surface(self,surf):
		if type(surf) == str:
			surf = Surface(surf)
		surf.parent = self
		self.surfaces[surf.name] = surf

	def execute(self,operations):
		print('AVL Executed!')
		input = open('chrysopelea.avl','w')
		input.write(str(self))
		input.close()
		cmd = open('chrysopelea.ain','w')
		cmd.write("""
load chrysopelea.avl
oper{}
quit

""".format(operations))
		cmd.close()
		subprocess.run(avl_path + "<chrysopelea.ain>chrysopelea.aot",shell=True)

		out = open("chrysopelea.aot")
		out_text = out.read()
		out.close()

		self.output = out_text
		return out_text

	def draw(self):
		operations = """
g
k"""
		return self.execute(operations)

	def pop(self, surname):
		if surname in self.surfaces:
			return self.surfaces.pop(surname)

	def set_attitude(self,cl=None,alpha=0):
		if cl != None:
			cmd = 'c {}'.format(cl)
		elif alpha != None:
			cmd = 'a {}'.format(alpha)
		ops = """
a
{}
x""".format(cmd)
		self.execute(ops)

	def get_output(self,var):
		if not self.output:
			self.set_attitude()
		text = self.output.split('Vortex Lattice Output -- Total Forces')[1]
		text = re.split("{} *= *".format(var),text)[1].split(' ')[0]
		return float(text)

	@property
	def cl(self):
		return self.get_output('CLff')
	@property
	def cdi(self):
		return self.get_output('CDff')
	@property
	def alpha(self):
		return self.get_output('Alpha')

	@property
	def e(self):
		return self.get_output('e')

	def scale(self, factor):
		for s in self.surfaces.keys():
			self.surfaces[s].scale(factor)

	def set_nchord(self,nc):
		for k in self.surfaces.keys():
			self.surfaces[k].nchord = nc
	def set_nspan(self,ns):
		for k in self.surfaces.keys():
			self.surfaces[k].nspan = ns

class fast_avl(avl):
	memory_df = pd.DataFrame({'Alpha':[],'CLtot':[],'CDind':[],'e':[]})
	mesh_size = 0.5
	output_df = None

	def set_attitude(self,cl=None,alpha=0):
		if self.memory_df.empty:
			avl.set_attitude(self,cl=cl,alpha=alpha)
			self.to_df()
		if cl != None:
			paramname = 'CLtot'
			paramvalue = cl
		elif alpha != None:
			paramname = 'Alpha'
			paramvalue = alpha
		while True:
			self.memory_df.sort_values(paramname,inplace=True)
			greater = self.memory_df.loc[self.memory_df[paramname] >= paramvalue]
			less = self.memory_df.loc[self.memory_df[paramname] < paramvalue]
			if (len(greater) > 0) and (len(less) > 0):
				greater, less = greater.iloc[0], less.iloc[-1]
				output_ser = less + (greater-less)*(paramvalue-less[paramname])/(greater[paramname]-less[paramname])
				self.output_df = pd.DataFrame(output_ser).transpose()
				return self.output_df
			elif len(greater) == 0:
				alpha = less.iloc[-1]['Alpha'] + self.mesh_size
			else:
				alpha = greater.iloc[0]['Alpha'] - self.mesh_size
			avl.set_attitude(self,alpha=alpha)
			self.to_df()

	def plot_mem(self):
		plt.plot(self.memory_df['CDind'],self.memory_df['CLtot'])
		plt.show()

	def reset(self):
		self.memory_df = pd.DataFrame({'Alpha':[],'CLtot':[],'CDind':[],'e':[]})

	def to_df(self):
		new_df = pd.DataFrame({'Alpha':[avl.get_output(self,'Alpha')],'CLtot':[avl.get_output(self,'CLtot')],\
'CDind':[avl.get_output(self,'CDind')],'e':[avl.get_output(self,'e')]})
		self.memory_df = pd.concat([self.memory_df, new_df])

	def get_output(self,var):
		if self.output_df is None:
			self.set_attitude
		return self.output_df[var][0]

############### Surface Class #######################

class Surface(object):
	sections = []
	yduplicate = 0
	nchord = 5
	cspace = 1
	parent = None

	def __init__(self,name):
		self.sections = Surface.sections.copy()
		self.name = name

	def add_afile(self,xyz, chord, afile='sd7062.dat',nspan=10):
		sec = xfoil(file=afile,position=xyz,chord=chord,nspan=nspan)
		sec.parent = self
		self.sections.append(sec)

	def add_naca(self,xyz,chord,desig="0014",nspan=10):
		sec = naca(position=xyz,chord=chord,desig=desig,nspan=nspan)
		sec.parent=self
		self.sections.append(sec)

	def __repr__(self):
		return 'AVL surface with name "{}"'.format(self.name)
	def __str__(self):
		# important note: spaces after numbers in Nchord... !!
		if self.yduplicate == None:
			ydup = ""
		else:
			ydup = "YDUPLICATE\n" + str(self.yduplicate)
		text = """
#==============================================
SURFACE
{}""".format(self.name)
		text += """
#Nchord		Cspace 
{} 		{} 
{}""".format(self.nchord,self.cspace,ydup)

		for s in self.sections:
			text += str(s)
		return text

	@property
	def area(self):
		a = 0
		for n in range(1,len(self.sections)):
			a += 0.5*abs(self.sections[n].position[1] - self.sections[n-1].position[1])*(self.sections[n].chord + self.sections[n-1].chord)
		if self.yduplicate != None:
			a *= 2
		return a
	@property
	def span(self):
		a = 0
		pos = [s.position[1] for s in self.sections]
		if self.yduplicate == None:
			b = abs(max(pos) - min(pos))
		else:
			b = 2*max([abs(p-self.yduplicate) for p in pos])
		return b

	@property
	def mean_chord(self):
		return self.area/self.span
	@property
	def ar(self):
		return self.span/self.mean_chord
	@property
	def cd0(self):
		c = 0
		for n in range(1,len(self.sections)):
			c0 = self.sections[n].cd0
			c1 = self.sections[n-1].cd0
			chordwise = 0.5*(self.sections[n].chord*c0 + self.sections[n-1].chord*c1)
			c += abs(self.sections[n].position[1] - self.sections[n-1].position[1]) * chordwise
		if self.yduplicate != "":
			c *= 2
		return c/self.area

	def from_text(text):
		text = re.sub('\n+','\n',text)
		sects = text.split('SECTION')
		name = sects.pop(0).split('\n')[0]
		s = Surface(name)
		for sect in sects:
			entries = re.split('\n|\t',sect)
			entries = [e for e in entries if e != '']
			coord = (float(entries[0]),float(entries[1]),float(entries[2]))
			chord = float(entries[3])
			afile = re.split('AFILE\n*\t*',sect)
			if len(afile) > 1:
				afile = afile[1]
				afile = re.split('\n|\t',afile)[0]
				s.add_afile(coord,chord,afile=afile)
			else:
				s.add_naca(coord,chord)
		return s

	def scale(self, factor):
		for s in self.sections:
			s.position = [x*factor for x in s.position]
			s.chord *= factor


############### XFOIL class #############################

class xfoil(object):
	output = None
	computed = {}
	parent = None
	re = 450000

	def __init__(self, file = "sd7062",position=[0,0,0],chord=1,sspace=1,nspan=10):
		self.file = file
		self.position=position
		self.chord = chord
		self.sspace = sspace
		self.nspan = nspan

	@property
	def load_cmd(self):
		return "load {}".format(self.file)

	@property
	def cd0(self):
		if self.file in xfoil.computed:
			return xfoil.computed[self.file]
		else:
			oper = "alfa 0"
			self.execute(oper)
			xfoil.computed[self.file] = self.output.iloc[0]['CD']
			return self.cd0

	"""
	@property
	def re(self):
		return round(self.parent.parent.speed*self.parent.parent.rho*self.chord/self.parent.parent.mu,-3)
	"""

	def execute(self,oper):
		input = open("chrysopelea.xin",'w')
		cmd = """
xfoil
{}
oper
visc {}
pacc
chrysopelea_xfoil.dat

{}
quit
""".format(self.load_cmd,self.re,oper)
		input.write(cmd)
		input.close()
		subprocess.run("xfoil<chrysopelea.xin>chrysopelea.xot",shell=True)

		file = open("chrysopelea_xfoil.dat")
		text = file.read()
		file.close()
		csv = io.StringIO(re.sub(' +',',',text))
		output = pd.read_csv(csv,skiprows = list(range(10)) + [11])
		output.dropna(axis=1,inplace=True)
		subprocess.run("rm chrysopelea.xin chrysopelea.xot chrysopelea_xfoil.dat",shell=True)
		self.output = output
		return output

	def __str__(self):
		return """
#----------------------------------------------
SECTION
#Xle	 	Yle	 	Zle	 	Chord	 	Ainc	 	Nspan	 	Sspace
{} 	 	{} 	 	{} 	 	{} 	 	0 	 	{} 	 	{} 
AFILE
{}""".format(self.position[0],self.position[1],self.position[2],self.chord,self.nspan,self.sspace,self.file)

class naca(xfoil):

	def __init__(self, desig="0014",position=[0,0,0],chord=1,sspace=1,nspan=10):
		self.file = desig
		self.position=position
		self.chord = chord
		self.sspace = sspace
		self.nspan = nspan

	@property
	def load_cmd(self):
		return "naca {}".format(self.file)

	def __str__(self):
		return """
#----------------------------------------------
SECTION
#Xle	 	Yle	 	Zle	 	Chord	 	Ainc	 	Nspan	 	Sspace
{} 	 	{} 	 	{} 	 	{} 	 	0 	 	{} 	 	{} 
NACA
{}""".format(self.position[0],self.position[1],self.position[2],self.chord,self.nspan,self.sspace,self.file)


############ motor class #####################

class motor(object):
	static = 0
	max = 1
	static_thrust = 1
	thrust_at_max = 1

	def thrust(self,v):
		return self.static_thrust + (self.thrust_at_max-self.static_thrust)*(v-self.static)/self.max

############### flight dynamics class ######################

class dynamic(avl):
	# aircraft characteristics
	weight = 1
	extra_drag = 0		# D/q
	motor = motor()
	alpha_max = 10
	rolling_mu = 0

	# freestream conditions
	speed = 1
	rho = 1.225
	mu = 18.27 * 10**-6
	g = 9.80665

	@property
	def cd0(self):
		c = 0
		for k in self.surfaces.keys():
			c += self.surfaces[k].cd0*self.surfaces[k].area
		c /= self.area
		c += self.extra_drag
		return c

	@property
	def thrust(self):
		return self.motor.thrust(self.speed)

	@property
	def climb_cl(self):
		a = 0.25* self.rho**2 * self.speed**4 * self.area**2/(math.pi*self.ar*self.e)**2
		b = 0.25*self.rho**2 * self.speed**4 *self.area**2 *(1 + 2*self.cd0/(math.pi*self.ar*self.e))
		b -= self.thrust*self.rho* self.speed**2 * self.area / (math.pi*self.ar*self.e)
		c = self.thrust**2 + 0.25*self.rho**2 * self.speed**4 * self.area**2 * self.cd0**2
		c -=  self.weight**2 + self.thrust*self.rho*self.speed**2 * self.area*self.cd0
		l = math.sqrt( (-b + math.sqrt(b**2 - 4*a*c)) / (2*a) ) # ignore the extraneous solution where cl**2 < 0
		return l

	@property
	def slope(self):
		return (self.thrust - 0.5*self.rho*self.speed**2 *self.area * (self.cdi + self.cd0))/self.weight
	@property
	def roc(self):
		return self.slope*self.speed
		

	def climb_plot(self):
		v = list(range(30,150))
		vs,cl,slope,rate = [],[],[],[]
		for s in v:
			try:
				print(self.e)
				self.speed = s
				l = self.climb_cl
				self.set_attitude(cl=l)
				l = self.climb_cl
				print("cdi form",l**2/(math.pi*self.ar*self.e))
				self.set_attitude(cl=l)
				sl = self.slope
				print("cdi",self.cdi)
				print("cd0",self.cd0)
				slope.append(sl)
				rate.append(sl*self.speed)
				cl.append(l)
				vs.append(s)
			except:
				pass
		print(cl)
		print(vs)
		plt.plot(vs,cl,label="cl")
		plt.plot(vs,slope,label="slope")
		plt.plot(vs,rate,label="rate")
		plt.legend()

	def optimize_roc(self,plot=False):
		v0 = 0
		dv = 1
		vs,rates=[],[]
		self.speed = 90
		self.set_attitude(cl=self.climb_cl)
		while self.speed - v0 > 1:
			self.set_attitude(cl=self.climb_cl)
			r0 = self.roc
			v0 = self.speed
			self.speed += dv
			self.set_attitude(cl=self.climb_cl)
			r1 = self.roc
			v1 = self.speed
			self.speed += dv
			self.set_attitude(cl=self.climb_cl)
			r2 = self.roc
			v2 = self.speed
			coefs = np.polyfit([v0,v1,v2],[r0,r1,r2],2)
			if plot:
				vs.append(v0)
				rates.append(r0)
				testv = np.linspace(0,100,100)
				testr = testv**2*coefs[0] + testv*coefs[1] + coefs[2]
				plt.plot(testv,testr)
			self.speed = -0.5*coefs[1]/coefs[0]
		if plot:
			self.set_attitude(cl=self.climb_cl)
			plt.scatter(vs+[self.speed],rates+[self.roc])

	@property
	def v_stall(self):
		self.set_attitude(alpha=self.alpha_max)
		return math.sqrt(2*self.weight/(self.rho*self.cl*self.area))

	def takeoff_distance(self,safety_factor=1.2,alpha=0,motor_decriment=0,lame=False):
		vto = self.v_stall*safety_factor
		self.set_attitude(alpha=alpha)
		if lame:
			return 1/(self.g*(self.motor.static_thrust/self.weight+self.rolling_mu - 0.5*self.rho*vto**2/2/self.weight*(self.cd0 + self.cdi - self.rolling_mu*self.cl)))*vto**2/2
		a = self.g*(self.motor.static_thrust/self.weight-self.rolling_mu)
		b = self.g/self.weight*(0.5*self.rho*self.area*(self.cd0 + self.cdi - self.rolling_mu*self.cl) + motor_decriment)
		return 0.5/b*math.log(a/(a - b*vto**2))

class imperial_dynamic(dynamic):
	rho = 0.0023769
	mu = 0.3766*10**-6
	g = 32.17405

############ lifting line class ##########

class LiftingLine(object):

	def __init__(self,n=100, chord='elipse',scale=0.1,x=0,y = 'cos',z=0):

		if np.array_equal(y,'uniform'):
			selfy = np.linspace(0.5/n,1-0.5/n,n)
			self.elip = 2*np.sqrt(0.25-(selfy-0.5)**2)
		elif np.array_equal(y,'cos'):
			theta = np.linspace(0,math.pi,n+1)
			yvec = -np.cos(theta)/2
			self.elip = np.sin(np.linspace(0,math.pi,n))
			selfy = 0.5*(yvec[1:] + yvec[:-1]) + 0.5
		else:
			selfy = y
			self.elip = 2*np.sqrt(0.25-(selfy-0.5)**2)
			n = len(y)

		selfx = np.zeros(n) + x
		selfz = np.zeros(n) + z
		self.r = np.array([selfx,selfy,selfz])

		self.kappa = np.zeros(n)
		self.upwash= np.zeros(n)

		if np.array_equal(chord,'uniform'):
			self.chord = np.zeros(n) + scale
		elif np.array_equal(chord,'elipse'):
			self.chord = scale*np.sqrt(1-(2*self.r[1]-1)**2)
		else:
			self.chord = chord
		self.set_mesh()

	def set_mesh(self):
		r0,r1 = 2*self.r[:,-1] - self.r[:,-2], 2*self.r[:,0] - self.r[:,1]
		self.r_minus = (np.concatenate([np.array([r1]).transpose(), self.r[:,:-1]],1) + self.r)/2
		self.r_plus = (np.concatenate([self.r[:,1:], np.array([r0]).transpose()],1) + self.r)/2
		diff = self.r_plus - self.r_minus
		self.space = diff[1]
		self.arcspace = np.sqrt(diff[0]**2 + diff[1]**2 + diff[2]**2)
		self.arclen = self.arcspace.sum()

	@property
	def ar(self):
		return 1/sum(self.chord*self.space)
	@property
	def area(self):
		return sum(self.chord*self.space)
	@property
	def cl(self):
		return -2*sum(self.kappa*self.space)/sum(self.chord*self.space)
	@property
	def cdi(self):
		return 2*sum(self.kappa*self.upwash*self.space)/sum(self.chord*self.space)
	@property
	def L(self):
		return -sum(self.kappa*self.space)
	@property
	def D(self):
		return sum(self.kappa*self.upwash*self.space)
	@property
	def e(self):
		return (self.cl**2)/(math.pi*self.ar*self.cdi)
	@property
	def lengthwise_e(self):
		return (2*self.L**2)/(math.pi*self.D*self.arclen**2)

	def vcoef(self,x,y,z):
		delta_y_plus,delta_z_plus = self.r_plus[1,:]-y,self.r_plus[2,:]-z
		delta_y_minus,delta_z_minus = self.r_minus[1,:]-y,self.r_minus[2,:]-z
		lat_dist_plus = np.sqrt(delta_y_plus**2 + delta_z_plus**2)
		lat_dist_minus = np.sqrt(delta_y_minus**2 + delta_z_minus**2)
		sweep_effect_plus = 2/math.pi*np.arctan( (x-self.r_plus[0,:])/lat_dist_plus) + 1
		sweep_effect_minus = 2/math.pi*np.arctan( (x-self.r_minus[0,:])/lat_dist_minus) + 1
		return (sweep_effect_plus*delta_y_plus/lat_dist_plus**2 - sweep_effect_minus*delta_y_minus/lat_dist_minus**2)/(4*math.pi)

	def solve(self,alpha):
		b = np.zeros(len(self.r[0]))+alpha
		x,y,z = np.array([self.r[0]]).transpose(),np.array([self.r[1]]).transpose(),np.array([self.r[2]]).transpose()
		vcoef = self.vcoef(x,y,z)
		eqns = -vcoef - np.identity(len(y))/(math.pi*self.chord)
		self.kappa = np.linalg.solve(eqns,b).flatten()
		self.upwash = np.dot( vcoef ,self.kappa)
	def solve_no_wash(self,alpha):
		b = np.zeros(len(self.r[0]))+alpha
		eqns = -np.identity(len(self.r[0]))/(math.pi*self.chord)
		self.kappa = np.linalg.solve(eqns,b).flatten()
		self.upwash *= 0

	def plot(self):
		n = len(self.space)
		plt.plot(self.r[1],self.kappa)
		elip = -self.elip*max(abs(self.kappa))
		plt.plot(self.r[1],elip)
		plt.plot(self.r[1],self.upwash)

	def plot_circ(self):
		circ = self.kappa/self.kappa.mean()
		plt.plot(self.y,circ)

	def plot_wash(self):
		wash = self.upwash/self.upwash.min()
		plt.plot(self.y,wash)

	def plot_planform(self):
		plt.axis('equal')
		plt.scatter(self.r[0],self.r[1],color='k')
		plt.scatter(self.r_plus[0],self.r_plus[1],color='r')
		plt.scatter(self.r_minus[0],self.r_minus[1],color='r')
		plt.plot(self.r[0]+0.75*self.chord,self.r[1],color='b')
		plt.plot(self.r[0]-0.25*self.chord,self.r[1],color='b')

	def print(self):
		n = len(self.space)
		print("cl",self.cl,"cdi",self.cdi)
		print("ar",self.ar)
		print("e",self.e)
		print()
		wash = self.upwash[int(n/2)]
		print("wash",wash,'alpha',2*math.pi/180,"cdi/cl",self.cdi/self.cl)
		alpha500 = 2*math.pi/180 + wash
		print("correct",math.pi*self.chord[50]*alpha500, "actual", self.kappa[int(n/2)] )

