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

	Trim Parameter Reference:
  A lpha
  B eta
  R oll  rate
  P itch rate
  Y aw   rate
  D<n>  <control surface>

	Constraint reference:
       A    alpha       =   0.000    
       B    beta        =   0.000    
       R    pb/2V       =   0.000    
       P    qc/2V       =   0.000    
       Y    rb/2V       =   0.000    
       C    CL          =   0.000    
       S    CY          =   0.000    
       RM   Cl roll mom =   0.000    
       PM   Cm pitchmom =   0.000    
       YM   Cn yaw  mom =   0.000    
       D<n> <control>   =   0.000

	(use lowercase)

	"""
	text = ""
	output = None
	pitch_trim = None

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
		self.constraints = {}

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

	def execute(self,operations=None):
		input = open('chrysopelea.avl','w')
		input.write(str(self))
		input.close()
		cmd = open('chrysopelea.ain','w')
		if operations == None:
			operations = ""
			cons = list(self.constraints)
			for c in cons:
				operations += "\n{}\n{}".format(c,self.constraints[c])
				self.constraints.pop(c)
			operations += '\nx\n'
		cmd.write("""
load chrysopelea.avl
oper{}
quit

""".format(operations))
		cmd.close()
		with open("chrysopelea_subproc_out","w") as subproc_out:
			subprocess.run(avl_path + "<chrysopelea.ain>chrysopelea.aot",shell=True,stderr=subproc_out)

		out = open("chrysopelea.aot")
		out_text = out.read()
		out.close()

		self.output = out_text
		return out_text

	def draw(self):
		operations = """
g
k"""
		self.execute(operations)
		self.output = None

	def pop(self, surname):
		if surname in self.surfaces:
			return self.surfaces.pop(surname)

	def control_variables(self):
		s = str(self)
		cs = s.split('CONTROL')[1:]
		controls = {}
		n = 1
		for c in cs:
			c = re.sub('#.*','',c)
			c = [cc for cc in re.split('\n|\t| ',c) if cc != ''][0]
			if c not in controls:
				controls[c] = 'd{}'.format(n)
				n += 1
		return controls

	def set(self,var,cons):
		self.constraints[var] = cons
		self.output=None

	def set_attitude(self,cl=None,alpha=0):
		"""
		constrain alpha either directly or with cl.
		Included primarily for backwards compatability.
		"""
		if cl != None:
			self.set('a','c {}'.format(cl))
		elif alpha != None:
			self.set('a','a {}'.format(alpha))
		if self.pitch_trim != None:
			d = self.control_variables()[self.pitch_trim]
			self.set(d,'pm 0')

	def get_output(self,var):
		if not self.output:
			self.execute()
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
		self.add_section(sec)

	def add_naca(self,xyz,chord,desig="0014",nspan=10):
		sec = naca(position=xyz,chord=chord,desig=desig,nspan=nspan)
		self.add_section(sec)

	def add_section(self, sec):
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
		"""
		return the planform area
		"""
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
	def integrated_cd0(self):
		"""
		return the drag that the surface will generate
		per unit dynamic pressure, in other words, the
		drag coefficient integrated over the area
		"""
		c = 0
		for n in range(1,len(self.sections)):
			c0 = self.sections[n].cd0
			c1 = self.sections[n-1].cd0
			chordwise = 0.5*(self.sections[n].chord*c0 + self.sections[n-1].chord*c1)
			spanwise = np.array(self.sections[n].position) - np.array(self.sections[n-1].position)
			c += math.sqrt(spanwise[0]**2 + spanwise[1]**2 + spanwise[2]**2) * chordwise
		if self.yduplicate != None:
			c *= 2
		return c

	def from_text(text):
		text = re.sub('\n+','\n',text)
		sects = text.split('SECTION')
		head = sects.pop(0)
		name = head.split('\n')[0]
		s = Surface(name)
		parts = head.split('TRANSLATE')
		if len(parts) > 1:
			entries = re.split('\n|\t',parts[1])
			entries = [e for e in entries if e != '']
			delta = (float(entries[0]),float(entries[1]),float(entries[2]))
		else:
			delta = (0,0,0)
		for sect in sects:
			try:
				section = naca.from_text(sect)
			except AssertionError:
				section = xfoil.from_text(sect)
			section.translate(delta)
			s.add_section(section)
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
		self.controls = []
		self.file = file
		self.position=position
		self.chord = chord
		self.sspace = sspace
		self.nspan = nspan

	def from_text(text):
		entries = re.split('\n|\t',text)
		entries = [e for e in entries if e != '']
		coord = (float(entries[0]),float(entries[1]),float(entries[2]))
		chord = float(entries[3])
		afile = re.split('AFILE\n*\t*',text)
		afile = afile[1]
		afile = re.split('\n|\t',afile)[0]
		sec = xfoil(file=afile,position=coord,chord=chord)
		sec.add_control_from_text(text)
		return sec

	def add_control(self,control):
		control.parent=self
		self.controls.append(control)

	def add_control_from_text(self,text):
		con = text.split('CONTROL')
		if len(con) > 1:
			con = Control.from_text(con[1])
			self.add_control(con)

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
		with open("chrysopelea_subproc_out","w") as subproc_out:
			subprocess.run("xfoil<chrysopelea.xin>chrysopelea.xot",shell=True,stderr=subproc_out)

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
		s = """
