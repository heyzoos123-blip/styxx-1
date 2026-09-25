# (a)4: a forked child's thread is a copy of the forking stack, not a bootstrap frame
import os, sys
def section_body():
    pid = os.fork()
    if pid == 0:
        names = []; f = sys._getframe()
        while f is not None: names.append(f.f_code.co_name); f = f.f_back
        os.write(1, f"child chain: {names}\n".encode()); os._exit(0)
    os.waitpid(pid, 0)
def _run(fn): return fn()      # stands for the anchor frame
_run(section_body)
print(sys.version.split()[0])
