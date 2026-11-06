#!/bin/bash
set -euo pipefail

UNIQUE_ID=$(printf '%04x%04x%04x' "$RANDOM" "$RANDOM" "$RANDOM")
export UNIQUE_ID
echo "Initializing instance: $UNIQUE_ID"

PROBE_TIMEOUT=${PROXY_PROBE_TIMEOUT:-2}

trim() {
  local value=$1
  value=${value#"${value%%[![:space:]]*}"}
  value=${value%"${value##*[![:space:]]}"}
  printf '%s' "$value"
}

quote() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '%s' "$value"
}

parse_upstream() {
  local raw=$1
  upstream_type=socks5
  local rest=$raw
  if [[ $rest == *://* ]]; then
    upstream_type=${rest%%://*}
    rest=${rest#*://}
  fi
  case $upstream_type in
    socks5|socks5h) upstream_type=socks5 ;;
    socks4) ;;
    http) upstream_type=http-connect ;;
    http-connect|http-relay) ;;
    *) return 1 ;;
  esac
  upstream_login=
  upstream_password=
  if [[ $rest == *@* ]]; then
    local creds=${rest%@*}
    rest=${rest##*@}
    upstream_login=${creds%%:*}
    if [[ $creds == *:* ]]; then
      upstream_password=${creds#*:}
    fi
  fi
  if [[ $rest != *:* ]]; then
    return 1
  fi
  upstream_host=${rest%:*}
  upstream_port=${rest##*:}
  if [[ $upstream_host == \[*\] ]]; then
    upstream_host=${upstream_host#[}
    upstream_host=${upstream_host%]}
  fi
  if [[ -z $upstream_host || ! $upstream_port =~ ^[0-9]+$ ]]; then
    return 1
  fi
  return 0
}

probe_upstream() {
  timeout "$PROBE_TIMEOUT" bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null
}

lines=()
if [[ -n ${PROXY_UPSTREAMS_FILE:-} && -r ${PROXY_UPSTREAMS_FILE} ]]; then
  mapfile -t lines < "$PROXY_UPSTREAMS_FILE"
elif [[ -n ${PROXY_UPSTREAMS:-} ]]; then
  mapfile -t lines < <(printf '%s\n' "$PROXY_UPSTREAMS" | tr ',' '\n')
elif [[ -n ${PROXY_UPSTREAM:-} ]]; then
  lines=("$PROXY_UPSTREAM")
fi

candidates=()
for line in "${lines[@]}"; do
  line=$(trim "$line")
  if [[ -z $line || $line == \#* ]]; then
    continue
  fi
  candidates+=("$line")
done

upstream_ip=
config=/etc/redsocks.conf

if [[ ${#candidates[@]} -gt 0 ]]; then
  picked=
  mapfile -t shuffled < <(printf '%s\n' "${candidates[@]}" | shuf)
  for entry in "${shuffled[@]}"; do
    if ! parse_upstream "$entry"; then
      echo "skip malformed upstream: $entry" >&2
      continue
    fi
    resolved=$(getent ahostsv4 "$upstream_host" 2>/dev/null | sed -n '1s/[[:space:]].*//p') || true
    if [[ -z $resolved ]]; then
      echo "skip unresolved upstream: $entry" >&2
      continue
    fi
    if [[ ${PROXY_NO_PROBE:-0} == 1 ]] || probe_upstream "$resolved" "$upstream_port"; then
      upstream_ip=$resolved
      picked=$entry
      break
    fi
    echo "upstream not answering: $entry" >&2
  done
  if [[ -z $picked ]]; then
    echo "no reachable upstream in pool" >&2
    exit 1
  fi

  parse_upstream "$picked"

  {
    printf 'base {\n'
    printf '    daemon = off;\n'
    printf '    log_debug = off;\n'
    printf '    log_info = on;\n'
    printf '    redirector = iptables;\n'
    printf '}\n'
    printf 'redsocks {\n'
    printf '    local_ip = 0.0.0.0;\n'
    printf '    local_port = 12345;\n'
    printf '    ip = %s;\n' "$upstream_ip"
    printf '    port = %s;\n' "$upstream_port"
    printf '    type = %s;\n' "$upstream_type"
    if [[ -n $upstream_login ]]; then
      printf '    login = "%s";\n' "$(quote "$upstream_login")"
      printf '    password = "%s";\n' "$(quote "$upstream_password")"
    fi
    printf '}\n'
  } > /tmp/redsocks.conf
  config=/tmp/redsocks.conf

  display_host=$upstream_host
  if [[ -n $upstream_login ]]; then
    display_host="${upstream_login}@${upstream_host}"
  fi
  echo "upstream: ${upstream_type}://${display_host}:${upstream_port} (${upstream_ip})"
else
  echo "upstream: default config /etc/redsocks.conf"
fi

while iptables -t nat -D PREROUTING -p tcp -j REDSOCKS 2>/dev/null; do :; done
while iptables -t nat -D OUTPUT -p tcp -j REDSOCKS 2>/dev/null; do :; done
iptables -t nat -F REDSOCKS 2>/dev/null || true
iptables -t nat -X REDSOCKS 2>/dev/null || true

iptables -t nat -N REDSOCKS
iptables -t nat -A REDSOCKS -d 127.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 10.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 172.16.0.0/12 -j RETURN
if [[ -n $upstream_ip ]]; then
  iptables -t nat -A REDSOCKS -d "$upstream_ip" -j RETURN
fi
iptables -t nat -A REDSOCKS -p tcp -j REDIRECT --to-ports 12345
iptables -t nat -A PREROUTING -p tcp -j REDSOCKS
iptables -t nat -A OUTPUT -p tcp -j REDSOCKS

exec redsocks -c "$config"
