local _M = {}

local ssl = require "ngx.ssl"

local WILDCARD_DOMAINS = {
    "%.nip%.io$",
    "%.sslip%.io$",
    "%.lvh%.me$",
    "%.localtest%.me$"
}

local function normalize_host(host)
    if not host then
        return nil
    end
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
        return nil
    end
    return red
end

function _M.select_cert()
    local server_name = ssl.server_name()
    if not server_name then
        return
    end
    local normalized_name = normalize_host(server_name)
    local red = get_redis()
    if not red then
        return
    end
    local cert_data = red:get("certs:" .. normalized_name)
    if (not cert_data or cert_data == ngx.null) and normalized_name ~= server_name then
        cert_data = red:get("certs:" .. server_name)
    end
    red:set_keepalive(10000, 100)
    if not cert_data or cert_data == ngx.null then
        return
    end
    local ok, cert_info = pcall(cjson.decode, cert_data)
    if not ok or not cert_info then
        return
    end
    local cert_path = cert_info.cert_path
    local key_path = cert_info.key_path
    if not cert_path or not key_path then
        return
    end
    local f = io.open(cert_path, "r")
    if not f then
        ngx.log(ngx.ERR, "cert file not found: ", cert_path)
        return
    end
    local cert_pem = f:read("*a")
    f:close()
    f = io.open(key_path, "r")
    if not f then
        ngx.log(ngx.ERR, "key file not found: ", key_path)
        return
    end
    local key_pem = f:read("*a")
    f:close()
    local ok, err = ssl.clear_certs()
    if not ok then
        ngx.log(ngx.ERR, "clear_certs failed: ", err)
        return
    end
    local cert_der, err = ssl.cert_pem_to_der(cert_pem)
    if not cert_der then
        ngx.log(ngx.ERR, "cert_pem_to_der failed: ", err)
        return
    end
    local ok, err = ssl.set_der_cert(cert_der)
    if not ok then
        ngx.log(ngx.ERR, "set_der_cert failed: ", err)
        return
    end
    local key_der, err = ssl.priv_key_pem_to_der(key_pem)
    if not key_der then
        ngx.log(ngx.ERR, "priv_key_pem_to_der failed: ", err)
        return
    end
    local ok, err = ssl.set_der_priv_key(key_der)
    if not ok then
        ngx.log(ngx.ERR, "set_der_priv_key failed: ", err)
        return
    end
end

return _M
