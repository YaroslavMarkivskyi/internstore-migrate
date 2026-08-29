import os
import glob
import yaml

for filepath in glob.glob("k8s/base/*/deployment.yaml"):
    with open(filepath, 'r') as f:
        docs = list(yaml.safe_load_all(f))
    
    modified = False
    for doc in docs:
        if not doc or doc.get('kind') != 'Deployment': continue
        containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
        for c in containers:
            if 'livenessProbe' in c:
                if c['livenessProbe'].get('initialDelaySeconds', 0) < 60:
                    c['livenessProbe']['initialDelaySeconds'] = 60
                    modified = True
            if 'readinessProbe' in c:
                if c['readinessProbe'].get('initialDelaySeconds', 0) < 30:
                    c['readinessProbe']['initialDelaySeconds'] = 30
                    modified = True
    
    if modified:
        with open(filepath, 'w') as f:
            yaml.dump_all(docs, f, default_flow_style=False, sort_keys=False)
