## 2026-10-17 - Fast Equirectangular Distance Pre-filtering for Station Selection
**Learning:** `vincenty` distance calculation on an ellipsoid is iterative and computationally expensive when called $O(N)$ times for weather stations in Buienradar feeds (~60 stations). Equirectangular projection distance squared `(dx^2 + dy^2)` is $O(1)$ fast arithmetic and accurately ranks nearest stations at local scales (such as the Netherlands). Slicing the top 3 candidates before evaluating exact `vincenty` distance preserves 100% precision while achieving an ~8x-10x performance speedup.
**Action:** When searching for nearest geographical points from a small or medium array of lat/lon points, use fast equirectangular approximation pre-filtering and only run exact geodesic algorithms (like Vincenty or Haversine) on top candidates.

## 2026-10-18 - Tuple Size vs Re-parsing Overhead in Candidate Sorting
**Learning:** Storing larger tuples `(sq, wstation, wslat, wslon)` to save re-converting `float(wstation['lat'])` on the top candidates resulted in ~20% worse performance (0.83x) due to Python's tuple allocation overhead and 4-tuple comparison cost during sorting across 50+ stations. Re-parsing string floats on only the top 3 candidates from 2-tuples `(sq, wstation)` is faster.
**Action:** In Python, keep sort keys/tuples small (2-tuples) when filtering candidate lists; defer extracting or converting secondary fields until after slicing the top candidates.

## 2026-10-19 - Lookup Table for Precipitation Intensity Exponentiation
**Learning:** Buienradar's precipitation text API returns values as integer strings from 0 to 255. Standard float parsing and floating-point exponentiation `10**((val-109)/32)` for every line (~25 lines per request) incurs unnecessary computation overhead. Pre-calculating a 256-element lookup table `_MMU_LOOKUP` and performing `int(val_str)` lookup avoids float parsing and exponentiation, speeding up forecast parsing by ~15%.
**Action:** When parsing bounded integer range domain formulas (such as 0..255 sensor/forecast values), use precalculated lookup tables instead of evaluating exponential equations per line.
