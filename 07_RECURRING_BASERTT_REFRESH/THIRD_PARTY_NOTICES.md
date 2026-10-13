# Source attribution and licenses

This addition consolidates recurring BaseRTT-history experiments prepared for Team 8's CS30401 project. Its source lineage is recorded in `code/provenance/package_origin.json`.

- `code/course/` contains course environment helpers retrieved from `Yeonjong21/cs30401-lab1-env`, preparation commit `f77e9a6a850805741d7290913c88ffe43dcae4ca`. Retained `LICENSE` and `NOTICE` apply to the upstream material. Its notice describes the original course repository and says satgenpy was downloaded separately; this addition vendors that separately obtained source below.
- `code/third_party/satgenpy/` contains Hypatia's satgenpy from commit `0ac531c313eba2335f6344b46347140c3a0d4230`. The upstream MIT license is retained in `code/third_party/HYPATIA_LICENSE`.
- `code/patches/ns3-refresh.patch` applies to ns-3.48 and the course-ported Hypatia/basic-sim modules. It includes source additions/changes to those GPL-licensed simulator components. No complete ns-3 distribution or simulator binary is included. Preserve the respective upstream licensing when distributing modified simulator code.
- The Python dependency lock records dependencies and hashes but does not redistribute their installed distributions. Those dependencies retain their own licenses.

Core research reference: Kassing et al., “Exploring the Internet from space with Hypatia,” ACM IMC, 2020.

Archived reference results are the measured/derived experiment artifacts previously supplied for this project. They are not newly simulated measurements.
