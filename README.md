<img src="docker_proxy.svg" alt="docker_proxy" width="120">

## run Proxy
```
docker run -d --name proxy --cap-add=NET_ADMIN --add-host=host.docker.internal:host-gateway myridia/proxy
```

## test
```
docker run --network container:proxy -it myridia/trixie bash
curl api.ipify.org
```




## Apply
```
kitty docker run -it  --network container:proxy -v /home/veto/webs:/home/veto/webs  myridia/opencode bash
```

## Demo 
```
ssh root@88.198.49.173 -D 0.0.0.0:9999
docker rm proxy && docker run -d --name proxy --cap-add=NET_ADMIN --add-host=host.docker.internal:host-gateway myridia/proxy
kitty docker run -it  --network container:proxy -v /home/veto/webs:/home/veto/webs  myridia/opencode bash
```
