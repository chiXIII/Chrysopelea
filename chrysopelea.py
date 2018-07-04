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
		text = re.split("{} = *".format(var),text)[1].split(' ')[0]
		return float(text)

	@property
	def cl(self):
		return self.get_output('CLtot')
	@property
	def cdi(self):
		return self.get_output('CDind')
	@property
	def alpha(self):
		return self.get_output('Alpha')

	@property
	def e(self):
		return self.get_output('e')

	def scale(self, factor):
		for s in self.surfaces.keys():
			self.surfaces[s].scale(factor)

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
	nchord = 10
	cspace = 1
	nspan = 20
	sspace = 1
	parent = None

	def __init__(self,name):
		self.sections = Surface.sections.copy()
		self.name = name

	def add_section(self,xyz, chord, afile = 'sd7062.dat'):
		sec = xfoil(file=afile,position=xyz,chord=chord)
		sec.parent = self
		self.sections.append(sec)

	def __repr__(self):
		return 'AVL surface with name "{}"'.format(self.name)
	def __str__(self):
		# important note: spaces after numbers in Nchord... !!
		text = """
#==============================================
SURFACE
{}""".format(self.name)
		text += """
#Nchord		Cspace		Nspan		Sspace
{} 		{} 		{} 		{}
YDUPLICATE
{}""".format(self.nchord,self.cspace,self.nspan,self.sspace,self.yduplicate)

		for s in self.sections:
			text += str(s)
		return text

	@property
	def area(self):
		a = 0
		for n in range(1,len(self.sections)):
			a += 0.5*abs(self.sections[n].position[1] - self.sections[n-1].position[1])\
*(self.sections[n].chord + self.sections[n-1].chord)
		if self.yduplicate != "":
			a *= 2
		return a
	@property
	def span(self):
		a = 0
		b = max([abs(s.position[1]) for s in self.sections])
		if self.yduplicate != "":
			b *= 2
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
				s.add_section(coord,chord,afile=afile)
			else:
				s.add_section(coord,chord)
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

	def __init__(self, file = "sd7062",position=[0,0,0],chord=1):
		self.file = file
		self.position=position
		self.chord = chord

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
			print(self.output)
			xfoil.computed[self.file] = self.output.iloc[0]['CD']
			return self.cd0

	@property
	def re(self):
		return self.parent.parent.speed*self.parent.parent.rho*self.chord/self.parent.parent.mu

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
{}	 	{}	 	{}	 	{}	 	0	 	0	 	0
AFILE
{}""".format(self.position[0],self.position[1],self.position[2],self.chord,self.file)

############ motor class #####################

class motor(object):
	static = 0
	max = 1
	static_thrust = 1
	thrust_at_max = 1

	def thrust(self,v):
		return self.static_thrust + (self.thrust_at_max-self.static_thrust)*(v-self.static)/self.max

############### flight dynamics class ######################

class dynamic(fast_avl):
	# aircraft characteristics
	weight = 1
	extra_drag = 0		# D/q
	motor = motor()

	# flight conditions
	speed = 1
	rho = 1.225
	mu = 18.27 * 10**-6

	# computational parameters
	speed_limits = (25,100)
	phi_limits = -math.pi/2,math.pi/2
	side_points = 10
	@property
	def cd0(self):
		c = 0
		for k in self.surfaces.keys():
			c += self.surfaces[k].cd0*self.surfaces[k].area
		c += self.extra_drag
		c /= self.area
		return c

	def q(self,v):
		return 0.5*self.rho*v**2

	def drag(self,v,phi):
		"""
		v is the speed,
		phi is the angle of elevation of the climb trajectory
		"""
		q = self.q(v)
		cl = self.weight*math.cos(phi)/(q*self.area)
		self.set_attitude(cl=cl)
		return q*self.area*(self.cd0 + self.cdi)

	def climb_envelope(self,plot=False):
		t0 = time.time()
		succeed = ([],[])
		fail = ([],[])
		for v in np.linspace(self.speed_limits[0],self.speed_limits[1],self.side_points):
			for phi in np.linspace(self.phi_limits[0],self.phi_limits[1],self.side_points):
				drag = self.drag(v,phi)
				thrust = self.motor.thrust(v)
				if thrust >= drag + self.weight*math.sin(phi):
					succeed[0].append(v)
					succeed[1].append(phi)
				else:
					fail[0].append(v)
					fail[1].append(phi)
		print('This call took')
		print(time.time()-t0)
		print('seconds')
		if plot:
			plt.scatter(succeed[0],succeed[1],c='g')
			plt.scatter(fail[0],fail[1],c='r')
			plt.xlabel('v')
			plt.ylabel('phi')
			plt.show()

		return succeed,fail

	@property
	def max_climb_rate(self):
		succeed,fail = self.climb_envelope(plot=True)
		climb_rates = [succeed[0][n]*math.sin(succeed[1][n]) for n in range(len(succeed[0]))]
		return max(climb_rates)

class imperial_dynamic(dynamic):
	rho = 0.0023769
	mu = 0.3766*10**-6
