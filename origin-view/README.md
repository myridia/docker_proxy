# origin-view

A small HTTP server that prints what an origin sees about a client coming
through the proxy: the peer IP (the exit address), the raw request line, every
header in received order, the body hash, and — with TLS — the TLS version,
cipher, ALPN and SNI.

The client cannot see any of this by itself. `curl ifconfig.me` only shows an
address; this server shows the request as it actually arrived.

## Run it outside the exit

The server must be reachable from the exit node (`88.198.49.173`), because the
request leaves the tunnel there. Run it on the exit host itself or on another
public host.

```sh
python3 server.py --port 8080
```

Output on every request:

```
2026-11-06T12:34:56+00:00 #3 GET / HTTP/1.1
  peer      88.198.49.173:51234
  headers
    Host: 203.0.113.10:8080
    User-Agent: curl/8.5.0
    Accept: */*
  notes
    - origin-form target: no HTTP proxy on the client, consistent with a transparent redirect
    - peer address is public: this is the exit IP the target sees
```

`/` returns the same text. `/json` (or `?format=json`) returns it as JSON.

## Run it from the client

The client container shares the proxy's network namespace, so start it the
usual way and then run the checks:

```sh
docker run --network container:proxy -it \
  -v /home/veto/webs:/home/veto/webs myridia/trixie bash
```

```sh
sh /home/veto/webs/github/docker_proxy/origin-view/client-check.sh http://88.198.49.173:8080/
```

The script shows the origin view, the raw request lines, the exit IP, the
resolver config and the routes in one pass.

If the server runs on the LAN host instead (`192.168.43.2`), it is not reachable
through the tunnel: `redirect.sh` excludes `10/8` and `172.16/12` but not
`192.168/16`, so that traffic is sent out through the exit and cannot come back
to a private address. Add `-d 192.168.0.0/16 -j RETURN` to test LAN reachability.

## TLS

TLS adds what a plain HTTP target cannot show: protocol version, cipher, ALPN
and SNI, plus the certificate the client accepted.

```sh
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout key.pem -out cert.pem -subj /CN=origin-view

python3 server.py --port 8443 --tls-cert cert.pem --tls-key key.pem
curl -k https://88.198.49.173:8443/
```

ALPN is limited to `http/1.1`. JA3/JA4 fingerprints are not computed; they
need the raw ClientHello.

## What it does not show

- DNS: redsocks only redirects TCP. UDP/53 goes out directly, so the resolver
  sees the real client network, not the exit.
- QUIC/HTTP3: UDP/443 is not redirected either, so a client that prefers QUIC
  can bypass the proxy entirely.
- The original client address: SOCKS5 does not carry it. Only the exit address
  arrives at the origin.

## Run from the Host 
```
ip route | grep default        # e.g. default via 172.17.0.1
curl -s http://172.17.0.1:8080/
curl -s http://172.17.0.1:8080/json | python3 -m json.tool
```
