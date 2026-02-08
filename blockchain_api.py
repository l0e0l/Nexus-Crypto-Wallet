"""
Blockchain API v3.2 - Custom RPC support, parallel balance fetching
"""

import time, threading
import requests


class Cache:
    def __init__(self, ttl=90):
        self.ttl = ttl; self.data = {}; self.lock = threading.Lock()
    def get(self, k):
        with self.lock:
            if k in self.data:
                v, t = self.data[k]
                if time.time() - t < self.ttl: return v
                del self.data[k]
        return None
    def set(self, k, v):
        with self.lock: self.data[k] = (v, time.time())


CG_IDS = {
    "BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin","MATIC":"matic-network",
    "LTC":"litecoin","DOGE":"dogecoin","BCH":"bitcoin-cash",
    "TRX":"tron","SOL":"solana","USDT":"tether","USDC":"usd-coin",
}

COINCAP_IDS = {
    "BTC":"bitcoin","ETH":"ethereum","BNB":"binance-coin","MATIC":"polygon",
    "LTC":"litecoin","DOGE":"dogecoin","BCH":"bitcoin-cash",
    "TRX":"tron","SOL":"solana","USDT":"tether","USDC":"usd-coin",
}


class BlockchainAPI:
    def __init__(self, config=None):
        self.config = config or {}
        self.pcache = Cache(120)
        self.bcache = Cache(30)
        self.ccache = Cache(120)
        self.s = requests.Session()
        self.s.headers.update({"User-Agent":"NexusWallet/3.2","Accept":"application/json"})
        self.timeout = 10

    def set_config(self, config):
        self.config = config

    def _get_rpc(self, sym):
        """Get custom RPC if set."""
        return self.config.get("custom_rpc", {}).get(sym, {}).get("rpc", "")

    def _get(self, url, **kw):
        try:
            r = self.s.get(url, timeout=self.timeout, **kw)
            if r.status_code == 200: return r.json()
        except: pass
        return None

    def _post(self, url, data):
        try:
            r = self.s.post(url, json=data, timeout=self.timeout)
            if r.status_code == 200: return r.json()
        except: pass
        return None

    # ── Prices ────────────────────────────────────────────────

    def get_prices(self, symbols=None, vs="usd"):
        if not symbols: symbols = list(CG_IDS.keys())
        prices = {}; need = []
        for s in symbols:
            c = self.pcache.get(f"p_{s}")
            if c is not None: prices[s] = c
            else: need.append(s)
        if not need: return prices

        # CoinGecko - also check custom coins coingecko ids
        all_ids = dict(CG_IDS)
        for s in need:
            from wallet_core import SUPPORTED_COINS
            cfg = SUPPORTED_COINS.get(s, {})
            cg = cfg.get("coingecko", "")
            if cg and s not in all_ids:
                all_ids[s] = cg

        try:
            ids = ",".join(all_ids[s] for s in need if s in all_ids)
            if ids:
                d = self._get("https://api.coingecko.com/api/v3/simple/price",
                              params={"ids":ids,"vs_currencies":vs,"include_24hr_change":"true"})
                if d:
                    for s in need:
                        cid = all_ids.get(s)
                        if cid and cid in d:
                            p = d[cid].get(vs, 0)
                            if p: prices[s] = p; self.pcache.set(f"p_{s}", p)
                            ch = d[cid].get(f"{vs}_24h_change")
                            if ch is not None: self.ccache.set(f"ch_{s}", ch)
        except: pass

        # Fallback CoinCap
        missing = [s for s in need if s not in prices]
        for s in missing:
            try:
                cid = COINCAP_IDS.get(s)
                if cid:
                    d = self._get(f"https://api.coincap.io/v2/assets/{cid}")
                    if d and "data" in d:
                        p = float(d["data"].get("priceUsd", 0))
                        if p > 0:
                            prices[s] = p; self.pcache.set(f"p_{s}", p)
                            ch = float(d["data"].get("changePercent24Hr", 0))
                            self.ccache.set(f"ch_{s}", ch)
            except: pass
        return prices

    def get_24h_change(self, sym):
        return self.ccache.get(f"ch_{sym}")

    # ── Balances ──────────────────────────────────────────────

    def get_balance(self, sym, addr):
        if not addr or "Error" in str(addr): return None
        ck = f"b_{sym}_{addr}"
        c = self.bcache.get(ck)
        if c is not None: return c
        bal = None
        try:
            # Check if it's a custom coin
            from wallet_core import SUPPORTED_COINS
            cfg = SUPPORTED_COINS.get(sym, {})

            if cfg.get("is_custom"):
                if cfg.get("is_token") and cfg.get("contract"):
                    bal = self._erc20(addr, cfg["contract"], cfg.get("decimals", 18),
                                      cfg.get("rpc") or self._get_rpc(sym))
                elif cfg.get("is_evm") and cfg.get("rpc"):
                    rpc = self._get_rpc(sym) or cfg.get("rpc", "")
                    bal = self._evm_balance(addr, rpc, cfg.get("decimals", 18))
                else:
                    bal = 0.0
            else:
                h = {"BTC":self._btc,"ETH":self._eth,"LTC":self._ltc,"DOGE":self._doge,
                     "BCH":self._bch,"TRX":self._trx,"SOL":self._sol,
                     "BNB":self._bnb,"MATIC":self._matic,
                     "USDT":lambda a: self._erc20(a, "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
                     "USDC":lambda a: self._erc20(a, "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6)}
                f = h.get(sym)
                if f: bal = f(addr)

            if bal is not None: self.bcache.set(ck, bal)
        except: pass
        return bal

    def _evm_balance(self, addr, rpc, decimals=18):
        """Generic EVM balance via JSON-RPC."""
        if not rpc: return None
        r = self._post(rpc, {"jsonrpc":"2.0","method":"eth_getBalance","params":[addr,"latest"],"id":1})
        if r and "result" in r: return int(r["result"], 16) / (10 ** decimals)
        return None

    def _btc(self, a):
        custom_rpc = self._get_rpc("BTC")
        if custom_rpc:
            # Custom mempool instance
            d = self._get(f"{custom_rpc}/api/address/{a}")
            if d and "chain_stats" in d:
                return (d["chain_stats"].get("funded_txo_sum",0) - d["chain_stats"].get("spent_txo_sum",0)) / 1e8
        d = self._get(f"https://mempool.space/api/address/{a}")
        if d and "chain_stats" in d:
            return (d["chain_stats"].get("funded_txo_sum",0) - d["chain_stats"].get("spent_txo_sum",0)) / 1e8
        return None

    def _eth(self, a):
        custom_rpc = self._get_rpc("ETH")
        if custom_rpc:
            r = self._post(custom_rpc, {"jsonrpc":"2.0","method":"eth_getBalance","params":[a,"latest"],"id":1})
            if r and "result" in r: return int(r["result"], 16) / 1e18
        d = self._get(f"https://eth.blockscout.com/api/v2/addresses/{a}")
        if d and "coin_balance" in d:
            raw = d.get("coin_balance")
            if raw: return int(raw) / 1e18
        r = self._post("https://cloudflare-eth.com",
                       {"jsonrpc":"2.0","method":"eth_getBalance","params":[a,"latest"],"id":1})
        if r and "result" in r: return int(r["result"], 16) / 1e18
        return None

    def _ltc(self, a):
        d = self._get(f"https://api.blockcypher.com/v1/ltc/main/addrs/{a}/balance")
        if d and "balance" in d: return d["balance"] / 1e8
        return None

    def _doge(self, a):
        d = self._get(f"https://api.blockcypher.com/v1/doge/main/addrs/{a}/balance")
        if d and "balance" in d: return d["balance"] / 1e8
        return None

    def _bch(self, a):
        d = self._get(f"https://api.blockchair.com/bitcoin-cash/dashboards/address/{a}")
        if d and "data" in d:
            return d["data"].get(a, {}).get("address", {}).get("balance", 0) / 1e8
        return None

    def _trx(self, a):
        custom_rpc = self._get_rpc("TRX")
        # Method 1: TronGrid v1
        try:
            url = custom_rpc or "https://api.trongrid.io"
            d = self._get(f"{url}/v1/accounts/{a}")
            if d and "data" in d and d["data"]:
                return d["data"][0].get("balance", 0) / 1e6
        except: pass
        # Method 2: TronScan
        try:
            d = self._get("https://apilist.tronscanapi.com/api/accountv2", params={"address": a})
            if d and "balance" in d: return d["balance"] / 1e6
        except: pass
        # Method 3: wallet/getaccount
        try:
            r = self._post(f"{custom_rpc or 'https://api.trongrid.io'}/wallet/getaccount",
                           {"address": a, "visible": True})
            if r and "balance" in r: return r["balance"] / 1e6
            if r is not None: return 0.0
        except: pass
        return 0.0

    def _sol(self, a):
        custom_rpc = self._get_rpc("SOL")
        rpc = custom_rpc or "https://api.mainnet-beta.solana.com"
        r = self._post(rpc, {"jsonrpc":"2.0","id":1,"method":"getBalance","params":[a]})
        if r and "result" in r: return r.get("result",{}).get("value", 0) / 1e9
        return None

    def _bnb(self, a):
        custom_rpc = self._get_rpc("BNB")
        rpc = custom_rpc or "https://bsc-dataseed1.binance.org"
        r = self._post(rpc, {"jsonrpc":"2.0","method":"eth_getBalance","params":[a,"latest"],"id":1})
        if r and "result" in r: return int(r["result"], 16) / 1e18
        return None

    def _matic(self, a):
        custom_rpc = self._get_rpc("MATIC")
        rpc = custom_rpc or "https://polygon-rpc.com"
        r = self._post(rpc, {"jsonrpc":"2.0","method":"eth_getBalance","params":[a,"latest"],"id":1})
        if r and "result" in r: return int(r["result"], 16) / 1e18
        return None

    def _erc20(self, addr, contract, decimals, rpc=None):
        data = "0x70a08231" + addr[2:].lower().zfill(64)
        rpc_url = rpc or self._get_rpc("ETH") or "https://cloudflare-eth.com"
        r = self._post(rpc_url, {"jsonrpc":"2.0","method":"eth_call",
                        "params":[{"to":contract,"data":data},"latest"],"id":1})
        if r and "result" in r:
            raw = r["result"]
            if raw and raw != "0x": return int(raw, 16) / (10 ** decimals)
        return 0.0

    def get_all_balances(self, addrs):
        results = {}; lock = threading.Lock()
        threads = []
        def fetch(s, a):
            b = self.get_balance(s, a)
            with lock: results[s] = b
        for s, a in addrs.items():
            t = threading.Thread(target=fetch, args=(s, a), daemon=True)
            threads.append(t); t.start()
        for t in threads: t.join(timeout=15)
        return results

    def fetch_balances_async(self, addrs, cb):
        threading.Thread(target=lambda: cb(self.get_all_balances(addrs)), daemon=True).start()

    def fetch_prices_async(self, syms, cb):
        threading.Thread(target=lambda: cb(self.get_prices(syms)), daemon=True).start()
