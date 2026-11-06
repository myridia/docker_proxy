#!/bin/sh
set -eu

url=${1:?usage: client-check.sh http://SERVER:8080/}

printf '== what the target sees ==\n'
curl -fsS --max-time 15 "$url/"

printf '\n\n== request as sent (origin-form, no Proxy-* headers expected) ==\n'
curl -sS -v -o /dev/null --max-time 15 "$url/" 2>&1 | sed -n '/^> /p'

printf '\n== exit ip ==\n'
curl -fsS --max-time 15 https://api.ipify.org
printf '\n'

printf '\n== resolver config (UDP is not proxied by redsocks) ==\n'
cat /etc/resolv.conf

printf '\n== dns answer ==\n'
getent ahosts api.ipify.org || true

printf '\n== routes ==\n'
ip route 2>/dev/null || true
