# IXON Config Pipeline AS-IS

- Generated at: `2026-03-29T11:22:07Z`
- Files analyzed: `30`

## Components
- IXrouter3 device (OpenWrt-based): edge router running LAN/WAN/VPN/services
- LAN bridge interface `lan` on `eth0.1`: local subnet gateway/DHCP-DNS segment
- WAN interface `wan` on `eth0.2`: primary uplink (static IPv4 + DHCPv6)
- WWAN interface `wwan` on `wwan0`: cellular uplink (QMI), currently disabled
- STA WAN interface `sta_wan` on `mlan0`: Wi-Fi client uplink
- VPN interface `vpn` on `tap+`: DHCP-based virtual VPN-side interface
- Firewall (`/etc/config/firewall`): zone policy and inter-zone forwarding
- Bridge firewall (`/etc/config/bridge-firewall`): L2 filtering/brouting around `tap0`
- DNS/DHCP (`dnsmasq`): LAN name resolution and lease assignment
- SSH server (`dropbear`): remote shell on port 22
- Web UI/API (`uhttpd` + LuCI + rpcd/ubus): HTTP management plane
- IXrouter link monitor (`/etc/config/ixrouter`): multi-uplink health/priority tracking
- BACnet service: UDP/47808 bound to `br-lan`

## Data Flows
- LAN clients -> IXrouter `lan` (`eth0.1`, 192.168.27.1/24) + IPv4/IPv6
- IXrouter `lan` -> WAN zone (`wan`,`wan6`,`wwan`,`sta_wan`,`sta_wan6`) via IP forwarding/NAT
- IXrouter `lan` <-> VPN zone (`vpn`) via bidirectional forwarding rules
- VPN source port 2000 -> DNAT -> `192.168.27.11` (`tcpudp`)
- DNS/DHCP requests on LAN -> dnsmasq (`/tmp/dhcp.leases`, `/tmp/resolv.conf.auto`)
- BACnet traffic on `br-lan` UDP/47808 -> local BACnet service
- `tap0` L2 frames (IPv4/ARP) -> broute path; selected ARP forwarding on `tap0` explicitly dropped
- LuCI HTTP clients -> `uhttpd` on `0.0.0.0:80`/`[::]:80` -> Lua handler `/cgi-bin/luci` -> rpcd/ubus socket `/var/run/ubus.sock`

## Control Flows
- Boot/init applies UCI configs for `network`, `firewall`, `dnsmasq`, `dropbear`, etc. (from `ucitrack` init mappings)
- Provisioning/management edits UCI files in `/etc/config`; LuCI apply has rollback window (`rollback 30`)
- Runtime uplink selection/monitoring inferred from `/etc/config/ixrouter` priorities + tracked IP probes at 5s interval
- Runtime forwarding policy enforced by zone forwardings (`lan->wan`, `lan<->vpn`) plus explicit REJECT rules
- Runtime management planes remain enabled: SSH password auth and HTTP LuCI

## Device Pipeline
- System boots as hostname `IXrouter3` with UTC timezone.
- Network stack brings up `lan` (static 192.168.27.1/24) on bridge `eth0.1`; switch VLANs map LAN/WAN ports.
- Primary WAN `eth0.2` comes up with static IPv4 (192.168.8.118/24, gw 192.168.8.1, DNS 8.8.8.8) and DHCPv6 (`wan6`).
- Alternative uplinks are defined: `wwan0` (QMI, disabled=1) and `mlan0` (`sta_wan` DHCP, `sta_wan6` DHCPv6).
- IXrouter monitor tracks public IPs every 5s per interface with priorities wan=1, wwan=2, sta_wan=3 (behavior beyond tracking is inferred).
- Firewall zones/forwardings activate (`lan`, `wan`, `vpn`) with masquerading enabled on `lan` and `wan`.
- dnsmasq serves LAN DHCP pool (100-249) and local DNS domain `lan`; WAN DHCP server disabled.
- VPN interface pattern `tap+` obtains DHCP; bridge-firewall/brouting rules around `tap0` handle L2 IPv4/ARP behavior.
- Management services start: `dropbear` on 22, `uhttpd` HTTP on 80, LuCI->rpcd/ubus control path.
- BACnet service listens on `br-lan` port 47808.

## Cloud Pipeline
- Device has a `vpn` network bound to `tap+`, indicating VPN-created TAP interfaces are expected.
- Firewall explicitly allows `vpn -> lan` and `lan -> vpn`, enabling bidirectional routed/bridged remote-to-local access once VPN is up.
- A specific VPN-side DNAT is configured (`src vpn`, port 2000 -> `192.168.27.11`), indicating remote service publishing through VPN.
- WAN-zone includes multiple physical uplinks (`wan`,`wwan`,`sta_wan` and v6 variants), implying cloud reachability can use whichever uplink is active.
- `/etc/config/openvpn` present but only sample instances are `enabled 0`; active cloud tunnel mechanism cannot be confirmed from provided configs alone.
- No explicit cloud registration token/endpoint is present in shown artifacts; registration workflow is unknown from configs only.

