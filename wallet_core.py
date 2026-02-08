"""
Nexus Wallet Core v3.1
Multi-wallet HD engine, 11+ coins, custom RPC/tokens, i18n ready
"""

import os, json, hashlib, base64, time, shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bip_utils import (
    Bip39MnemonicGenerator, Bip39SeedGenerator, Bip39WordsNum,
    Bip39MnemonicValidator,
    Bip44, Bip44Coins, Bip44Changes,
    Bip49, Bip49Coins,
    Bip84, Bip84Coins,
)
try:
    from bip_utils import Bip86, Bip86Coins
    HAS_86 = True
except ImportError:
    HAS_86 = False; Bip86 = Bip86Coins = None

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ═══════════════════════════════════════════════════════════════
# i18n SYSTEM
# ═══════════════════════════════════════════════════════════════

STRINGS = {
    "en": {
        "app_name": "Nexus Wallet",
        "app_subtitle": "Multi-Chain · HD · Open Source",
        "create_wallet": "Create New Wallet",
        "import_wallet": "Import Seed Phrase",
        "restore_backup": "Restore Backup",
        "welcome_back": "Welcome Back",
        "unlock": "Unlock",
        "password": "Password",
        "confirm_password": "Confirm Password",
        "wallet_name": "Wallet Name",
        "min_8_chars": "Minimum 8 characters",
        "generate_wallet": "Generate Wallet →",
        "import_btn": "Import →",
        "restore_btn": "Restore →",
        "back": "← Back",
        "seed_strength": "Seed",
        "words_12": "12 words",
        "words_24": "24 words",
        "backup_warning": "⚠  BACKUP YOUR RECOVERY PHRASE",
        "backup_desc": "Write these words down and store them safely. This is the ONLY way to recover your wallet.",
        "copy_phrase": "Copy Phrase",
        "confirm_backup": "I have safely saved my recovery phrase",
        "open_wallet": "Open Wallet →",
        "confirm_backup_err": "Please confirm backup first",
        "dashboard": "Dashboard",
        "portfolio": "Portfolio",
        "derivation": "Derivation",
        "send": "Send",
        "receive": "Receive",
        "history": "History",
        "contacts": "Contacts",
        "security": "Security",
        "settings": "Settings",
        "total_balance": "TOTAL BALANCE",
        "assets_tracked": "assets tracked",
        "assets": "ASSETS",
        "refresh": "↻ Refresh",
        "quick_send": "↗  Send",
        "quick_recv": "↙  Receive",
        "quick_derive": "⑃  Derive",
        "balance": "Balance",
        "available": "Available",
        "recipient": "Recipient Address",
        "amount": "Amount",
        "verify_addr_warn": "⚠  Verify address. Transactions are irreversible.",
        "review_tx": "Review Transaction",
        "confirm_tx": "Confirm Transaction",
        "coin": "Coin",
        "to": "To",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "network_fee": "Network Fee",
        "fee_speed": "Fee Speed",
        "fee_low": "🐢 Low (Slow)",
        "fee_medium": "⚡ Medium",
        "fee_high": "🚀 High (Fast)",
        "fee_custom": "⚙ Custom",
        "invalid_address": "Invalid {coin} address format",
        "tx_real_warning": "⚠ Real transaction — cannot be reversed!",
        "signing_tx": "Signing and broadcasting...",
        "sending": "Sending...",
        "tx_success": "✓ TX sent!",
        "tx_hash_label": "TX Hash",
        "view_explorer": "View on Explorer",
        "copy_hash": "Copy Hash",
        "missing_lib": "Missing library",
        "wrong_pw": "Wrong password",
        "enter_pw_send": "Enter wallet password to sign",
        "insufficient_bal": "Insufficient balance",
        "format": "Format",
        "copy_address": "Copy Address",
        "explorer": "Explorer",
        "only_send_to": "Only send {name} ({sym}) to this address",
        "shared_with": "Shared with {parent}",
        "derive_title": "Derivation Paths",
        "derive_subtitle": "Derive custom addresses for coins with own keys",
        "derive_new": "Derive Custom Address",
        "account": "Account",
        "index": "Index",
        "preview": "Preview",
        "add": "+ Add",
        "remove": "Remove",
        "custom_addresses": "CUSTOM ADDRESSES",
        "no_custom": "No custom addresses yet",
        "no_tx": "No transactions yet",
        "sent": "↗ Sent",
        "received": "↙ Recv",
        "add_contact": "Add Contact",
        "no_contacts": "No contacts yet",
        "name": "Name",
        "address": "Address",
        "save": "Save",
        "recovery_phrase": "Recovery Phrase",
        "pw_required": "Password required to view",
        "show_phrase": "🔓 Show Recovery Phrase",
        "private_keys": "Private Keys",
        "never_share": "Never share your private keys!",
        "show_key": "🔓 Show Private Key",
        "change_password": "Change Password",
        "current_pw": "Current Password",
        "new_pw": "New Password (8+)",
        "confirm_new_pw": "Confirm New",
        "change_btn": "Change",
        "pw_changed": "✓ Password changed",
        "wrong_pw": "Wrong password",
        "backup_title": "Encrypted Backup",
        "export_backup": "📦 Export Encrypted Backup",
        "backup_saved": "Backup saved!",
        "active_formats": "Active Formats",
        "display": "Display",
        "currency": "Currency",
        "auto_lock": "Auto-Lock",
        "timeout": "Timeout",
        "sec_never": "sec (0=never)",
        "wallets": "Wallets",
        "active": "Active",
        "delete": "Delete",
        "new_wallet": "+ New Wallet",
        "about": "About",
        "language": "Language",
        "custom_rpc": "Custom RPC / Explorer",
        "rpc_url": "RPC URL",
        "explorer_url": "Explorer URL",
        "save_rpc": "Save",
        "reset_rpc": "Reset",
        "custom_tokens": "Custom Tokens",
        "add_token": "+ Add Custom Token",
        "token_symbol": "Symbol (e.g. LINK)",
        "token_name": "Name (e.g. Chainlink)",
        "token_network": "Network",
        "token_contract": "Contract Address (for ERC-20)",
        "token_decimals": "Decimals",
        "token_explorer": "Explorer URL (use {} for address)",
        "token_rpc": "RPC URL (optional)",
        "token_color": "Color (#hex)",
        "token_icon": "Icon (1-2 chars)",
        "add_token_btn": "Add Token",
        "remove_token": "Remove",
        "evm_ethereum": "EVM (Ethereum address)",
        "own_derivation": "Own Derivation",
        "copied": "Copied!",
        "enter_pw": "Enter password",
        "verify_identity": "Verify Identity",
        "lock": "🔒 Lock",
        "switch_wallet": "⇄ Switch",
        "passwords_dont_match": "Passwords don't match",
        "pw_too_short": "Password must be 8+ characters",
        "invalid_phrase": "Invalid phrase",
        "generating": "Generating...",
        "importing": "Importing...",
        "unlocking": "Unlocking...",
    },
}

