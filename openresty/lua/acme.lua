local _M = {}

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

function _M.handle_challenge()
    local uri = ngx.var.uri
    local token = string.match(uri, "^/.well%-known/acme%-challenge/(.+)$")
    if not token then
        return ngx.exit(404)
    end
    local red = get_redis()
    if not red then
        ngx.log(ngx.ERR, "redis not available for acme challenge")
        return ngx.exit(500)
    end
    local key_auth = red:get("acme:challenge:" .. token)
    red:set_keepalive(10000, 100)
    if not key_auth or key_auth == ngx.null then
        return ngx.exit(404)
    end
    ngx.header["Content-Type"] = "text/plain"
    ngx.say(key_auth)
    ngx.exit(200)
end

return _M
