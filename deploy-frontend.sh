#!/bin/bash
gcloud run deploy internstore-frontend \
  --image us-central1-docker.pkg.dev/internstore-taij26/internstore/frontend:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --project internstore-taij26 \
  --port 8080
