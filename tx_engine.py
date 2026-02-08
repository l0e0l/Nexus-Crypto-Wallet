"""
Transaction Engine v3.2 — Real signing & broadcasting for all supported chains.
Fixes: proper fee estimation (low/med/high/custom), address validation,
correct signing per chain, robust error handling, reliable broadcasting.
"""

import hashlib, time, json, base64, re, struct, threading
import requests

# Optional chain libraries (graceful fallback)
try:
    from eth_account import Account as EthAccount
    HAS_ETH = True
except ImportError:
    HAS_ETH = False

try:
    from bit import PrivateKey as BtcKey
    HAS_BIT = True
except ImportError:
    HAS_BIT = False

try:
    from bitcash import PrivateKey as BchKey
    HAS_BCH = True
except ImportError:
    HAS_BCH = False

try:
    from solders.keypair import Keypair as SolKeypair
    from solders.pubkey import Pubkey as SolPubkey
    from solders.system_program import TransferParams, transfer as sol_transfer
    from solders.transaction import Transaction as SolTx
    from solders.message import Message as SolMsg
    from solders.hash import Hash as SolHash
    HAS_SOL = True
except ImportError:
    HAS_SOL = False

try:
    import ecdsa
    HAS_ECDSA = True
except ImportError:
    HAS_ECDSA = False

try:
    import base58 as b58lib
    HAS_BASE58 = True
except ImportError:
    HAS_BASE58 = False

# ══════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════
EVM_CHAINS = {
    "ETH":  {"chain_id": 1,   "rpc": "https://cloudflare-eth.com",
             "explorer": "https://etherscan.io/tx/{}"},
    "BNB":  {"chain_id": 56,  "rpc": "https://bsc-dataseed1.binance.org",
             "explorer": "https://bscscan.com/tx/{}"},
    "MATIC":{"chain_id": 137, "rpc": "https://polygon-rpc.com",
             "explorer": "https://polygonscan.com/tx/{}"},
}

ERC20_TOKENS = {
    "USDT": {"contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
             "decimals": 6, "chain": "ETH"},
    "USDC": {"contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
             "decimals": 6, "chain": "ETH"},
}

EXPLORERS = {
    "BTC":  "https://mempool.space/tx/{}",
    "SOL":  "https://solscan.io/tx/{}",
    "TRX":  "https://tronscan.org/#/transaction/{}",
    "LTC":  "https://blockchair.com/litecoin/transaction/{}",
    "DOGE": "https://blockchair.com/dogecoin/transaction/{}",
    "BCH":  "https://blockchair.com/bitcoin-cash/transaction/{}",
}

FEE_MULT = {"low": 0.8, "medium": 1.0, "high": 1.5}

# ══════════════════════════════════════════════════════════════
#  HTTP HELPERS
# ══════════════════════════════════════════════════════════════
_sess = requests.Session()
_sess.headers.update({"User-Agent": "NexusWallet/3.2", "Accept": "application/json"})
_TIMEOUT = 20


def _get(url, **kw):
    try:
        r = _sess.get(url, timeout=_TIMEOUT, **kw)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _post(url, data, headers=None):
    """POST JSON. Returns parsed JSON on ANY status (to capture errors)."""
    try:
        r = _sess.post(url, json=data, timeout=_TIMEOUT, headers=headers or {})
        try:
            return r.json()
        except ValueError:
            return {"_raw": r.text, "_status": r.status_code} if r.ok else None
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except Exception:
        return None


