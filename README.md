<img src="docker_proxy.svg" alt="docker_proxy" width="120">

## run Proxy
```
docker run -d --name proxy --cap-add=NET_ADMIN --add-host=host.docker.internal:host-gateway myridia/proxy
```

## run with an upstream pool
`PROXY_UPSTREAMS` is a comma-separated list. Each container start picks one random upstream that answers a TCP probe, so the receiving server sees a different exit per proxy container.
```
docker run -d --name proxy --cap-add=NET_ADMIN \
  -e PROXY_UPSTREAMS='socks5://1.2.3.4:9999,socks5://user:pass@5.6.7.8:1080,http://9.10.11.12:3128' \
  myridia/proxy
```

For credentials keep the list outside the repo and mount it. One upstream per line, `#` at line start comments out the line.
```
docker run -d --name proxy --cap-add=NET_ADMIN \
  -v /home/veto/proxies.txt:/run/proxies.txt:ro \
  -e PROXY_UPSTREAMS_FILE=/run/proxies.txt \
  myridia/proxy
```

`PROXY_UPSTREAM` sets a single upstream instead. `PROXY_NO_PROBE=1` skips the TCP probe and picks the first shuffled entry. `PROXY_PROBE_TIMEOUT` changes the 2 second probe timeout. Restart or recreate the proxy to pick another exit; all clients attached to it share that exit. Supported forms: `host:port`, `socks5://`, `socks5h://`, `socks4://`, `http://`.

## test
```
docker run --network container:proxy -it myridia/trixie bash
curl api.ipify.org
```




## Apply
```
kitty docker run -it  --network container:proxy -v /home/veto/webs:/home/veto/webs  myridia/opencode bash
```

## Inspect
`origin-view/README.md` — server that prints the exit IP, raw headers and TLS details an origin sees.

## Demo 
```
ssh root@88.198.49.173 -D 0.0.0.0:9999
docker rm proxy && docker run -d --name proxy --cap-add=NET_ADMIN --add-host=host.docker.internal:host-gateway myridia/proxy
kitty docker run -it  --network container:proxy -v /home/veto/webs:/home/veto/webs  myridia/opencode bash
```
