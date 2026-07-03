# Use Host Networking for Linux Deployments

OpsFlow uses host networking in the Linux deployment profile so Nmap, Iperf3, the backend, Redis, and Nginx operate directly on the server network stack. This trades port isolation for more accurate network discovery and lower measurement distortion, which matters because the platform is meant to inspect and test the same internal network the host can reach.