## Security Model
### Identity
- Device identity hints: hostname `IXrouter3`; fixed MACs on `lan`/`wan` interfaces.
- SSH uses password-based auth including root (`PasswordAuth 'on'`, `RootPasswordAuth 'on'`).
- rpcd has root login entry with placeholder hash reference `'$p$root'` and full read/write ACL.
- OpenVPN sample references cert/key files (`ca.crt`, `server.crt`, `server.key`) but sample is disabled; active cert usage unconfirmed.
- No explicit cloud token/serial/certificate artifact shown in provided config set.
### Transport
- LAN/WAN/VPN traffic is IP-routed with firewall/NAT; masquerading enabled on `lan` and `wan` zones.
- Management web transport is HTTP only in config (`listen_http` enabled; HTTPS listeners commented out).
- SSH transport enabled on TCP/22 via Dropbear.
- VPN transport type for production tunnel is uncertain; only generic `vpn` interface on `tap+` and disabled OpenVPN samples are visible.
- L2 bridge/firewall controls include EtherType allow rules and brouting for IPv4/ARP on `tap0`.
### Access Control
- Zone policies: `wan` input REJECT, forward REJECT; `lan` and `vpn` input/output/forward ACCEPT.
- Forwarding permissions: explicit `lan->wan`, `lan->vpn`, `vpn->lan`.
- Additional egress control: `lan->wan` to RFC1918 ranges REJECT and `lan->wan` public rule also REJECT (suggesting restrictive custom policy; interpretation medium due truncation).
- rpcd ACL in config grants root `read '*'` and `write '*'` (full privileges).
- uhttpd/LuCI session control exists (`sessiontime 3600`), but no extra HTTP auth section enabled in shown config.

## Config to Behavior
- `firmware_dump/etc/config/network` / `config interface 'lan'`: Device LAN gateway is static 192.168.27.1/24 on bridge `eth0.1` with IPv6 prefix assignment. (confidence: high)
  - evidence: option ifname 'eth0.1'
  - evidence: option type 'bridge'
  - evidence: option proto 'static'
  - evidence: option ipaddr '192.168.27.1'
  - evidence: option netmask '255.255.255.0'
  - evidence: option ip6assign '60'
- `firmware_dump/etc/config/network` / `config interface 'wan'`: Primary WAN uses static IPv4 config with gateway and manual DNS. (confidence: high)
  - evidence: option ifname 'eth0.2'
  - evidence: option proto 'static'
  - evidence: option ipaddr '192.168.8.118'
  - evidence: option gateway '192.168.8.1'
  - evidence: list dns '8.8.8.8'
- `firmware_dump/etc/config/network` / `config interface 'wwan'`: Cellular/QMI uplink exists but is disabled in this snapshot. (confidence: high)
  - evidence: option ifname 'wwan0'
  - evidence: option proto 'qmi'
  - evidence: option device '/dev/cdc-wdm0'
  - evidence: option at_device '/dev/ttyUSB3'
  - evidence: option disabled '1'
- `firmware_dump/etc/config/network` / `config interface 'vpn'`: VPN network expects TAP-style interfaces (`tap+`) and gets addressing via DHCP. (confidence: high)
  - evidence: option ifname 'tap+'
  - evidence: option proto 'dhcp'
- `firmware_dump/etc/config/ixrouter` / `config interface 'wan'/'wwan'/'sta_wan'`: A link-monitor/failover controller likely probes fixed internet IPs every 5s and ranks interfaces by priority. (confidence: medium)
  - evidence: option interval '5'
  - evidence: option priority '1'
  - evidence: option priority '2'
  - evidence: option priority '3'
  - evidence: list track_ip '208.67.220.220'
  - evidence: list track_ip '8.8.8.8'
- `firmware_dump/etc/config/firewall` / `zone_wan + forwardings`: WAN is ingress-restricted, while LAN<->VPN and LAN->WAN forwarding are explicitly allowed. (confidence: high)
  - evidence: option name 'wan'
  - evidence: option input 'REJECT'
  - evidence: config forwarding 'forwarding_lan_wan'
  - evidence: config forwarding 'forwarding_vpn_lan'
  - evidence: config forwarding 'forwarding_lan_vpn'
- `firmware_dump/etc/config/firewall` / `config redirect 'portforward_vpn_2000'`: Traffic from VPN clients to port 2000 is DNATed to internal host 192.168.27.11. (confidence: high)
  - evidence: option src 'vpn'
  - evidence: option src_dport '2000'
  - evidence: option target 'DNAT'
  - evidence: option dest_ip '192.168.27.11'
- `firmware_dump/etc/config/firewall` / `forwarding_lan_wan_private / forwarding_lan_wan_public`: Custom rules reject LAN-to-WAN traffic (private ranges and an additional broad public rule), implying tightened outbound policy. (confidence: medium)
  - evidence: option name 'forward_lan_wan_private'
  - evidence: list dest_ip '10.0.0.0/8'
  - evidence: list dest_ip '172.16.0.0/12'
  - evidence: list dest_ip '192.168.0.0/16'
  - evidence: option target 'REJECT'
  - evidence: option name 'forward_lan_wan_public'
  - evidence: option target 'REJECT'
