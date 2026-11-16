"""Optional pinned Linux-container custom adapters. No host mounts or credentials."""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from uuid import uuid4


PYTHON = '''import json,sys,pathlib,importlib.util
payload=json.load(sys.stdin)
root=pathlib.Path('/tmp/strategy'); root.mkdir()
for name,content in payload['files'].items():
 p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content)
sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('paper_strategy',root/'paper_adapter.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
result=module.decide(payload['context'])
print(json.dumps(result,allow_nan=False))
'''
JAVASCRIPT = '''import fs from 'node:fs';import path from 'node:path';
const input=JSON.parse(fs.readFileSync(0,'utf8'));const root='/tmp/strategy';fs.mkdirSync(root);
for(const [name,text] of Object.entries(input.files)){const p=path.join(root,name);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,text);}
const module=await import('file:///tmp/strategy/paper_adapter.mjs');
console.log(JSON.stringify(await module.decide(input.context)));
'''


def image_for(adapter):
    image = os.environ.get('Q_PAPER_PYTHON_IMAGE' if adapter == 'custom_python' else 'Q_PAPER_JAVASCRIPT_IMAGE', '')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ValueError('Custom execution requires a verified isolated worker and a pinned local image digest')
    docker = shutil.which('docker')
    if not docker: raise ValueError('Custom isolated worker unavailable: Docker is not installed')
    # Environment only for the Docker client, never forwarded into the container.
    env = {k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','TEMP','TMP','USERPROFILE','HOME')}
    try:
        result = subprocess.run([docker, 'info', '--format', '{{.OSType}}'], capture_output=True, text=True, timeout=10, env=env)
        if result.returncode or result.stdout.strip() != 'linux': raise ValueError('A Linux-container isolation runtime is required')
        result = subprocess.run([docker, 'image', 'inspect', image, '--format', '{{.Id}}'], capture_output=True, text=True, timeout=10, env=env)
        if result.returncode or result.stdout.strip() != image: raise ValueError('Pinned custom-worker image is not available locally')
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Custom isolation verification failed') from None
    return docker, image, env


def validate_files(spec):
    files = spec.parameters.get('snapshot', {}).get('files', {})
    entry = 'paper_adapter.py' if spec.adapter == 'custom_python' else 'paper_adapter.mjs'
    if not isinstance(files, dict) or entry not in files or len(files) > 300:
        raise ValueError(f'Frozen custom version must contain {entry} with decide(context)')
    if sum(len(v) for v in files.values() if isinstance(v, str)) > 2_000_000:
        raise ValueError('Custom source bundle exceeds 2 MB; exclude datasets and generated reports')
    for name, content in files.items():
        if not isinstance(content, str) or not re.fullmatch(r'[A-Za-z0-9_. /-]+', name) or any(p in ('..', '') for p in name.split('/')) or name.startswith('/') or '\\' in name:
            raise ValueError('Invalid custom source path')
    return files


def run(spec, context, cancelled=lambda: False):
    files = validate_files(spec)
    docker, image, env = image_for(spec.adapter)
    if spec.parameters.get('worker_image') != image:
        raise ValueError('Custom worker image differs from frozen deployment')
    name = 'q-paper-' + uuid4().hex
    runtime = ['python', '-I', '-c', PYTHON] if spec.adapter == 'custom_python' else ['node', '--input-type=module', '-e', JAVASCRIPT]
    command = [docker, 'run', '--rm', '--pull=never', '--name', name, '--network=none', '--read-only',
               '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=64', '--memory=256m',
               '--memory-swap=256m', '--cpus=1', '--user=65534:65534',
               '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m', '--entrypoint', runtime[0], '-i', image, *runtime[1:]]
    output = bytearray()
    overflow = threading.Event()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    def read():
        while True:
            chunk = process.stdout.read(4096)
            if not chunk: break
            if len(output) + len(chunk) > 1_000_000:
                overflow.set(); process.kill(); break
            output.extend(chunk)
    reader = threading.Thread(target=read, daemon=True); reader.start()
    def write():
        try:
            process.stdin.write(json.dumps({'files':files,'context':context}, allow_nan=False).encode())
            process.stdin.close()
        except (OSError, ValueError): pass
    writer=threading.Thread(target=write,daemon=True); writer.start()
    try:
        deadline = time.monotonic() + 20
        while process.poll() is None:
            if cancelled(): raise ValueError('Custom worker interrupted by runner shutdown')
            if time.monotonic() >= deadline: raise subprocess.TimeoutExpired(command, 20)
            try: process.wait(timeout=.2)
            except subprocess.TimeoutExpired: pass
        reader.join(timeout=2)
        if process.returncode or overflow.is_set(): raise ValueError('Custom worker failed or exceeded output limits')
        result = json.loads(output)
        if not isinstance(result, dict) or set(result) - {'targets', 'orders', 'state'}:
            raise ValueError('Custom worker must return targets or orders and optional JSON state')
        expected = 'targets' if spec.output == 'targets' else 'orders'
        if expected not in result or ('orders' if expected == 'targets' else 'targets') in result:
            raise ValueError('Custom output differs from frozen adapter contract')
        json.dumps(result, allow_nan=False)
        return result
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        raise ValueError('Custom worker timed out or returned invalid JSON') from None
    finally:
        if process.poll() is None: process.kill()
        subprocess.run([docker,'rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,env=env)
