# Run Network Work as Asynchronous Tasks

OpsFlow runs scanning, performance testing, topology discovery, and renewal checks as asynchronous tasks instead of holding API requests open. Network work can be slow, noisy, or blocked by remote targets, so the platform records task state and results while workers execute the long-running operations outside the request path.
