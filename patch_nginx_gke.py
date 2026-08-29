import re

with open("k8s/overlays/gcp/nginx-gke.conf", "r") as f:
    content = f.read()

# 1. Replace resolver
content = re.sub(r'resolver 127\.0\.0\.11[^;]*;', 'resolver kube-dns.kube-system.svc.cluster.local valid=5s;', content)

# 2. Remove the 8080 -> 8443 redirect server block
content = re.sub(r'server \{\s*listen 8080;\s*return 301 [^\}]+\}', '', content)

# 3. Change the 8443 server block to listen on 8080 without SSL
content = re.sub(r'listen 8443 ssl;', 'listen 8080;', content)
content = re.sub(r'ssl_certificate[^;]*;', '', content)
content = re.sub(r'ssl_certificate_key[^;]*;', '', content)
content = re.sub(r'ssl_protocols[^;]*;', '', content)
content = re.sub(r'ssl_ciphers[^;]*;', '', content)
content = re.sub(r'ssl_prefer_server_ciphers[^;]*;', '', content)

# 4. Add the /health endpoint for the GKE load balancer to use!
# The BackendConfig says requestPath: /api/catalog/health
# But we can just add a direct /health on nginx that returns 200 OK!
# That way GCLB knows NGINX is healthy.
health_block = """
    location = /health {
      return 200 'OK';
      add_header Content-Type text/plain;
    }
"""
content = content.replace('listen 8080;', 'listen 8080;' + health_block)

with open("k8s/overlays/gcp/nginx-gke.conf", "w") as f:
    f.write(content)