#----------------------------------------------
SECTION
#Xle	 	Yle	 	Zle	 	Chord	 	Ainc	 	Nspan	 	Sspace
{} 	 	{} 	 	{} 	 	{} 	 	0 	 	{} 	 	{} 
AFILE
{}""".format(self.position[0],self.position[1],self.position[2],self.chord,self.nspan,self.sspace,self.file)
		for con in self.controls:
			s += str(con)
		return s

	def translate(self,xyz):
		self.position = (self.position[0] + xyz[0], self.position[1] + xyz[1],self.position[2] + xyz[2])

class naca(xfoil):

	def __init__(self, desig="0014",position=[0,0,0],chord=1,sspace=1,nspan=10):
		self.controls = []
		self.file = desig
		self.position=position
		self.chord = chord
		self.sspace = sspace
		self.nspan = nspan

	def from_text(text):
		entries = re.split('\n|\t',text)
		entries = [e for e in entries if e != '']
		coord = (float(entries[0]),float(entries[1]),float(entries[2]))
		chord = float(entries[3])
		desig = re.split('NACA\n*\t*',text)
		assert len(desig) > 1
		desig = re.split('\n|\t| ',desig[1])[0]
		n = naca(desig=desig,position=coord,chord=chord)
		n.add_control_from_text(text)
		return n

	@property
	def load_cmd(self):
		return "naca {}".format(self.file)

	def __str__(self):
		s = """
#----------------------------------------------
SECTION
#Xle	 	Yle	 	Zle	 	Chord	 	Ainc	 	Nspan	 	Sspace
{} 	 	{} 	 	{} 	 	{} 	 	0 	 	{} 	 	{} 
NACA
{}""".format(self.position[0],self.position[1],self.position[2],self.chord,self.nspan,self.sspace,self.file)
		for con in self.controls:
			s += str(con)
		return s


#################################### Control Surface Class ####################################

class Control:

	def __init__(self,name,gain=1,xhinge=0.5,xyzhvec=(0,0,0),signdup=1):
		self.name=name
		self.gain=gain
		self.xhinge=0.5
		self.xyzhvec=xyzhvec
		self.signdup=signdup

	def from_text(text):
		text = re.sub('#.*','',text)
		entries = [e for e in re.split('\n|\t| ',text) if e != '']
		return Control(entries[0],gain=entries[1],xhinge=entries[2],xyzhvec=(entries[3],entries[4],entries[5]),signdup=entries[6])

	def __str__(self):
		return """
CONTROL
#NAME 		GAIN		XHINGE		XHVEC		YHVEC		ZHVEC		SIGNDUP
{} 		{} 		{} 		{} 		{} 		{} 		{} """.format(self.name,self.gain,self.xhinge,self.xyzhvec[0],self.xyzhvec[1],self.xyzhvec[2],self.signdup) # Note whitespace after parameter values

