# 0003 - Distributed Probe Architecture over VPN

## Status

Accepted (Amended)

## Context

OpsFlow originally deployed as a single-machine tool with nmap and iperf3 executing locally on the host. To serve multiple branch offices with accurate network discovery, the platform needs to execute nmap/iperf3 from within each branch's local network-not from a central server that would be separated by firewalls, NAT, and routing.

The team considered three options:
- **Central server with remote execution**: scan from the central server over VPN. Rejected because nmap results would reflect the VPN tunnel path, not the actual local network topology.
- **Pure probe mode without VPN**: probes on public internet. Rejected due to security concerns and difficulty accessing internal network data.
- **Distributed probes over site-to-site VPN**: probes deployed inside each branch network, communicating with the central platform over a WireGuard VPN tunnel.

Initial decision assumed site-to-site VPN at the router level (probes do not need VPN client software). This was amended because not all branch office routers support WireGuard configuration. The central server has a static public IP.

## Decision

Adopt a distributed probe architecture with WireGuard VPN, where probes carry their own VPN client:

1. **Probes** are Docker Compose deployments inside each branch's local network. The probe image bundles Python, nmap, iperf3, and WireGuard. Probes execute nmap/iperf3 using the physical network interface (for local scanning) and communicate with the central platform over the WireGuard VPN tunnel.

2. **WireGuard VPN** connects each probe to the central server. The probe runs as a WireGuard client (road warrior mode), connecting to the central server's public IP on UDP 51820. The probe does not depend on router-level VPN support.

3. **Probe networking**: the probe container uses host networking for nmap/iperf3 access to the local network. WireGuard runs inside the container, creating a tunnel interface (e.g., wg0) for VPN traffic to the central server. The probe's `OPSFLOW_URL` points to the central server's VPN tunnel IP (e.g., 10.99.0.1:8000).

4. **Pull mode**: probes poll the central API over the VPN tunnel for pending tasks and POST results back. No inbound ports required on the probe.

5. **Probe-only execution**: the central server does not execute nmap or iperf3 directly. Scan and iperf tasks are only executed by probes. Organizations without a probe cannot create scan or iperf tasks.

6. **Monitoring split**: Zabbix (already deployed at each branch) handles real-time continuous monitoring and alerting (seconds-level). Probes handle on-demand deep scanning and throughput testing (minutes-level). The central dashboard aggregates both data sources.

7. **HTTPS reserved**: the probe-to-central communication currently goes over VPN. If future branch offices block UDP 51820, the architecture can fall back to public HTTPS (with a domain + TLS certificate) without changing probe logic. This is deferred until needed.

## Consequences

- The probe Docker image must include WireGuard tools and kernel module access (`--cap-add NET_ADMIN`).
- The central server must have a public IP and run WireGuard server, accepting connections on UDP 51820.
- Each probe needs its own WireGuard key pair and a tunnel IP assignment. The central server maintains a list of peer public keys.
- The single-machine deployment includes a local probe that connects to the local WireGuard server (or skips VPN if co-located).
- Network topology requires non-overlapping subnet planning across all sites.
- If a branch firewall blocks UDP 51820, the probe cannot connect. Mitigation: document the requirement, or use udp2raw to wrap WireGuard in TCP.
