# AGENTS.md — docker_proxy

## What this is
Docker container running a transparent proxy using redsocks + iptables. Routes container traffic through a proxy.

## Stack
- Debian
- redsocks
- iptables

## Build
```bash
docker build -t myridia/proxy .
```

## Run
```bash
docker run -d --name proxy --cap-add=NET_ADMIN --add-host=host.docker.internal:host-gateway myridia/proxy
```

## Structure
- `Dockerfile` — Debian + redsocks + iptables
- `redsocks.conf` — redsocks configuration
- `redirect.sh` — iptables redirect entrypoint

## Conventions
- No comments in code unless asked.
