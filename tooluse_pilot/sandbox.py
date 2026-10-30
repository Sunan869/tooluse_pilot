"""Untrusted model-generated Python/Shell executes only inside Docker (no host fallback)."""
import json, subprocess, shutil, tempfile, os
from pathlib import Path

class DockerTools:
    def __init__(self,case_dir,image='tooluse-pilot-sandbox:py311-openpyxl',timeout=30):
        if not shutil.which('docker'):
            raise RuntimeError('Docker is required for python_shell; host execution is intentionally forbidden')
        self.case=Path(case_dir).resolve()
        self.image=image
        self.timeout=min(max(int(timeout),1),120)
        self.calls=[]
        self.workspace=tempfile.TemporaryDirectory(prefix='tooluse_agent_')
        self.root=Path(self.workspace.name)
        shutil.copytree(self.case/'input',self.root/'input')
        (self.root/'output').mkdir()
        (self.root/'tmp').mkdir()
        os.chmod(self.root,0o777)
        os.chmod(self.root/'output',0o777)
        os.chmod(self.root/'tmp',0o777)
        os.chmod(self.root/'input',0o755)
        for f in (self.root/'input').iterdir():
            if f.is_file():os.chmod(f,0o644)
        # Never mount case private/oracle, project source, or host credential directories.
        (self.root/'instruction.md').write_text((self.case/'instruction.md').read_text(encoding='utf-8'),encoding='utf-8')
        self._closed=False
    def _exec(self,kind,code):
        if not isinstance(code,str) or not code.strip() or len(code)>20000:raise ValueError('invalid script')
        cmd=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
             '--security-opt','no-new-privileges','--pids-limit','64','--memory','512m','--cpus','1',
             '--user','65534:65534','-v',f'{self.root / "tmp"}:/tmp:rw',
             '-v',f'{self.root}:/work:rw','-w','/work',self.image]
        cmd+=['python','-c',code] if kind=='execute_python' else ['sh','-c',code]
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=self.timeout,check=False)
            result={'exit_code':p.returncode,'stdout':(p.stdout or '')[-6000:],'stderr':(p.stderr or '')[-2000:]}
        except subprocess.TimeoutExpired:
            result={'exit_code':124,'stdout':'','stderr':'Docker command timed out'}
        self.calls.append({'tool':kind,'exit_code':result['exit_code']})
        return result
    def execute_python(self,code):return self._exec('execute_python',code)
    def execute_shell(self,command):return self._exec('execute_shell',command)
    def publish(self):
        src=self.root/'output'/'anomalies.csv'
        if src.is_symlink():raise ValueError('symlink output prohibited')
        if src.is_file() and src.stat().st_size < 2000000:
            target=self.case/'output'/'anomalies.csv';target.parent.mkdir(exist_ok=True)
            shutil.copyfile(src,target)
            return True
        return False
    def close(self):
        if not self._closed:
            self.workspace.cleanup();self._closed=True
