# deploying

### login first

```bash
az acr login --name adivistaApiImage
```

### build and push

```bash
docker build -t adivistaapiimage.azurecr.io/python-api:latest . && docker push adivistaapiimage.azurecr.io/python-api:latest
```

then restart the advista-api-container in azure portal
