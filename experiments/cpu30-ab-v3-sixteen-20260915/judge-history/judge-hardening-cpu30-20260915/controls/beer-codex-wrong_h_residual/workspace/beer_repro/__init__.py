"""CPU reference implementation for the BEER paper experiments."""

from .algorithms import BEER, CHOCOSGD, DSGD, D2
from .compression import compress, compressor_bits
from .graphs import mixing_matrix, spectral_gap

__all__ = ["BEER", "CHOCOSGD", "DSGD", "D2", "compress", "compressor_bits", "mixing_matrix", "spectral_gap"]