- `firmware_dump/etc/config/bridge-firewall` / `defaults/rules/broute`: Layer-2 filtering defaults to DROP, with explicit EtherType allowances and special handling of IPv4/ARP on `tap0`. (confidence: medium)
  - evidence: option input 'DROP'
  - evidence: option output 'DROP'
  - evidence: option forward 'DROP'
  - evidence: option proto '0x8892'
  - evidence: option proto '0x8100'
  - evidence: config broute 'broute_ipv4'
  - evidence: option interface 'tap0'
  - evidence: option proto 'IPv4'
  - evidence: config broute 'broute_arp'
- `firmware_dump/etc/config/dhcp` / `config dhcp lan / dnsmasq`: Router provides authoritative LAN DHCP/DNS for domain `lan`; WAN-side DHCP service is disabled. (confidence: high)
  - evidence: option authoritative	1
  - evidence: option domain	'lan'
  - evidence: config dhcp lan
  - evidence: option start 	100
  - evidence: option limit	150
  - evidence: config dhcp wan
  - evidence: option ignore	1
- `firmware_dump/etc/config/dropbear` / `config dropbear`: SSH management allows password auth including root on port 22. (confidence: high)
  - evidence: option PasswordAuth 'on'
  - evidence: option RootPasswordAuth 'on'
  - evidence: option Port         '22'
- `firmware_dump/etc/config/uhttpd` / `config uhttpd main`: Web management is exposed over HTTP on all interfaces; HTTPS is not enabled in config. (confidence: high)
  - evidence: list listen_http	0.0.0.0:80
  - evidence: list listen_http	[::]:80
  - evidence: #list listen_https	0.0.0.0:443
  - evidence: #list listen_https	[::]:443
- `firmware_dump/etc/config/rpcd` / `config login`: rpcd defines root account with full ubus read/write permissions. (confidence: high)
  - evidence: option username 'root'
  - evidence: list read '*'
  - evidence: list write '*'
- `firmware_dump/etc/config/bacnet` / `config service 'service'`: BACnet service is bound to LAN bridge and UDP port 47808. (confidence: high)
  - evidence: option ifname 'br-lan'
  - evidence: option port '47808'
- `firmware_dump/etc/config/openvpn` / `custom_config / sample_server`: Provided OpenVPN UCI entries are templates/examples and disabled; they do not prove active OpenVPN tunnel. (confidence: high)
  - evidence: config openvpn custom_config
  - evidence: option enabled 0
  - evidence: config openvpn sample_server
  - evidence: option enabled 0
- `firmware_dump/etc/config/ucitrack` / `init mappings`: UCI config changes trigger restarts/reloads of linked services, shaping runtime control flow. (confidence: high)
  - evidence: config network option init network
  - evidence: config firewall option init firewall
  - evidence: config dhcp option init dnsmasq
  - evidence: config dropbear option init dropbear
  - evidence: config system option exec '/etc/init.d/log reload'

## Gaps and Unknowns
- No explicit IXON cloud endpoint, tenant/org ID, registration token, or device serial mapping appears in provided configs.
- Actual VPN daemon/process used for production cloud tunnel is not identifiable from these files alone (only `tap+` interface and disabled OpenVPN samples).
- Truncated tail of `/etc/config/firewall` may hide additional redirects/rules, affecting full traffic policy interpretation.
- Bridge-firewall semantics (especially broute behavior) require runtime ebtables/br_netfilter implementation details not present here.
- Authentication secrets/cert material contents are not provided (`/etc/dropbear/*`, `/etc/openvpn/*`, passwd shadow data).
- Service enablement/order at boot (procd init scripts, rc.d links) is not fully derivable from config snippets only.
- Wireless operational state is unclear: device stanzas are `disabled '1'`, but interface usage may be changed dynamically at runtime.
- No logs or process list are provided, so inferred failover behavior from `ixrouter` priorities cannot be validated empirically.

## Takeaways for MYXON
- Model uplink orchestration as priority + health-probe based policy (`interval`, `track_ip`, `priority`) rather than single-WAN assumptions.
- Support mixed connectivity stack: wired WAN, cellular QMI, Wi-Fi STA uplink, and VPN virtual interface (`tap+`).
- Represent policy at two layers: L3 zone firewall/NAT and separate L2 bridge-firewall/brouting controls for TAP/bridge scenarios.
- Treat `vpn<->lan` forwarding and VPN-side DNAT as first-class remote-access primitives.
- Assume device-local services (DHCP/DNS/BACnet) stay on LAN while cloud path is via WAN-selected uplink + VPN.
- For security baseline in MYXON, avoid mirroring weak defaults seen here (HTTP-only LuCI, root/password SSH) unless explicitly required for compatibility.
- Build config-to-runtime reconciliation around UCI-style service restart graph (similar to `ucitrack`) to ensure predictable apply semantics.
- Mark cloud-registration details as external dependency: cannot be reconstructed from these artifacts, so design explicit provisioning artifacts for tokens/endpoints/certs.