_current_lang = "en"

def set_lang(lang):
    global _current_lang
    _current_lang = lang

def L(key, **kwargs):
    s = STRINGS.get(_current_lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))
    if kwargs:
        try: return s.format(**kwargs)
        except: return s
    return s

def get_available_langs():
    return list(STRINGS.keys())


# ═══════════════════════════════════════════════════════════════
# COIN DEFINITIONS
# ═══════════════════════════════════════════════════════════════

ADDRESS_FORMATS = {
    "BIP44": {"name": "Legacy", "purpose": 44},
    "BIP49": {"name": "Nested SegWit", "purpose": 49},
    "BIP84": {"name": "Native SegWit", "purpose": 84},
    "BIP86": {"name": "Taproot", "purpose": 86},
    "SINGLE": {"name": "Standard", "purpose": 44},
}

def _btc_fmts():
    f = {"BIP44": {"bip": Bip44, "coin": Bip44Coins.BITCOIN, "path_coin": 0},
         "BIP84": {"bip": Bip84, "coin": Bip84Coins.BITCOIN, "path_coin": 0}}
    if HAS_86:
        f["BIP86"] = {"bip": Bip86, "coin": Bip86Coins.BITCOIN, "path_coin": 0}
    return f

_OWN_COINS = {
    "BTC": {"name":"Bitcoin","icon":"₿","color":"#F7931A","decimals":8,
            "formats":_btc_fmts(),"default_format":"BIP84",
            "explorer":"https://mempool.space/address/{}",
            "coingecko":"bitcoin"},
    "ETH": {"name":"Ethereum","icon":"Ξ","color":"#627EEA","decimals":18,
            "formats":{"SINGLE":{"bip":Bip44,"coin":Bip44Coins.ETHEREUM,"path_coin":60}},
            "default_format":"SINGLE","format_label":"",
            "explorer":"https://etherscan.io/address/{}",
            "coingecko":"ethereum"},
    "LTC": {"name":"Litecoin","icon":"Ł","color":"#345D9D","decimals":8,
            "formats":{"BIP44":{"bip":Bip44,"coin":Bip44Coins.LITECOIN,"path_coin":2},
                       "BIP49":{"bip":Bip49,"coin":Bip49Coins.LITECOIN,"path_coin":2},
                       "BIP84":{"bip":Bip84,"coin":Bip84Coins.LITECOIN,"path_coin":2}},
            "default_format":"BIP84",
            "explorer":"https://blockchair.com/litecoin/address/{}",
            "coingecko":"litecoin"},
    "DOGE":{"name":"Dogecoin","icon":"Ð","color":"#C2A633","decimals":8,
            "formats":{"BIP44":{"bip":Bip44,"coin":Bip44Coins.DOGECOIN,"path_coin":3}},
            "default_format":"BIP44",
            "explorer":"https://blockchair.com/dogecoin/address/{}",
            "coingecko":"dogecoin"},
    "BCH": {"name":"Bitcoin Cash","icon":"Ƀ","color":"#8DC351","decimals":8,
            "formats":{"BIP44":{"bip":Bip44,"coin":Bip44Coins.BITCOIN_CASH,"path_coin":145}},
            "default_format":"BIP44",
            "explorer":"https://blockchair.com/bitcoin-cash/address/{}",
            "coingecko":"bitcoin-cash"},
    "TRX": {"name":"Tron","icon":"◆","color":"#FF0013","decimals":6,
            "formats":{"SINGLE":{"bip":Bip44,"coin":Bip44Coins.TRON,"path_coin":195}},
            "default_format":"SINGLE","format_label":"",
            "explorer":"https://tronscan.org/#/address/{}",
            "coingecko":"tron"},
    "SOL": {"name":"Solana","icon":"◎","color":"#9945FF","decimals":9,
            "formats":{"SINGLE":{"bip":Bip44,"coin":Bip44Coins.SOLANA,"path_coin":501}},
            "default_format":"SINGLE","format_label":"",
            "explorer":"https://solscan.io/account/{}",
            "coingecko":"solana"},
}

