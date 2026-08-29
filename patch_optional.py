import os
import glob
import yaml

for filepath in glob.glob("k8s/base/*/deployment.yaml"):
    with open(filepath, 'r') as f:
        docs = list(yaml.safe_load_all(f))
    
    for doc in docs:
        if not doc or doc.get('kind') != 'Deployment': continue
        containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
        for c in containers:
            if 'envFrom' in c:
                for env in c['envFrom']:
                    if 'secretRef' in env:
                        env['secretRef']['optional'] = True
            if 'env' in c:
                for env in c['env']:
                    if 'valueFrom' in env and 'secretKeyRef' in env['valueFrom']:
                        env['valueFrom']['secretKeyRef']['optional'] = True
    
    with open(filepath, 'w') as f:
        yaml.dump_all(docs, f, default_flow_style=False, sort_keys=False)
