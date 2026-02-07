# Nexus Wallet

<p align="center">
  <img src="https://img.shields.io/badge/version-3.2-8b5cf6?style=for-the-badge" alt="Version 3.2">
  <img src="https://img.shields.io/badge/python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/license-MIT-06d6a0?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20|%20macOS%20|%20Linux-1e293b?style=for-the-badge" alt="Cross Platform">
</p>

<p align="center">
  <b>A multi-chain HD desktop wallet that actually respects your privacy.</b><br>
  Your keys. Your coins. No servers. No tracking. No BS.
</p>

---

## Why I Built This

I wanted something simple: generate a seed, derive my addresses, send and receive, check my balances that’s it. No cloud sync. No analytics. No emails.

I’m fed up with people collecting my data, digging through it, and selling it. We don’t know how they use it, and I refuse to become a product for them.

So I built Nexus. It runs locally, storing everything encrypted on disk.

---

## What It Does

**11 assets out of the box** — Bitcoin, Ethereum, BNB Chain, Polygon, Solana, Tron, Litecoin, Dogecoin, Bitcoin Cash, USDT, and USDC. All from a single seed phrase.

**Real transaction signing & broadcasting** — This isn't a demo wallet. When you hit Send, it actually signs the transaction locally with your private key and broadcasts it to the network. Supports all 11 assets. BTC uses mempool.space for fee estimation and broadcasting. ETH/BNB/MATIC goes through JSON-RPC. SOL uses Solana RPC. TRX goes through TronGrid. LTC/DOGE use Blockcypher. Each chain has its own proper signing flow.

**HD Derivation done right** — Full BIP39/44/49/84/86 support. Switch between Legacy, SegWit, Native SegWit, and Taproot for Bitcoin. Pick whatever format you want for Litecoin. Every coin gets the correct derivation path, not some lazy shortcut.

**Add your own tokens** — Got some ERC-20 token or an EVM chain I didn't include? Add it yourself from Settings. It shares your ETH address (because that's how EVM works) and you can send from it too, as long as you configure the RPC.

**Custom RPC endpoints** — Don't trust public RPCs? Run your own node and point Nexus to it. Override the RPC and block explorer URL for every single coin. Your node, your rules.

**Multi-language ready** — The whole UI runs through a translation system. English is included, adding more is just copying a dictionary in one file.

**Real transactions** — Send any supported coin directly from the wallet. BTC, ETH, BNB, MATIC, SOL, TRX, LTC, DOGE, BCH, USDT, USDC — all with real signing and broadcasting. Password required for every transaction, fee estimation shown before confirming.

**Multi-wallet** — Create as many wallets as you want. Each one gets its own seed, its own encryption, its own password.

---

## Quick Start

### Requirements
- Python 3.9 or higher
- pip

### Install & Run

```bash
git clone https://github.com/l0e0l/Nexus-Crypto-Wallet.git
cd Nexus-Crypto-Wallet

pip install -r requirements.txt

python main.py
```

On Windows, double-click `setup_and_run.bat`.

### Dependencies

```
customtkinter, Pillow, qrcode, pyperclip, requests, bip_utils, cryptography
eth-account, bit, bitcash, solders, ecdsa, base58, pynacl
```

The first line is the core wallet. The second line is for real transaction signing — each library handles a specific chain.

---

## Transaction Signing

Every send goes through this flow:

1. You enter the address, amount, and pick a fee level
2. Nexus estimates the network fee and shows you the details
3. You enter your wallet password to decrypt your private key
4. The transaction is signed locally — your key never leaves your machine
5. The signed transaction is broadcast to the network
6. You get the TX hash and a link to view it on a block explorer

Here's how each chain works under the hood:

| Chain | Signing Library | Broadcasting | Fee Source |
|-------|----------------|--------------|------------|
| BTC | `bit` | mempool.space | mempool.space/api/fees |
| ETH | `eth-account` | JSON-RPC | eth_gasPrice |
| BNB | `eth-account` | BSC JSON-RPC | eth_gasPrice |
| MATIC | `eth-account` | Polygon JSON-RPC | eth_gasPrice |
| USDT/USDC | `eth-account` | ETH JSON-RPC | eth_estimateGas |
| SOL | `solders` + `pynacl` | Solana RPC | Fixed 5000 lamports |
| TRX | `ecdsa` (secp256k1) | TronGrid API | Bandwidth/Energy |
| LTC | `ecdsa` + Blockcypher | Blockcypher API | Blockcypher estimate |
| DOGE | `ecdsa` + Blockcypher | Blockcypher API | Blockcypher estimate |
| BCH | `bitcash` | Bitcoin Cash network | Built-in |

Custom EVM tokens and chains also work — as long as you've set a valid RPC endpoint, Nexus will sign and broadcast through it.

---

## Security