_EVM_COINS = {
    "BNB":  {"name":"BNB Chain","icon":"◆","color":"#F3BA2F","decimals":18,
             "explorer":"https://bscscan.com/address/{}",
             "rpc":"https://bsc-dataseed1.binance.org",
             "coingecko":"binancecoin"},
    "MATIC":{"name":"Polygon","icon":"⬡","color":"#8247E5","decimals":18,
             "explorer":"https://polygonscan.com/address/{}",
             "rpc":"https://polygon-rpc.com",
             "coingecko":"matic-network"},
}

_ERC20_TOKENS = {
    "USDT": {"name":"Tether","icon":"₮","color":"#26A17B","decimals":6,
             "contract":"0xdAC17F958D2ee523a2206206994597C13D831ec7",
             "explorer":"https://etherscan.io/token/0xdAC17F958D2ee523a2206206994597C13D831ec7?a={}",
             "coingecko":"tether"},
    "USDC": {"name":"USD Coin","icon":"$","color":"#2775CA","decimals":6,
             "contract":"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
             "explorer":"https://etherscan.io/token/0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48?a={}",
             "coingecko":"usd-coin"},
}

# Master registry
SUPPORTED_COINS = {}
for sym, cfg in _OWN_COINS.items():
    SUPPORTED_COINS[sym] = {**cfg, "symbol": sym, "has_own_key": True}
