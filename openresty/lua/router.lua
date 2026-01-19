local _M = {}

local WILDCARD_DOMAINS = {
    "%.nip%.io$",
    "%.sslip%.io$",
    "%.lvh%.me$",
    "%.localtest%.me$"
}

local function normalize_host(host)
    for _, pattern in ipairs(WILDCARD_DOMAINS) do
        if string.match(host, pattern) then
            local base = string.gsub(host, "%.[%d]+%.[%d]+%.[%d]+%.[%d]+%.[%w]+%.[%w]+$", "")
            if base ~= host then
                return base
            end
            base = string.gsub(host, "%.[%d]+-[%d]+-[%d]+-[%d]+%.[%w]+%.[%w]+$", "")
            if base ~= host then
                return base
            end
        end
    end
    return host
end

local function get_redis()
    local redis = require "resty.redis"
    local red = redis:new()
    red:set_timeout(1000)
    local ok, err = red:connect(redis_host, redis_port)
    if not ok then
        ngx.log(ngx.ERR, "redis connect failed: ", err)
        return nil
    end
    return red
end

local function release_redis(red)
    if red then
        red:set_keepalive(10000, 100)
    end
end

function _M.route()
    local host = ngx.var.host
    local normalized_host = normalize_host(host)
    local uri = ngx.var.uri
    local red = get_redis()
    if not red then
        return ngx.exit(502)
    end
    local route_ids, err = red:smembers("routes:index:host:" .. normalized_host)
    if (not route_ids or #route_ids == 0) and normalized_host ~= host then
        route_ids, err = red:smembers("routes:index:host:" .. host)
    end
    if err then
        ngx.log(ngx.ERR, "redis smembers failed: ", err)
        release_redis(red)
        return ngx.exit(502)
    end
    if not route_ids or #route_ids == 0 then
        release_redis(red)
        return ngx.exit(404)
    end
    local selected_route = nil
    local longest_path = 0
    for _, route_id in ipairs(route_ids) do
        local rid = type(route_id) == "string" and route_id or route_id
        local route_data = red:get("routes:" .. rid)
        if route_data and route_data ~= ngx.null then
            local ok, route = pcall(cjson.decode, route_data)
            if ok and route then
                if route.enabled ~= false then
                    local path = route.path or "/"
                    if string.sub(uri, 1, #path) == path and #path > longest_path then
                        selected_route = route
                        selected_route._id = rid
                        longest_path = #path
                    end
                end
            end
        end
    end
    if not selected_route then
        release_redis(red)
        return ngx.exit(404)
    end
    ngx.ctx.route = selected_route
    ngx.var.route_id = selected_route._id or ""
    
    -- Fetch upstreams here to avoid yielding in balancer
    local route_id = selected_route._id or selected_route.id
    local upstreams = red:lrange("upstreams:" .. route_id, 0, -1)
    local healthy_upstreams = {}
    
    if upstreams and #upstreams > 0 then
        for _, upstream_str in ipairs(upstreams) do
            local parts = {}
            for part in string.gmatch(upstream_str, "[^:]+") do
                table.insert(parts, part)
            end
            if #parts >= 2 then
                local addr = parts[1]
                local port = tonumber(parts[2])
                local weight = tonumber(parts[3]) or 1
                local health_key = "upstreams:health:" .. route_id .. ":" .. addr .. ":" .. port
                local health = red:get(health_key)
                if health ~= "unhealthy" then
                    for _ = 1, weight do
                        table.insert(healthy_upstreams, {addr = addr, port = port})
                    end
                end
            end
        end
    end
    
    ngx.ctx.upstreams = healthy_upstreams
    
    -- Release redis here, dont pass to ctx
    release_redis(red)

    if selected_route.strip_path and longest_path > 1 then
        local new_uri = string.sub(uri, longest_path + 1)
        if new_uri == "" then
            new_uri = "/"
        end
        ngx.req.set_uri(new_uri)
    end
end

return _M
