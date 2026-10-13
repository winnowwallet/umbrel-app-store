# Winnow Umbrel app store

A community [Umbrel](https://umbrel.com) app store with one app, **Winnow
Gateways**: the Tor and I2P SOCKS gateways that
[Winnow](https://winnowwallet.com)'s Automatic peer routing looks for on your
tailnet. Add `https://github.com/winnowwallet/umbrel-app-store` under *App
Store → Community App Stores* in umbrelOS 2.0 or later, then install it.

Winnow resolves two names through Tailscale's own resolver and uses whichever
answers a SOCKS5 greeting: `winnow-tor-gateway:9050` and
`winnow-i2p-gateway:4447`. When either answers, it sends every Bitcoin peer
connection through Tor and I2P and none direct. How the wallet decides is in
[winnow's peer-gateway guide](https://github.com/winnowwallet/winnow/blob/main/docs/peer-gateways.md).

The app joins your tailnet as two machines with those names. Tor goes through
Umbrel's own Tor proxy; I2P through an i2pd router in the app. The gateways
advertise no routes and are not exit nodes, and nothing is published on your
LAN or the internet.

## Setup

1. Make sure the names are free: if any machine on your tailnet is already
   called `winnow-tor-gateway` or `winnow-i2p-gateway`, delete or rename it.
2. In the Tailscale admin console, generate a reusable auth key. A tagged key
   is best, because tagged machines' keys do not expire; whatever tags you
   choose need an owner in your tailnet policy's `tagOwners`, such as
   `["autogroup:admin"]`. With an untagged key, turn off key expiry for both
   machines after they join, or they drop off the tailnet when it lapses.
3. Install the app, then enter the key as `TS_AUTHKEY` under *App settings →
   Advanced → Environment variables* and save. The app restarts.
4. Open the app. Its status page shows, for each gateway, whether it has
   joined, under which name, and whether the proxy behind it answers. A new
   i2pd router can take a few minutes to integrate.

Each gateway uses the key once; you can clear it afterwards. On the phone,
keep the Tailscale app connected to the same tailnet, with MagicDNS on, and
leave Winnow's peer routing on Automatic.

## Who can use them

Anyone your tailnet policy lets reach these machines can use your Tor and I2P
through them. A SOCKS proxy has no login. To limit them, give the machines a
tag and allow TCP 9050 and 4447 to it only from your own devices.