for sym, cfg in _EVM_COINS.items():
    SUPPORTED_COINS[sym] = {**cfg, "symbol": sym, "has_own_key": False,
                             "shares_address_with": "ETH", "is_evm": True,
                             "formats": {}, "default_format": "SINGLE", "format_label": ""}
for sym, cfg in _ERC20_TOKENS.items():
    SUPPORTED_COINS[sym] = {**cfg, "symbol": sym, "has_own_key": False,
                             "shares_address_with": "ETH", "is_token": True,
                             "formats": {}, "default_format": "SINGLE", "format_label": ""}

COIN_ORDER = ["BTC","ETH","BNB","MATIC","SOL","TRX","LTC","DOGE","BCH","USDT","USDC"]


def get_coin_order(config=None):
    """Return coin order including custom coins."""
    order = list(COIN_ORDER)
    if config:
        for sym in config.get("custom_coins_order", []):
            if sym not in order:
                order.append(sym)
    return order

def get_coin_explorer(sym, config=None):
    """Get explorer URL, with custom override."""
    if config:
        custom = config.get("custom_rpc", {}).get(sym, {})
        if custom.get("explorer"):
            return custom["explorer"]
    cfg = SUPPORTED_COINS.get(sym, {})
    return cfg.get("explorer", "")

def get_coin_rpc(sym, config=None):
    """Get RPC URL, with custom override."""
    if config:
        custom = config.get("custom_rpc", {}).get(sym, {})
        if custom.get("rpc"):
            return custom["rpc"]
    cfg = SUPPORTED_COINS.get(sym, {})
    return cfg.get("rpc", "")


# ═══════════════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════════════

class WalletSecurity:
    SALT_SIZE = 16; ITERATIONS = 480000

    @staticmethod
    def derive_key(pw, salt):
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=WalletSecurity.ITERATIONS)
        return base64.urlsafe_b64encode(kdf.derive(pw.encode()))

    @staticmethod
    def encrypt(data, pw):
        s = os.urandom(WalletSecurity.SALT_SIZE)
        return base64.b64encode(s + Fernet(WalletSecurity.derive_key(pw, s)).encrypt(data.encode())).decode()

    @staticmethod
    def decrypt(enc, pw):
        try:
            p = base64.b64decode(enc.encode())
            return Fernet(WalletSecurity.derive_key(pw, p[:16])).decrypt(p[16:]).decode()
        except: return None

    @staticmethod
    def hash_password(pw):
        s = os.urandom(32)
        return base64.b64encode(s + hashlib.pbkdf2_hmac('sha256', pw.encode(), s, 100000)).decode()

    @staticmethod
    def verify_password(pw, stored):
        d = base64.b64decode(stored.encode())
        return hashlib.pbkdf2_hmac('sha256', pw.encode(), d[:32], 100000) == d[32:]


# ═══════════════════════════════════════════════════════════════
# HD ENGINE
# ═══════════════════════════════════════════════════════════════

