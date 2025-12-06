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

## Setuped CI/CD
no need to do above steps just push to dev brnach on github.

### Adding environment variables in azure portal
1. Go to your container app -> Export Template
2. copy template
3. search new template deployment
4. paste the template
5. modfiy what is needed 
6. then 
add this 
```json
"imageRegistryCredentials": [
  {
    "server": "adivistaapiimage.azurecr.io",
    "username": "<ACR-username-from-Access-keys>",
    "password": "<ACR-password-from-Access-keys>"
  }
]
```
7. you can get ACR-username and password from Access keys in your container registry(advistaApiImage) in azure portal.
8. in workspace key add same password as above.
9. deploy

10. restart the advista-api-container in azure portal

11. copy new ipv4 address and update it in cloudflare dns for advista-api
