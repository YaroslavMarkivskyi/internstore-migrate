with open("k8s/overlays/gcp/kustomization.yaml", "r") as f:
    content = f.read()
content = content.replace('patchesStrategicMerge:\n- nginx-patch.yaml\n', '')
content = content.replace('patchesStrategicMerge:\n- redis-patch.yaml\n', 'patchesStrategicMerge:\n- nginx-patch.yaml\n- redis-patch.yaml\n')
with open("k8s/overlays/gcp/kustomization.yaml", "w") as f:
    f.write(content)