class HDWalletEngine:
    @staticmethod
    def generate_mnemonic(strength=256):
        wm = {128:Bip39WordsNum.WORDS_NUM_12, 256:Bip39WordsNum.WORDS_NUM_24}
        return Bip39MnemonicGenerator().FromWordsNumber(wm.get(strength, Bip39WordsNum.WORDS_NUM_24)).ToStr()

    @staticmethod
    def validate_mnemonic(mn):
        try: Bip39MnemonicValidator(mn).Validate(); return True
        except: return False

    @staticmethod
    def derive_address(mn, coin, fmt=None, account=0, index=0):
        cfg = _OWN_COINS.get(coin)
        if not cfg: raise ValueError(f"No derivation for {coin}")
        if fmt is None: fmt = cfg["default_format"]
        fc = cfg["formats"][fmt]
        seed = Bip39SeedGenerator(mn).Generate()
        addr = fc["bip"].FromSeed(seed, fc["coin"]).Purpose().Coin().Account(account).Change(Bip44Changes.CHAIN_EXT).AddressIndex(index)
        purpose = ADDRESS_FORMATS.get(fmt, {}).get("purpose", 44)
        return {
            "address": addr.PublicKey().ToAddress(),
            "public_key": addr.PublicKey().RawCompressed().ToHex(),
            "private_key": addr.PrivateKey().Raw().ToHex(),
            "format": fmt,
            "path": f"m/{purpose}'/{fc['path_coin']}'/{account}'/0/{index}",
            "account": account, "index": index,
        }

    @staticmethod
    def derive_all_coins(mn, account=0, index=0):
        results = {}
        for sym in _OWN_COINS:
            results[sym] = {}
            for fmt in _OWN_COINS[sym]["formats"]:
                try: results[sym][fmt] = HDWalletEngine.derive_address(mn, sym, fmt, account, index)
                except Exception as e: results[sym][fmt] = {"error": str(e), "address": "Error"}
        eth = results.get("ETH", {}).get("SINGLE", {})
        for sym in list(_EVM_COINS.keys()) + list(_ERC20_TOKENS.keys()):
            results[sym] = {"SINGLE": {
                "address": eth.get("address", ""),
                "public_key": eth.get("public_key", ""),
                "private_key": eth.get("private_key", ""),
                "format": "SINGLE", "path": eth.get("path", "m/44'/60'/0'/0/0"),
                "account": account, "index": index, "shared_from": "ETH",
            }}
        return results


# ═══════════════════════════════════════════════════════════════
# STORAGE
# ═══════════════════════════════════════════════════════════════

class WalletStorage:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".nexus_wallet"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "wallets_index.json"
        self.config_file = self.base_dir / "config.json"
        self.tx_file = self.base_dir / "tx_history.json"
        self.contacts_file = self.base_dir / "contacts.json"

    def _wf(self, wid): return self.base_dir / f"wallet_{wid}.dat"

    def load_index(self):
        if self.index_file.exists():
            with open(self.index_file) as f: return json.load(f)
        return []

    def save_index(self, idx):
        with open(self.index_file, 'w') as f: json.dump(idx, f, indent=2)

    def wallet_count(self): return len(self.load_index())
    def has_wallets(self): return self.wallet_count() > 0

    def save_wallet(self, wid, wdata, pw):
        p = {"version":3, "encrypted_data": WalletSecurity.encrypt(json.dumps(wdata), pw),
             "password_hash": WalletSecurity.hash_password(pw),
             "created_at": wdata.get("created_at", time.time()), "updated_at": time.time()}
        with open(self._wf(wid), 'w') as f: json.dump(p, f, indent=2)

    def load_wallet(self, wid, pw):
        wf = self._wf(wid)
        if not wf.exists(): return None
        with open(wf) as f: p = json.load(f)
        if not WalletSecurity.verify_password(pw, p["password_hash"]): return None
        d = WalletSecurity.decrypt(p["encrypted_data"], pw)
        return json.loads(d) if d else None

    def verify_wallet_password(self, wid, pw):
        wf = self._wf(wid)
        if not wf.exists(): return False
        with open(wf) as f: p = json.load(f)
        return WalletSecurity.verify_password(pw, p["password_hash"])

    def delete_wallet(self, wid):
        wf = self._wf(wid)
        if wf.exists(): wf.unlink()
        self.save_index([w for w in self.load_index() if w["id"] != wid])

    def export_backup(self, wid, pw, path):
        try:
            wd = self.load_wallet(wid, pw)
            if not wd: return False
            with open(path, 'w') as f:
                json.dump({"version":3,"type":"nexus_wallet_backup",
                           "data":WalletSecurity.encrypt(json.dumps(wd), pw),
                           "timestamp":time.time()}, f, indent=2)
            return True
        except: return False

    def import_backup(self, path, pw):
        try:
            with open(path) as f: p = json.load(f)
            if p.get("type") != "nexus_wallet_backup": return None
            d = WalletSecurity.decrypt(p["data"], pw)
            return json.loads(d) if d else None
        except: return None

    def save_config(self, cfg):
        with open(self.config_file, 'w') as f: json.dump(cfg, f, indent=2)

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file) as f: return json.load(f)
        return {"currency":"USD","auto_lock":300,"active_wallet":None,"language":"en",
                "selected_formats":{s:c.get("default_format","SINGLE") for s,c in SUPPORTED_COINS.items() if c.get("has_own_key")},
                "custom_rpc":{},"custom_coins":{},"custom_coins_order":[]}

    def save_contacts(self, c):
        with open(self.contacts_file, 'w') as f: json.dump(c, f, indent=2)
    def load_contacts(self):
        if self.contacts_file.exists():
            with open(self.contacts_file) as f: return json.load(f)
        return []
    def save_tx(self, tx):
        with open(self.tx_file, 'w') as f: json.dump(tx, f, indent=2)
    def load_tx(self):
        if self.tx_file.exists():
            with open(self.tx_file) as f: return json.load(f)
        return {}


