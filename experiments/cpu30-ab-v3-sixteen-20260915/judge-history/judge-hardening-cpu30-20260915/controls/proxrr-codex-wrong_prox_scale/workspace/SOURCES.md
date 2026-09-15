# Sources and provenance

- Paper: arXiv:2102.06704v1, `Proximal and Federated Random Reshuffling`, Mishchenko, Khaled, and Richtarik (2021). The task-provided PDF SHA256 is `765342ddc320fe1b8f0507848a2ee818e9fd5080fa57d980bfa44acce44a7ae0`.
- Official reference repository: https://github.com/konstmish/rr_prox_fed at commit `7a72e2bb38794897e729d1a474b59e671f51701d`. The snapshot supplied with the task was inspected read-only; the package here reimplements its objective and optimizer behavior without bundling a third-party checkout.
- Datasets: the official snapshot's libsvm files `a1a`, `a9a`, and `mushrooms` are copied into `.run-data/datasets/` at run time. Formal result configurations record byte counts and SHA256 checksums. These files are intentionally excluded from Git history.
- Numerical libraries: versions are pinned in `requirements.txt`; formal runs record the Python, NumPy, and platform information in `machine.json`.