- **AES-256 encryption** for all wallet data at rest
- **PBKDF2 with 480,000 iterations** for key derivation from your password
- **Private key decrypted only at send time** — and only after password verification
- **Auto-lock** after configurable timeout (default 5 minutes)
- **Private keys auto-hide** after 30 seconds of being displayed
- **All signing happens locally** — keys never touch the network

Your seed phrase is encrypted and stored in `~/.nexus_wallet/`. I don't have access to it. Nobody does except you.

---

## Supported Coins & Derivation Paths

| Coin | Symbol | Derivation | Formats |
|------|--------|-----------|---------|
| Bitcoin | BTC | m/44'/0', m/84'/0', m/86'/0' | Legacy, Native SegWit, Taproot |
| Ethereum | ETH | m/44'/60' | Standard |
| BNB Chain | BNB | Shares ETH address | EVM |
| Polygon | MATIC | Shares ETH address | EVM |
| Solana | SOL | m/44'/501' | Standard |
| Tron | TRX | m/44'/195' | Standard |
| Litecoin | LTC | m/44'/2', m/49'/2', m/84'/2' | Legacy, Nested SegWit, Native SegWit |
| Dogecoin | DOGE | m/44'/3' | Legacy |
| Bitcoin Cash | BCH | m/44'/145' | Legacy |
| Tether | USDT | ERC-20 on ETH | Token |
| USD Coin | USDC | ERC-20 on ETH | Token |

Plus any custom tokens you add from Settings.

---

## Custom RPC & Explorer

**Settings > Custom RPC / Explorer** — set your own endpoints for any coin.

Use `{}` as a placeholder for address/hash in explorer URLs:
```
https://my-explorer.local/address/{}
```

---

## Adding Custom Tokens

**Settings > Custom Tokens > + Add Custom Token**

- **ERC-20 tokens**: contract address + decimals
- **EVM chains**: any Ethereum-compatible chain with its own RPC

Custom tokens share your ETH address and support sending if RPC is configured.

---

## Adding Languages

Add a dictionary to `wallet_core.py`:

```python
STRINGS["ar"] = {
    "app_name": "Nexus Wallet",
    "dashboard": "Dashboard",
    # ... translate all keys from STRINGS["en"]
}
```

Select from Settings > Language. Falls back to English for missing keys.

---

## Project Structure

```
nexus-wallet/
+-- main.py              # UI layer
+-- wallet_core.py       # HD engine, encryption, i18n
+-- blockchain_api.py    # Balance fetching, price APIs
+-- tx_engine.py         # Transaction signing & broadcasting
+-- requirements.txt
+-- setup_and_run.bat
+-- README.md
```

Four Python files. That's the whole wallet.

---

## Known Limitations

1. **LTC/DOGE sending uses Blockcypher API** — this means Blockcypher handles UTXO selection. If you want full sovereignty, run your own infrastructure.
2. **TRX signing uses raw ecdsa** — works fine but less battle-tested than dedicated libraries.
3. **No hardware wallet support yet** — Ledger/Trezor integration is on the roadmap.
4. **Not audited** — crypto primitives come from established libraries but the integration is mine. Use at your own risk with amounts you're comfortable with.

---

## Roadmap

- [ ] Hardware wallet support (Ledger/Trezor)
- [ ] More languages (Français, Türkçe, Español, Chinese {中文}, العربية, Deutsch, 日本語, 한국어, Русский, Português, हिन्दी)
- [ ] Historical price charts
- [ ] Import/export from MetaMask, Electrum
- [ ] Flatpak/Snap packaging

---

## Contributing

PRs welcome. Keep it simple. Don't add 47 npm dependencies.

---

## License

MIT. Do whatever you want with it.

---

## Disclaimer

This software is provided as-is, without warranty. I'm not responsible for any loss of funds. Always verify addresses before sending. Always keep your seed phrase backed up. Don't store life-changing money in any hot wallet.

---

## Support the Project

If Nexus helped you out, here are my addresses:

**Bitcoin (BTC)**
```
1PCk9Y9eHoGBDD8YRo8Y6droVUNC9akEQ1
```

**Ethereum (ETH)**
```
0x9cc957df65b0b6caa570280ff72f05e98cc7f9f9
```

**Monero (XMR)**
```
4BFCQ1HB14dcbWvDDcuyJJaBKaRJt2vHHHhbVFr7gMrtCFS3TYLZQzbCiy61W6K8ppL8Etv1gQdD9LBarjtucTmy2UdbuuU
```

**Zcash (ZEC)**
```
t1VLBF3yzEgxPuFEN6QbhM97vEGepELyMMP
```

Starring the repo helps too.

---

<p align="center">
  <b>Nexus Wallet v3.2</b> — built with mass amounts of coffee and mass amounts of stubbornness.
</p>
