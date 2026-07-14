# Security policy

Please report vulnerabilities privately to the repository owner rather than
opening a public issue.

## Model trust boundary

PyTorch package models contain serialized executable Python objects. The
service therefore loads only model URLs and SHA-256 digests pinned in its
reviewed catalogue. It does not execute arbitrary Torch Hub repositories or
accept user-supplied model paths through the HTTP API.

Downloaded files remain inactive until their expected size and digest match.
They are then promoted atomically into the managed model directory.

The server binds to loopback by default. Set `SILERO_API_KEY` whenever it is
reachable outside the local machine, and place it behind an authenticated TLS
reverse proxy.