def _rpc(url, method, params):
    """JSON-RPC 2.0 call."""
    resp = _post(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if resp is None:
        raise Exception(f"No response from {url}")
    if "error" in resp:
        err = resp["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise Exception(msg)
    return resp.get("result")


# ══════════════════════════════════════════════════════════════
class TxResult:
    __slots__ = ("success", "tx_hash", "error", "fee", "explorer_url")
    def __init__(self, success, tx_hash="", error="", fee=0.0, explorer_url=""):
        self.success = success
        self.tx_hash = tx_hash
        self.error = error
        self.fee = fee
        self.explorer_url = explorer_url


# ══════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════
class TxEngine:
    def __init__(self, config=None):
        self.config = config or {}

    def set_config(self, config):
        self.config = config

    def _rpc_url(self, sym):
        custom = self.config.get("custom_rpc", {}).get(sym, {}).get("rpc", "")
        if custom: return custom
        if sym in EVM_CHAINS: return EVM_CHAINS[sym]["rpc"]
        if sym in ERC20_TOKENS:
            return EVM_CHAINS.get(ERC20_TOKENS[sym]["chain"], {}).get("rpc", "https://cloudflare-eth.com")
        return {"BTC":"https://mempool.space","SOL":"https://api.mainnet-beta.solana.com",
                "TRX":"https://api.trongrid.io"}.get(sym, "")

    def _explorer_url(self, sym, tx_hash):
        custom = self.config.get("custom_rpc", {}).get(sym, {}).get("explorer", "")
        if custom: return custom.replace("{}", tx_hash)
        if sym in EVM_CHAINS: return EVM_CHAINS[sym]["explorer"].format(tx_hash)
        if sym in ERC20_TOKENS:
            ch = ERC20_TOKENS[sym]["chain"]
            return EVM_CHAINS.get(ch, {}).get("explorer", "").format(tx_hash)
        return EXPLORERS.get(sym, "").format(tx_hash) if sym in EXPLORERS else ""

    # ── ADDRESS VALIDATION ────────────────────────────────────
    @staticmethod
    def validate_address(coin, address):
        if not address or not address.strip():
            return False, "Address is empty"
        a = address.strip()
        V = {
            "BTC": (lambda x: bool(re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$',x) or re.match(r'^bc1[qp][a-z0-9]{38,58}$',x)),
                    "1..., 3..., bc1q..., or bc1p..."),
            "ETH": (lambda x: bool(re.match(r'^0x[0-9a-fA-F]{40}$',x)), "0x + 40 hex"),
            "BNB": (lambda x: bool(re.match(r'^0x[0-9a-fA-F]{40}$',x)), "0x + 40 hex"),
            "MATIC":(lambda x: bool(re.match(r'^0x[0-9a-fA-F]{40}$',x)), "0x + 40 hex"),
            "USDT": (lambda x: bool(re.match(r'^0x[0-9a-fA-F]{40}$',x)), "0x + 40 hex"),
            "USDC": (lambda x: bool(re.match(r'^0x[0-9a-fA-F]{40}$',x)), "0x + 40 hex"),
            "SOL":  (lambda x: bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$',x)), "Base58 32-44 chars"),
            "TRX":  (lambda x: bool(re.match(r'^T[1-9A-HJ-NP-Za-km-z]{33}$',x)), "T + 33 chars"),
            "LTC":  (lambda x: bool(re.match(r'^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$',x) or re.match(r'^ltc1[a-z0-9]{39,59}$',x)),
                     "L..., M..., 3..., or ltc1..."),
            "DOGE": (lambda x: bool(re.match(r'^D[1-9A-HJ-NP-Za-km-z]{25,34}$',x)), "D..."),
            "BCH":  (lambda x: bool(re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$',x) or re.match(r'^(bitcoincash:)?[qp][a-z0-9]{41}$',x)),
                     "1..., 3..., q..., or p..."),
        }
        c = coin.upper()
        if c in V:
            fn, fmt = V[c]
            return (True, "") if fn(a) else (False, f"Expected: {fmt}")
        # Custom EVM
        try:
            from wallet_core import SUPPORTED_COINS
            cfg = SUPPORTED_COINS.get(c, {})
            if cfg.get("shares_address_with") == "ETH" or cfg.get("is_evm") or cfg.get("is_token"):
                if re.match(r'^0x[0-9a-fA-F]{40}$', a): return True, ""
                return False, "Expected: 0x + 40 hex"
        except ImportError: pass
        return (True, "") if len(a) >= 20 else (False, "Too short")

    # ── DEPENDENCY CHECK ──────────────────────────────────────
    def check_deps(self, coin):
        c = coin.upper()
        if c in ("ETH","BNB","MATIC","USDT","USDC"):
            return (True,"") if HAS_ETH else (False,"eth-account")
        if c == "BTC": return (True,"") if HAS_BIT else (False,"bit")
        if c == "BCH": return (True,"") if HAS_BCH else (False,"bitcash")
        if c == "SOL": return (True,"") if HAS_SOL else (False,"solders")
        if c == "TRX": return (True,"") if HAS_ECDSA else (False,"ecdsa")
        if c in ("LTC","DOGE"): return (True,"") if HAS_ECDSA else (False,"ecdsa")
        try:
            from wallet_core import SUPPORTED_COINS
            cfg = SUPPORTED_COINS.get(c, {})
            if cfg.get("is_evm") or cfg.get("is_token"):
                return (True,"") if HAS_ETH else (False,"eth-account")
        except ImportError: pass
        return (False, "unsupported")

    # ── FEE ESTIMATION ────────────────────────────────────────
    def estimate_fee(self, coin, amount=0, fee_level="medium"):
        """Returns (fee_value: float, display: str)."""
        c = coin.upper()
        try:
            if c == "BTC": return self._fee_btc(fee_level)
            if c in EVM_CHAINS: return self._fee_evm(c, 21000, fee_level)
            if c in ERC20_TOKENS:
                return self._fee_evm(ERC20_TOKENS[c]["chain"], 65000, fee_level)
            if c == "SOL": return (0.000005, "SOL (5000 lamports)")
            if c == "TRX": return (0.0, "TRX (bandwidth)")
            if c == "LTC":
                m = {"low":0.00005,"medium":0.0001,"high":0.0005}
                v = m.get(fee_level, 0.0001) if isinstance(fee_level, str) else float(fee_level)/1e8
                return (v, "LTC")
            if c == "DOGE":
                m = {"low":0.5,"medium":1.0,"high":3.0}
                v = m.get(fee_level, 1.0) if isinstance(fee_level, str) else float(fee_level)
                return (v, "DOGE")
            if c == "BCH": return (0.00001, "BCH")
            try:
                from wallet_core import SUPPORTED_COINS
                cfg = SUPPORTED_COINS.get(c, {})
                if cfg.get("is_evm") or cfg.get("is_token"):
                    rpc = self._rpc_url(c) or cfg.get("rpc","")
                    if rpc:
                        gl = 65000 if cfg.get("is_token") else 21000
                        return self._fee_evm_rpc(rpc, gl, fee_level, c)
            except ImportError: pass
            return (0.0, c)
        except Exception:
            return (0.0, c)

    def _fee_btc(self, level):
        vbytes = 250
        try:
            d = _get(f"{self._rpc_url('BTC')}/api/v1/fees/recommended")
            if d:
                keys = {"low":"economyFee","medium":"halfHourFee","high":"fastestFee"}
                if isinstance(level, str) and level in keys:
                    spvb = d.get(keys[level], 10)
                else:
                    spvb = max(1, int(float(level))) if level else 10
                return (round(spvb * vbytes / 1e8, 8), f"BTC ({int(spvb)} sat/vB)")
        except Exception: pass
        defaults = {"low":3,"medium":10,"high":30}
        s = defaults.get(level, 10) if isinstance(level, str) else 10
        return (round(s * vbytes / 1e8, 8), f"BTC (~{s} sat/vB)")

    def _fee_evm(self, chain, gas_limit, level):
        return self._fee_evm_rpc(self._rpc_url(chain), gas_limit, level, chain)

    def _fee_evm_rpc(self, rpc, gas_limit, level, unit):
        if not rpc: return (0.001, f"{unit} (no RPC)")
        try: gp = int(_rpc(rpc, "eth_gasPrice", []), 16)
        except: return (0.001, f"{unit} (RPC error)")
        if isinstance(level, str):
            mult = FEE_MULT.get(level, 1.0)
        else:
            gp = int(float(level) * 1e9); mult = 1.0
        adj = int(gp * mult)
        fee = adj * gas_limit / 1e18
        gwei = adj / 1e9
        return (round(fee, 8), f"{unit} ({gwei:.2f} Gwei)")

    # ══════════════════════════════════════════════════════════
    #  MAIN SEND
    # ══════════════════════════════════════════════════════════
    def send(self, coin, priv_key_hex, to_addr, amount, fee_level="medium", from_address=""):
        c = coin.upper()
        try:
            valid, err = self.validate_address(c, to_addr)
            if not valid: return TxResult(False, error=f"Invalid address: {err}")
            if c in EVM_CHAINS: return self._send_evm(c, priv_key_hex, to_addr, amount, fee_level)
            if c in ERC20_TOKENS: return self._send_erc20(c, priv_key_hex, to_addr, amount, fee_level)
            if c == "BTC": return self._send_btc(priv_key_hex, from_address, to_addr, amount, fee_level)
            if c == "SOL": return self._send_sol(priv_key_hex, to_addr, amount)
            if c == "TRX": return self._send_trx(priv_key_hex, from_address, to_addr, amount)
            if c in ("LTC","DOGE"): return self._send_utxo_bc(c.lower(), priv_key_hex, from_address, to_addr, amount, fee_level)
            if c == "BCH": return self._send_bch(priv_key_hex, to_addr, amount)
            try:
                from wallet_core import SUPPORTED_COINS
                cfg = SUPPORTED_COINS.get(c, {})
                if cfg.get("is_token") and cfg.get("contract"):
                    return self._send_custom_token(c, cfg, priv_key_hex, to_addr, amount, fee_level)
                if cfg.get("is_evm"):
                    return self._send_custom_evm(c, cfg, priv_key_hex, to_addr, amount, fee_level)
            except ImportError: pass
            return TxResult(False, error=f"Sending {c} not supported")
        except Exception as e:
            return TxResult(False, error=str(e))

    # ── EVM (ETH/BNB/MATIC) ──────────────────────────────────
    def _send_evm(self, coin, pk, to, amount, fee_level):
        if not HAS_ETH: return TxResult(False, error="Missing: pip install eth-account")
        rpc = self._rpc_url(coin)
        chain_id = EVM_CHAINS[coin]["chain_id"]
        acct = EthAccount.from_key(pk)
        nonce = int(_rpc(rpc, "eth_getTransactionCount", [acct.address, "pending"]), 16)
        base_gp = int(_rpc(rpc, "eth_gasPrice", []), 16)
        if isinstance(fee_level, str):
            gp = int(base_gp * FEE_MULT.get(fee_level, 1.0))
        else:
            gp = int(float(fee_level) * 1e9)
        gl = 21000; val = int(amount * 10**18)
        # Try EIP-1559 for ETH
        tx = None; fee_cost = 0
        if coin == "ETH":
            try:
                blk = _rpc(rpc, "eth_getBlockByNumber", ["latest", False])
                bf = int(blk.get("baseFeePerGas","0x0"),16) if blk else 0
                if bf > 0:
                    try: prio = int(_rpc(rpc, "eth_maxPriorityFeePerGas", []), 16)
                    except: prio = 1_500_000_000
                    if isinstance(fee_level, str): prio = int(prio * FEE_MULT.get(fee_level,1.0))
                    mf = bf * 2 + prio
                    tx = {"type":2,"chainId":chain_id,"nonce":nonce,"to":to,"value":val,
                          "gas":gl,"maxFeePerGas":mf,"maxPriorityFeePerGas":prio}
                    fee_cost = gl * mf / 1e18
            except: pass
        if tx is None:
            tx = {"chainId":chain_id,"nonce":nonce,"to":to,"value":val,"gas":gl,"gasPrice":gp}
            fee_cost = gl * gp / 1e18
        signed = acct.sign_transaction(tx)
        try: txh = _rpc(rpc, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
        except Exception as e: return TxResult(False, error=f"Broadcast: {e}")
        if not txh: return TxResult(False, error="Empty hash returned")
        return TxResult(True, tx_hash=txh, fee=fee_cost, explorer_url=self._explorer_url(coin, txh))

    # ── ERC-20 (USDT/USDC) ───────────────────────────────────
    def _send_erc20(self, coin, pk, to, amount, fee_level):
        if not HAS_ETH: return TxResult(False, error="Missing: pip install eth-account")
        tok = ERC20_TOKENS[coin]; ch = tok["chain"]
        rpc = self._rpc_url(ch); cid = EVM_CHAINS.get(ch,{}).get("chain_id",1)
        acct = EthAccount.from_key(pk)
        nonce = int(_rpc(rpc, "eth_getTransactionCount", [acct.address, "pending"]), 16)
        base_gp = int(_rpc(rpc, "eth_gasPrice", []), 16)
        gp = int(base_gp * FEE_MULT.get(fee_level,1.0)) if isinstance(fee_level,str) else int(float(fee_level)*1e9)
        ta = int(amount * (10**tok["decimals"]))
        data = "0xa9059cbb" + to[2:].lower().zfill(64) + hex(ta)[2:].zfill(64)
        gl = 100000
        try:
            est = _rpc(rpc, "eth_estimateGas", [{"from":acct.address,"to":tok["contract"],"data":data}])
            if est: gl = max(int(int(est,16)*1.3), 60000)
        except: pass
        tx = {"chainId":cid,"nonce":nonce,"to":tok["contract"],"value":0,
              "gas":gl,"gasPrice":gp,"data":bytes.fromhex(data[2:])}
        signed = acct.sign_transaction(tx)
        try: txh = _rpc(rpc, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
        except Exception as e: return TxResult(False, error=f"Broadcast: {e}")
        return TxResult(True, tx_hash=txh, fee=gl*gp/1e18, explorer_url=self._explorer_url(coin, txh))

    # ── Custom EVM native ─────────────────────────────────────
    def _send_custom_evm(self, coin, cfg, pk, to, amount, fee_level):
        if not HAS_ETH: return TxResult(False, error="Missing: pip install eth-account")
        rpc = self._rpc_url(coin) or cfg.get("rpc","")
        if not rpc: return TxResult(False, error=f"No RPC for {coin}")
        acct = EthAccount.from_key(pk)
        nonce = int(_rpc(rpc, "eth_getTransactionCount", [acct.address, "pending"]), 16)
        base_gp = int(_rpc(rpc, "eth_gasPrice", []), 16)
        gp = int(base_gp * FEE_MULT.get(fee_level,1.0)) if isinstance(fee_level,str) else int(float(fee_level)*1e9)
        dec = cfg.get("decimals",18)
        try: cid = int(_rpc(rpc, "eth_chainId", []), 16)
        except: cid = 1
        tx = {"chainId":cid,"nonce":nonce,"to":to,"value":int(amount*(10**dec)),"gas":21000,"gasPrice":gp}
        signed = acct.sign_transaction(tx)
        try: txh = _rpc(rpc, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
        except Exception as e: return TxResult(False, error=f"Broadcast: {e}")
        exp = cfg.get("explorer",""); url = exp.replace("{}",txh) if exp else ""
        return TxResult(True, tx_hash=txh, fee=21000*gp/1e18, explorer_url=url)

    # ── Custom ERC-20 token ───────────────────────────────────
    def _send_custom_token(self, coin, cfg, pk, to, amount, fee_level):
        if not HAS_ETH: return TxResult(False, error="Missing: pip install eth-account")
        rpc = self._rpc_url(coin) or cfg.get("rpc","") or self._rpc_url("ETH")
        if not rpc: return TxResult(False, error=f"No RPC for {coin}")
        acct = EthAccount.from_key(pk)
        nonce = int(_rpc(rpc, "eth_getTransactionCount", [acct.address, "pending"]), 16)
        base_gp = int(_rpc(rpc, "eth_gasPrice", []), 16)
        gp = int(base_gp * FEE_MULT.get(fee_level,1.0)) if isinstance(fee_level,str) else int(float(fee_level)*1e9)
        dec = cfg.get("decimals",18); contract = cfg.get("contract","")
        ta = int(amount * (10**dec))
        data = "0xa9059cbb" + to[2:].lower().zfill(64) + hex(ta)[2:].zfill(64)
        gl = 100000
        try:
            est = _rpc(rpc, "eth_estimateGas", [{"from":acct.address,"to":contract,"data":data}])
            if est: gl = max(int(int(est,16)*1.3), 60000)
        except: pass
        try: cid = int(_rpc(rpc, "eth_chainId", []), 16)
        except: cid = 1
        tx = {"chainId":cid,"nonce":nonce,"to":contract,"value":0,"gas":gl,"gasPrice":gp,"data":bytes.fromhex(data[2:])}
        signed = acct.sign_transaction(tx)
        try: txh = _rpc(rpc, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
        except Exception as e: return TxResult(False, error=f"Broadcast: {e}")
        return TxResult(True, tx_hash=txh, fee=gl*gp/1e18)

    # ── BTC ───────────────────────────────────────────────────
    def _send_btc(self, pk_hex, from_addr, to, amount, fee_level):
        if not HAS_BIT: return TxResult(False, error="Missing: pip install bit")
        if from_addr and from_addr.startswith("bc1p"):
            return TxResult(False, error="Taproot not supported by 'bit'. Use BIP84 (Native SegWit).")
        key = BtcKey.from_hex(pk_hex)
        spb = 10
        try:
            d = _get(f"{self._rpc_url('BTC')}/api/v1/fees/recommended")
            if d:
                keys = {"low":"economyFee","medium":"halfHourFee","high":"fastestFee"}
                if isinstance(fee_level, str) and fee_level in keys:
                    spb = d.get(keys[fee_level], 10)
                elif fee_level not in ("low","medium","high"):
                    spb = max(1, int(float(fee_level)))
        except:
            spb = {"low":3,"medium":10,"high":30}.get(fee_level, 10) if isinstance(fee_level, str) else 10
        sats = int(round(amount * 1e8))
        try:
            txh = key.send([(to, sats, "satoshi")], fee=spb, absolute_fee=False)
        except Exception as e:
            err = str(e)
            if "insufficient" in err.lower(): return TxResult(False, error="Insufficient BTC (including fee)")
            return TxResult(False, error=f"BTC: {err}")
        return TxResult(True, tx_hash=txh, fee=spb*250/1e8, explorer_url=self._explorer_url("BTC", txh))

    # ── BCH ───────────────────────────────────────────────────
    def _send_bch(self, pk_hex, to, amount):
        if not HAS_BCH: return TxResult(False, error="Missing: pip install bitcash")
        key = BchKey.from_hex(pk_hex)
        sats = int(round(amount * 1e8))
        try: txh = key.send([(to, sats, "satoshi")])
        except Exception as e: return TxResult(False, error=f"BCH: {e}")
        return TxResult(True, tx_hash=txh, fee=0.00001, explorer_url=self._explorer_url("BCH", txh))

    # ── LTC / DOGE via BlockCypher ────────────────────────────
    def _send_utxo_bc(self, network, pk_hex, from_addr, to, amount, fee_level):
        if not HAS_ECDSA: return TxResult(False, error="Missing: pip install ecdsa")
        if not from_addr: return TxResult(False, error=f"From address needed for {network.upper()}")
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(pk_hex), curve=ecdsa.SECP256k1)
        vk = sk.get_verifying_key(); raw = vk.to_string()
        x, y = raw[:32], raw[32:]
        prefix = b'\x02' if y[-1] % 2 == 0 else b'\x03'
        pubc = (prefix + x).hex()
        sats = int(round(amount * 1e8))
        chain = {"ltc":"ltc/main","doge":"doge/main"}.get(network, f"{network}/main")
        api = f"https://api.blockcypher.com/v1/{chain}"
        pref = {"low":"low","medium":"medium","high":"high"}.get(fee_level,"medium") if isinstance(fee_level,str) else "medium"
        new_tx = {"inputs":[{"addresses":[from_addr]}],"outputs":[{"addresses":[to],"value":sats}],"preference":pref}
        resp = _post(f"{api}/txs/new", new_tx)
        if resp is None: return TxResult(False, error="BlockCypher: no response")
        if "errors" in resp:
            e = resp["errors"]
            msg = e[0].get("error",str(e[0])) if isinstance(e,list) and e else str(e)
            return TxResult(False, error=f"BlockCypher: {msg}")
        tosign = resp.get("tosign", [])
        if not tosign: return TxResult(False, error="BlockCypher: nothing to sign (no UTXOs?)")
        sigs = []
        for ts in tosign:
            sig = sk.sign_digest(bytes.fromhex(ts), sigencode=ecdsa.util.sigencode_der)
            sigs.append(sig.hex())
        resp["signatures"] = sigs
        resp["pubkeys"] = [pubc] * len(sigs)
        result = _post(f"{api}/txs/send", resp)
        if result is None: return TxResult(False, error="BlockCypher: broadcast failed")
        if "errors" in result:
            e = result["errors"]
            msg = e[0].get("error",str(e[0])) if isinstance(e,list) and e else str(e)
            return TxResult(False, error=f"BlockCypher: {msg}")
        txh = result.get("tx",{}).get("hash","")
        fee = result.get("tx",{}).get("fees",0) / 1e8
        return TxResult(True, tx_hash=txh, fee=fee, explorer_url=self._explorer_url(network.upper(), txh))

    # ── SOL ───────────────────────────────────────────────────
    def _send_sol(self, pk_hex, to, amount):
        if not HAS_SOL: return TxResult(False, error="Missing: pip install solders")
        rpc = self._rpc_url("SOL"); kb = bytes.fromhex(pk_hex)
        try:
            if len(kb) == 64: kp = SolKeypair.from_bytes(kb)
            elif len(kb) == 32:
                try: kp = SolKeypair.from_seed(kb)
                except (AttributeError, TypeError):
                    try:
                        from nacl.signing import SigningKey
                        sk = SigningKey(kb); kp = SolKeypair.from_bytes(bytes(sk) + bytes(sk.verify_key))
                    except ImportError: return TxResult(False, error="Need: pip install pynacl")
            else: return TxResult(False, error=f"Invalid SOL key length: {len(kb)}")
        except Exception as e: return TxResult(False, error=f"SOL keypair: {e}")
        lam = int(amount * 1e9); to_pk = SolPubkey.from_string(to)
        bhr = _post(rpc, {"jsonrpc":"2.0","id":1,"method":"getLatestBlockhash",
                          "params":[{"commitment":"finalized"}]})
        if not bhr or "result" not in bhr:
            err = bhr.get("error",{}).get("message","") if bhr else ""
            return TxResult(False, error=f"SOL blockhash failed. {err}")
        bh = SolHash.from_string(bhr["result"]["value"]["blockhash"])
        ix = sol_transfer(TransferParams(from_pubkey=kp.pubkey(), to_pubkey=to_pk, lamports=lam))
        msg = SolMsg.new_with_blockhash([ix], kp.pubkey(), bh)
        tx = SolTx.new_unsigned(msg); tx.sign([kp], bh)
        enc = base64.b64encode(bytes(tx)).decode()
        sr = _post(rpc, {"jsonrpc":"2.0","id":1,"method":"sendTransaction",
                         "params":[enc,{"encoding":"base64","preflightCommitment":"confirmed","skipPreflight":False}]})
        if not sr: return TxResult(False, error="SOL: no RPC response")
        if "error" in sr:
            e = sr["error"]; m = e.get("message",str(e)) if isinstance(e,dict) else str(e)
            return TxResult(False, error=f"SOL: {m}")
        txh = sr.get("result","")
        if not txh: return TxResult(False, error="SOL: empty hash")
        return TxResult(True, tx_hash=txh, fee=0.000005, explorer_url=self._explorer_url("SOL", txh))

    # ── TRX (tronpy first, ecdsa fallback) ────────────────────
    def _send_trx(self, pk_hex, from_addr, to, amount):
        # Method 1: tronpy
        try:
            from tronpy import Tron
            from tronpy.keys import PrivateKey as TronPK
            api = self._rpc_url("TRX")
            if "trongrid.io" in api or not api: client = Tron()
            else:
                from tronpy.providers import HTTPProvider
                client = Tron(provider=HTTPProvider(api))
            priv = TronPK(bytes.fromhex(pk_hex))
            sun = int(amount * 1e6)
            fa = from_addr or priv.public_key.to_base58check_address()
            txn = client.trx.transfer(fa, to, sun).memo("").build().sign(priv)
            result = txn.broadcast()
            tx_id = result.get("txid","") or result.get("id","")
            if tx_id: return TxResult(True, tx_hash=tx_id, explorer_url=self._explorer_url("TRX", tx_id))
        except ImportError: pass
        except Exception as e:
            err = str(e).lower()
            if "bandwidth" in err or "energy" in err or "balance" in err:
                return TxResult(False, error=f"TRX: {e}")

        # Method 2: ecdsa + TronGrid REST
        if not HAS_ECDSA: return TxResult(False, error="Missing: pip install tronpy OR ecdsa")
        api = self._rpc_url("TRX") or "https://api.trongrid.io"
        sun = int(amount * 1e6)
        if not from_addr: return TxResult(False, error="TRX: from_address required")
        cr = _post(f"{api}/wallet/createtransaction",
                   {"owner_address":from_addr,"to_address":to,"amount":sun,"visible":True})
        if not cr: return TxResult(False, error="TRX: TronGrid not responding")
        if "Error" in cr: return TxResult(False, error=f"TRX: {cr['Error']}")
        if "txID" not in cr: return TxResult(False, error=f"TRX: bad response: {str(cr)[:100]}")
        tx_id = cr["txID"]
        # Sign txID bytes directly (txID = hex(sha256(raw_data)))
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(pk_hex), curve=ecdsa.SECP256k1)
        sig_raw = sk.sign_digest(bytes.fromhex(tx_id), sigencode=ecdsa.util.sigencode_string)
        r_b, s_b = sig_raw[:32], sig_raw[32:]
        # Find recovery byte
        vk_bytes = sk.get_verifying_key().to_string()
        v_found = 0
        for v_try in [0, 1]:
            try:
                recs = ecdsa.VerifyingKey.from_public_key_recovery_with_digest(
                    sig_raw, bytes.fromhex(tx_id), ecdsa.SECP256k1, hashfunc=hashlib.sha256)
                if len(recs) > v_try and recs[v_try].to_string() == vk_bytes:
                    v_found = v_try; break
            except: continue
        sig_hex = r_b.hex() + s_b.hex() + format(v_found, "02x")
        cr["signature"] = [sig_hex]
        bc = _post(f"{api}/wallet/broadcasttransaction", cr)
        if bc and bc.get("result") is True:
            return TxResult(True, tx_hash=tx_id, explorer_url=self._explorer_url("TRX", tx_id))
        # Try other v
        sig_hex2 = r_b.hex() + s_b.hex() + format(1-v_found, "02x")
        cr["signature"] = [sig_hex2]
        bc2 = _post(f"{api}/wallet/broadcasttransaction", cr)
        if bc2 and bc2.get("result") is True:
            return TxResult(True, tx_hash=tx_id, explorer_url=self._explorer_url("TRX", tx_id))
        msg = ""
        for r in [bc, bc2]:
            if r and r.get("message"):
                try: msg = bytes.fromhex(r["message"]).decode()
                except: msg = r["message"]
                break
        code = bc.get("code","") if bc else ""
        return TxResult(False, error=f"TRX broadcast: {msg or code or 'rejected'}")
