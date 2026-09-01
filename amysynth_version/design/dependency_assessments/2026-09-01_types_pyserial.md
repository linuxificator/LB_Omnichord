# Dependency assessment: types-pyserial

Date: 2026-09-01
Decision: adopt as test-only typing data
Owner: test and quality requirements
Requirement: make the existing `pyserial==3.5.*` transport API visible to mypy
Owning dependency group: `requirements-test.txt`

## Decision evidence

`types-pyserial` is the official typeshed stub distribution for pyserial, not a
runtime implementation or a small independent wrapper. The selected
3.5.0.20260712 release explicitly targets pyserial 3.5, supports Python 3.10+
and is generated from the Python-community typeshed project according to its
[PyPI record](https://pypi.org/project/types-pyserial/). It is Apache-2.0
licensed and a universal pure-Python typing wheel.

The stubs run only inside static analysis. They add no imports, allocations or
platform behavior and are not included in release artifacts. If pyserial gains
inline types or is replaced, this package can be removed with no runtime or
data migration.

Accepted input: `types-pyserial==3.5.0.20260712`.
