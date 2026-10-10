#!/usr/bin/env python3
"""Offline desktop toolbox. No AI account, API call, or automatic disk writes."""
import tkinter as tk
from tkinter import ttk,messagebox
import pathlib,subprocess,shutil
BASE=pathlib.Path('/opt/gbrunch')
def terminal(command=None):
 args=['xfce4-terminal','--disable-server']
 if command:args+=['--command',command]
 subprocess.Popen(args)
def read(path):
 try:return pathlib.Path(path).read_text().strip()
 except OSError:return 'Unknown'
def workspace():
 p=subprocess.run(['findmnt','-nr','-S','LABEL=GBWORK','-o','TARGET'],text=True,capture_output=True)
 return pathlib.Path(p.stdout.splitlines()[0]) if p.returncode==0 and p.stdout.strip() else None
root=tk.Tk();root.title('GBRUNCH Toolbox — experimental v0.3');root.geometry('1000x720');root.minsize(800,680)
style=ttk.Style();style.theme_use('clam');style.configure('TFrame',background='#f3f5f8');style.configure('TLabel',background='#f3f5f8',font=('DejaVu Sans',11));style.configure('Title.TLabel',font=('DejaVu Sans',24,'bold'));style.configure('TButton',font=('DejaVu Sans',11),padding=12)
f=ttk.Frame(root,padding=28);f.pack(fill='both',expand=True)
ttk.Label(f,text='GBRUNCH Toolbox',style='Title.TLabel').pack(anchor='w')
ttk.Label(f,text='A working desktop for preparation, recovery and collaboration.').pack(anchor='w',pady=(6,16))
model=read('/sys/class/dmi/id/product_name');vendor=read('/sys/class/dmi/id/sys_vendor')
ttk.Label(f,text=vendor+' '+model).pack(anchor='w')
status=tk.StringVar();ttk.Label(f,textvariable=status,wraplength=840).pack(anchor='w',pady=(8,18))
def refresh():
 w=workspace()
 status.set('Persistent workspace: '+str(w)+' | Free: %.1f GiB'%(shutil.disk_usage(w).free/(1<<30)) if w else 'Temporary session. Set up a 64 GB USB workspace to retain settings, downloads and logs.')
 widgets['Set up USB storage'].configure(state='disabled' if w else 'normal')
 root.after(5000,refresh)
def build():
 if not workspace():messagebox.showinfo('Set up storage first','Run “Set up USB storage”, then reboot into the normal desktop entry.');return
 terminal('sudo /usr/local/bin/gbrunch-build-recovery')
def installer():
 if not workspace():messagebox.showinfo('Set up storage first','Persistent storage is required for installation logs.');return
 terminal('sudo /usr/local/bin/gbrunch-install-local')
def trial():
 if not workspace():messagebox.showinfo('Set up storage first','Initialize USB storage, then reboot before preparing the trial.');return
 terminal('sudo /usr/local/bin/gbrunch-prepare-trial')
grid=ttk.Frame(f);grid.pack(fill='x')
buttons=[('Check this laptop','sudo /usr/local/bin/gbrunch-report'),('Collect Android boot logs','sudo /usr/local/bin/gbrunch-report --android-logs'),('Set up USB storage','sudo /usr/local/bin/gbrunch-storage'),('Prepare official recovery',build),('Prepare USB Googlebook trial',trial),('Install Googlebook on internal disk',installer),('Connect to Wi-Fi','nm-connection-editor'),('Open terminal',lambda:terminal())]
widgets={}
for i,(label,action) in enumerate(buttons):
 callback=(lambda a=action:terminal(a)) if isinstance(action,str) else action
 b=ttk.Button(grid,text=label,command=callback);b.grid(row=i//2,column=i%2,sticky='ew',padx=(0,12),pady=6);widgets[label]=b
grid.columnconfigure(0,weight=1);grid.columnconfigure(1,weight=1)
row=ttk.Frame(f);row.pack(fill='x',pady=12)
ttk.Button(row,text='Open browser',command=lambda:subprocess.Popen(['firefox-esr'])).pack(side='left',padx=(0,10))
ttk.Button(row,text='Open reports',command=lambda:subprocess.Popen(['thunar',str(workspace()/'reports' if workspace() else pathlib.Path('/home/live/gbrunch-reports'))])).pack(side='left')
ttk.Label(f,text='After preparing the trial, reboot and select Try Googlebook. Compatibility rollback is not yet implemented.\nAI assistance: use your preferred service in the browser or terminal; no credentials are bundled.',wraplength=840).pack(anchor='w',pady=10)
ttk.Label(f,text='Only the HP Envy external V7 installation is proven on hardware.\nStorage changes require explicit confirmation. Google recovery is downloaded and built locally.',wraplength=840).pack(anchor='w',pady=8)
refresh();root.mainloop()
