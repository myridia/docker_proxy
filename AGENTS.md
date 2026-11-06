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
- `redsocks.conf` — default redsocks configuration, used when no upstream pool is set
- `redirect.sh` — picks the upstream, writes the redsocks config, installs the iptables redirect, starts redsocks
- `origin-view/` — inspection server (`server.py`), client-side check (`client-check.sh`) and its README; prints peer IP, headers, TLS details as seen by an origin

## Upstream pool
`redirect.sh` reads `PROXY_UPSTREAMS` (comma list) or `PROXY_UPSTREAMS_FILE` (one per line, `#` comments). It shuffles the list, resolves each host, probes the TCP port (`PROXY_PROBE_TIMEOUT`, default 2s), and uses the first reachable entry. Forms: `host:port`, `socks5://`, `socks5h://`, `socks4://`, `http://`, with optional `user:pass@`. The chosen upstream IP is added to the REDSOCKS chain as RETURN so redsocks' own connection is not redirected into itself. `PROXY_NO_PROBE=1` skips the probe. Without a pool the container uses `/etc/redsocks.conf` (`host.docker.internal:9999`). One proxy container still means one exit for every client attached to it.

## Traffic path
Client container (`--network container:proxy`) → nat `OUTPUT`/`PREROUTING` → REDSOCKS chain → REDIRECT `:12345` → redsocks → selected upstream → internet. The origin sees the exit address, never the client.

## Limits
- Only TCP is redirected; UDP (DNS/53, QUIC/443) goes out directly.
- IPv6 is not handled by these iptables rules.
- `192.168/16` is not excluded, so LAN destinations are sent through the exit and will not answer.
- The SSH SOCKS5 listener is started as `0.0.0.0:9999`; keep it behind a firewall or bind it to one address.
- A new exit changes the IP, not the TLS/HTTP fingerprint, account or request pattern.

## Conventions
- No comments in code unless asked.
