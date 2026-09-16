# Sources

- Paper: arXiv:2201.13320v3, SHA-256 `7f6492f9472edfeb6133d39667df94e17e1cdd3ee7af21166491e9a0110eae22`.
- Algorithm cross-check: `https://github.com/liboyue/beer`, commit `ebd11e0effb6bef448bf7261dfb7601935edce98`.
- a9a: LIBSVM canonical `a9a` (`2329875` bytes, SHA-256 `f5d5ffd8d865ff41328e7ee043e4b020816914ff6843ff15b98905ddbedce906`) and `a9a.t` (`1164628` bytes, SHA-256 `1f448a153f0320399a7e40836eb207655b0bde0f21fc941cc472193daa9f5de9`), supplied read-only at the path in `DATASETS.json`.
- MNIST: supplied parquet mirror, `train.parquet` (`15561616` bytes, SHA-256 `f2c01285a9f89399335b00ee4e8d499dc4e46db5e39c74903ce5618d895eb3bf`) and `test.parquet` (`2595890` bytes, SHA-256 `d49fcf556ce25b002b302e318ce4a11098bbfe5d4499c3f35d7c72297c52374b`).

The runner writes a machine-readable copy of the dataset metadata to `.run-data/SOURCES.md` when formal data preparation is performed. Large shared data and caches are intentionally excluded from Git.
