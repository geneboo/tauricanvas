from pathlib import Path
from dataclasses import dataclass
import subprocess,time
@dataclass
class Result: args:list[str]; cwd:str; code:int; out:str; err:str; seconds:float
@property
def ok(self): return self.code==0
def run(args:list[str],cwd:Path,timeout=600):
 start=time.monotonic()
 try:
  p=subprocess.run(args,cwd=cwd,text=True,encoding='utf-8',capture_output=True,timeout=timeout,check=False)
  return Result(args,str(cwd),p.returncode,p.stdout,p.stderr,time.monotonic()-start)
 except FileNotFoundError as e: return Result(args,str(cwd),127,'',str(e),time.monotonic()-start)