# ═══════════════════════════════════════════════════════════════
# WALLET MANAGER
# ═══════════════════════════════════════════════════════════════

class WalletManager:
    def __init__(self, base_dir=None):
        self.storage = WalletStorage(base_dir)
        self.config = self.storage.load_config()
        self.contacts = self.storage.load_contacts()
        self.tx_history = self.storage.load_tx()
        self.wallet_data = None
        self.active_wallet_id = None
        self.active_password = None
        self.is_locked = True
        self.last_activity = time.time()
        # Load custom coins into registry
        self._load_custom_coins()

    def _load_custom_coins(self):
        for sym, cfg in self.config.get("custom_coins", {}).items():
            if sym not in SUPPORTED_COINS:
                SUPPORTED_COINS[sym] = {
                    "symbol": sym, "name": cfg.get("name", sym),
                    "icon": cfg.get("icon", "?"), "color": cfg.get("color", "#888888"),
                    "decimals": cfg.get("decimals", 18),
                    "explorer": cfg.get("explorer", ""),
                    "has_own_key": False,
                    "shares_address_with": "ETH",
                    "is_evm": cfg.get("type") == "evm",
                    "is_token": cfg.get("type") == "erc20",
                    "contract": cfg.get("contract", ""),
                    "rpc": cfg.get("rpc", ""),
                    "coingecko": cfg.get("coingecko", ""),
                    "formats": {}, "default_format": "SINGLE", "format_label": "",
                    "is_custom": True,
                }

    def get_wallet_list(self): return self.storage.load_index()

    def create_wallet(self, pw, mnemonic=None, name="My Wallet", strength=256):
        if mnemonic is None:
            mnemonic = HDWalletEngine.generate_mnemonic(strength)
        elif not HDWalletEngine.validate_mnemonic(mnemonic):
            return False, "Invalid mnemonic", ""
        wid = hashlib.md5(f"{mnemonic}{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()[:12]
        addresses = HDWalletEngine.derive_all_coins(mnemonic)
        # Also derive for custom EVM coins
        eth_addr = addresses.get("ETH", {}).get("SINGLE", {})
        for sym in self.config.get("custom_coins_order", []):
            if sym not in addresses:
                addresses[sym] = {"SINGLE": {
                    "address": eth_addr.get("address", ""),
                    "public_key": eth_addr.get("public_key", ""),
                    "private_key": eth_addr.get("private_key", ""),
                    "format": "SINGLE", "path": eth_addr.get("path", "m/44'/60'/0'/0/0"),
                    "shared_from": "ETH",
                }}
        wdata = {"name":name, "mnemonic":mnemonic, "addresses":addresses,
                 "created_at":time.time(), "custom_paths":{}}
        self.storage.save_wallet(wid, wdata, pw)
        idx = self.storage.load_index()
        idx.append({"id":wid, "name":name, "created_at":time.time()})
        self.storage.save_index(idx)
        self.wallet_data = wdata; self.active_wallet_id = wid; self.active_password = pw
        self.config["active_wallet"] = wid; self.storage.save_config(self.config)
        self.is_locked = False; self.last_activity = time.time()
        return True, mnemonic, wid

    def unlock_wallet(self, wid, pw):
        wd = self.storage.load_wallet(wid, pw)
        if wd:
            self.wallet_data = wd; self.active_wallet_id = wid; self.active_password = pw
            self.config["active_wallet"] = wid; self.storage.save_config(self.config)
            self.is_locked = False; self.last_activity = time.time()
            return True
        return False

    def lock_wallet(self):
        self.wallet_data = None; self.active_password = None; self.is_locked = True

    def verify_password(self, pw):
        return self.storage.verify_wallet_password(self.active_wallet_id, pw) if self.active_wallet_id else False

    def _save(self):
        if self.wallet_data and self.active_wallet_id and self.active_password:
            self.storage.save_wallet(self.active_wallet_id, self.wallet_data, self.active_password)

    def derive_custom_address(self, coin, fmt, account, index):
        if not self.wallet_data or coin not in _OWN_COINS: return None
        try: return HDWalletEngine.derive_address(self.wallet_data["mnemonic"], coin, fmt, account, index)
        except: return None

    def add_derived_address(self, coin, fmt, account, index):
        ad = self.derive_custom_address(coin, fmt, account, index)
        if not ad: return None
        cl = self.wallet_data.setdefault("custom_paths", {}).setdefault(coin, [])
        for e in cl:
            if e.get("path") == ad.get("path"): return e
        cl.append(ad); self._save(); return ad

    def remove_derived_address(self, coin, path):
        if not self.wallet_data: return
        cp = self.wallet_data.get("custom_paths", {}).get(coin, [])
        self.wallet_data["custom_paths"][coin] = [a for a in cp if a.get("path") != path]
        self._save()

    def get_custom_addresses(self, coin):
        return self.wallet_data.get("custom_paths", {}).get(coin, []) if self.wallet_data else []

    def get_selected_format(self, coin):
        return self.config.get("selected_formats", {}).get(coin,
               SUPPORTED_COINS.get(coin, {}).get("default_format", "SINGLE"))

    def set_selected_format(self, coin, fmt):
        self.config.setdefault("selected_formats", {})[coin] = fmt
        self.storage.save_config(self.config)

    def get_address(self, coin, fmt=None):
        if not self.wallet_data: return None
        cfg = SUPPORTED_COINS.get(coin, {})
        if cfg.get("shares_address_with"):
            parent = cfg["shares_address_with"]
            pfmt = self.get_selected_format(parent)
            return self.wallet_data.get("addresses", {}).get(parent, {}).get(pfmt, {}).get("address")
        if fmt is None: fmt = self.get_selected_format(coin)
        return self.wallet_data.get("addresses", {}).get(coin, {}).get(fmt, {}).get("address")

    def get_all_active_addresses(self):
        if not self.wallet_data: return {}
        result = {}
        for sym in get_coin_order(self.config):
            a = self.get_address(sym)
            if a: result[sym] = a
        return result

    def get_private_key(self, coin, fmt=None):
        if not self.wallet_data: return None
        cfg = SUPPORTED_COINS.get(coin, {})
        if cfg.get("shares_address_with"):
            return self.wallet_data.get("addresses", {}).get("ETH", {}).get("SINGLE", {}).get("private_key")
        if fmt is None: fmt = self.get_selected_format(coin)
        return self.wallet_data.get("addresses", {}).get(coin, {}).get(fmt, {}).get("private_key")

    def get_mnemonic(self):
        return self.wallet_data.get("mnemonic") if self.wallet_data else None

    def get_all_formats_for_coin(self, coin):
        if not self.wallet_data: return {}
        return self.wallet_data.get("addresses", {}).get(coin, {})

    def add_custom_coin(self, sym, name, coin_type, color="#888888", icon="?",
                        decimals=18, explorer="", rpc="", contract="", coingecko=""):
        sym = sym.upper()
        cfg = {"name":name, "type":coin_type, "color":color, "icon":icon,
               "decimals":decimals, "explorer":explorer, "rpc":rpc,
               "contract":contract, "coingecko":coingecko}
        self.config.setdefault("custom_coins", {})[sym] = cfg
        if sym not in self.config.get("custom_coins_order", []):
            self.config.setdefault("custom_coins_order", []).append(sym)
        self.storage.save_config(self.config)
        # Register
        SUPPORTED_COINS[sym] = {
            "symbol":sym, "name":name, "icon":icon, "color":color,
            "decimals":decimals, "explorer":explorer, "has_own_key":False,
            "shares_address_with":"ETH", "is_evm":coin_type=="evm",
            "is_token":coin_type=="erc20", "contract":contract, "rpc":rpc,
            "coingecko":coingecko, "formats":{}, "default_format":"SINGLE",
            "format_label":"", "is_custom":True,
        }
        # Add address to current wallet
        if self.wallet_data:
            eth = self.wallet_data.get("addresses", {}).get("ETH", {}).get("SINGLE", {})
            self.wallet_data.setdefault("addresses", {})[sym] = {"SINGLE": {
                "address": eth.get("address", ""),
                "public_key": eth.get("public_key", ""),
                "private_key": eth.get("private_key", ""),
                "format": "SINGLE", "path": eth.get("path", "m/44'/60'/0'/0/0"),
                "shared_from": "ETH",
            }}
            self._save()

    def remove_custom_coin(self, sym):
        self.config.get("custom_coins", {}).pop(sym, None)
        order = self.config.get("custom_coins_order", [])
        if sym in order: order.remove(sym)
        self.storage.save_config(self.config)
        SUPPORTED_COINS.pop(sym, None)

    def set_custom_rpc(self, sym, rpc="", explorer=""):
        self.config.setdefault("custom_rpc", {})[sym] = {"rpc": rpc, "explorer": explorer}
        self.storage.save_config(self.config)

    def get_custom_rpc(self, sym):
        return self.config.get("custom_rpc", {}).get(sym, {})

    def reset_custom_rpc(self, sym):
        self.config.get("custom_rpc", {}).pop(sym, None)
        self.storage.save_config(self.config)

    def add_contact(self, name, addr, coin, notes=""):
        self.contacts.append({"id":hashlib.md5(f"{name}{addr}{time.time()}".encode()).hexdigest()[:8],
                              "name":name,"address":addr,"coin":coin,"notes":notes,"created_at":time.time()})
        self.storage.save_contacts(self.contacts)

    def remove_contact(self, cid):
        self.contacts = [c for c in self.contacts if c["id"] != cid]
        self.storage.save_contacts(self.contacts)

    def get_contacts(self, coin=None):
        return [c for c in self.contacts if c["coin"] == coin] if coin else self.contacts

    def add_tx(self, coin, tx_hash, tx_type, amount, to_addr, status="pending"):
        self.tx_history.setdefault(coin, []).insert(0,
            {"hash":tx_hash,"type":tx_type,"amount":amount,"to":to_addr,"status":status,"timestamp":time.time()})
        self.storage.save_tx(self.tx_history)

    def get_tx_history(self, coin=None):
        if coin: return self.tx_history.get(coin, [])
        all_tx = []
        for c, txs in self.tx_history.items():
            for tx in txs: tx["coin"] = c; all_tx.append(tx)
        return sorted(all_tx, key=lambda x: x["timestamp"], reverse=True)

    def change_password(self, old_pw, new_pw):
        if not self.active_wallet_id: return False
        if not self.storage.verify_wallet_password(self.active_wallet_id, old_pw): return False
        self.storage.save_wallet(self.active_wallet_id, self.wallet_data, new_pw)
        self.active_password = new_pw; return True

    def check_auto_lock(self):
        t = self.config.get("auto_lock", 300)
        if not self.is_locked and t > 0 and (time.time() - self.last_activity) > t:
            self.lock_wallet()

    def update_activity(self): self.last_activity = time.time()
    def save_config(self): self.storage.save_config(self.config)
