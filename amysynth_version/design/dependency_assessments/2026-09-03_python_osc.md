# Dependency assessment: python-osc

Date: 2026-09-03
Decision: adopt
Owner: OSC input adapter
Requirement and code replaced/prevented: OSC 1.0 message and bundle parsing
Owning dependency group: portable runtime

## Functional fit and public API

LB Omnichord needs to receive OSC 1.0 messages over one configured UDP socket,
decode bundles and expose numeric arguments through a small application-owned
event type. `python-osc` provides a public `OscPacket` parser for exactly that
protocol surface. The application retains socket lifecycle and threading, so
library server objects and callbacks do not leak into the Qt or binding layers.

Qt provides portable UDP sockets but no OSC packet decoder. A local decoder
would have to reproduce OSC padding, type tags, bundles and nested packets and
would therefore be a partial implementation of an established protocol.

## Maintenance health and release activity

The upstream project describes itself as stable, has 422 commits and published
1.10.2 on 2026-04-02. Its current package requires Python 3.10 or newer and the
repository remains active. The project is primarily owned by one maintainer;
that concentration is a risk, but the stable protocol, active 2026 release,
small source surface and dependency-free exit path keep it acceptable.

## Adoption and ecosystem standing

The public repository had approximately 582 stars and 118 forks when checked.
It has been released since 2013, has public documentation and examples and is
widely recognizable as the standard Python OSC package. These are supporting
signals rather than a security guarantee.

## Five-platform and packaging evidence

1.10.2 publishes one `py3-none-any` wheel, is pure Python and declares no
runtime dependencies. The used parser operates only on bytes and standard
Python values. The application-owned UDP adapter uses the standard-library
socket API available on Linux x86_64, Linux aarch64, macOS arm64, Windows
x86_64 and Android arm64.

This source-level evidence permits adoption. All five release jobs must install
the portable requirements and exercise an OSC parser/import/package smoke
before the feature may merge to `main`; Android packaging remains a mandatory
gate rather than an assumption based on a universal wheel tag.

The macOS bundle must carry `NSLocalNetworkUsageDescription` before signing.
The current Android target API 36 uses `INTERNET`; its platform contract grants
that target implicit local-network access and says not to request the new
runtime `ACCESS_LOCAL_NETWORK` permission before target API 37. A target-SDK
upgrade therefore requires a deliberate permission-flow change and test.

## License and redistribution obligations

The package and repository publish the Unlicense/public-domain dedication. It
permits source and binary redistribution. The package has no transitive
dependencies. Release component evidence must identify the package, version,
license and upstream source.

## Security and supply-chain evidence

PyPI identifies the repository, publishes wheel SHA-256
`018b28e1cc06427c2c3d695f4e8d87d0caecfe604ff889acc45235cfd94183a2`,
and reported no known vulnerabilities on 2026-09-03. The package has no install-
or run-time downloads and no dependencies. Release inputs pin 1.10.2; normal
dependency review remains responsible for future advisories and ownership
changes.

OSC over UDP has no authentication or confidentiality. That network property
is handled by configuration and product documentation, not delegated to this
parser: users should bind to loopback on untrusted networks or apply host
firewall rules.

## Runtime/thread/real-time impact

Only the OSC adapter worker imports and calls the parser. One bounded UDP
datagram is decoded synchronously and converted to immutable application
events. Parsing and socket I/O never run in the Qt thread or AMY audio process.
There are no transitive imports or background threads owned by the package.

## Test boundary, migration and exit cost

Tests construct real OSC packets with the public builder API, send them through
a loopback UDP socket and assert only application-owned immutable events. Unit
tests also feed malformed datagrams and bundles directly to the adapter
boundary. If the package becomes unsuitable, only the adapter parser call and
its tests change; preset, QML and musical state contain no `python-osc` types.

## Exact accepted version/range and sources

- exact version: `python-osc==1.10.2`
- PyPI: https://pypi.org/project/python-osc/1.10.2/
- source: https://github.com/attwad/python-osc
- documentation: https://python-osc.readthedocs.io/
- protocol: https://opensoundcontrol.stanford.edu/spec-1_0.html
- Apple local-network privacy: https://developer.apple.com/documentation/Technotes/tn3179-understanding-local-network-privacy
- Android local-network permission: https://developer.android.com/privacy-and-security/local-network-permission

## Required follow-up and review date

Update the portable requirement hash, release component evidence and SPDX
generation inputs. Run all five package jobs before merging to `main`. Review
maintenance, ownership and the latest safe compatible version no later than
2027-09-03 or sooner when a vulnerability or Python compatibility issue is
reported.
