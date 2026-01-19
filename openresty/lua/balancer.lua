local _M = {}

local balancer = require "ngx.balancer"

local function get_redis()
    local redis = require "resty.redis"
    local red = redis:new()
    red:set_timeout(1000)
    local ok, err = red:connect(redis_host, redis_port)
    if not ok then
        return nil
    end
    return red
end

local function release_redis(red)
    if red then
        red:set_keepalive(10000, 100)
    end
end

function _M.balance()
    local route = ngx.ctx.route
    if not route then
        ngx.log(ngx.ERR, "no route in context")
        return ngx.exit(502)
    end
    
    local healthy_upstreams = ngx.ctx.upstreams
    if not healthy_upstreams or #healthy_upstreams == 0 then
        ngx.log(ngx.ERR, "no healthy upstreams for route")
        return ngx.exit(502)
    end

    local selected
    local lb = route.load_balancer or "round_robin"
    if lb == "random" then
        math.randomseed(ngx.now() * 1000 + ngx.worker.pid())
        selected = healthy_upstreams[math.random(#healthy_upstreams)]
    elseif lb == "ip_hash" then
        local ip = ngx.var.remote_addr or "127.0.0.1"
        local hash = ngx.crc32_long(ip)
        local idx = (hash % #healthy_upstreams) + 1
        selected = healthy_upstreams[idx]
    else
        local idx = ((ngx.worker.id() or 0) + (tonumber(ngx.var.connection) or 0)) % #healthy_upstreams + 1
        selected = healthy_upstreams[idx]
    end
    
    local ok, err = balancer.set_current_peer(selected.addr, selected.port)
    if not ok then
        ngx.log(ngx.ERR, "set_current_peer failed: ", err)
        return ngx.exit(502)
    end

end

return _M
