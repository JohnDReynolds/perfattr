# One-Time `pybrinson` Differential Cross-Check

**Status:** Completed September 9, 2026.

## Purpose and authority

This note records a one-time numerical comparison between `perfattr` and the
independent [`gghez/pybrinson`](https://github.com/gghez/pybrinson/) project. The
comparison supplements, but does not replace, `perfattr`'s primary financial
references, independently hand-calculated fixtures, production reconciliation, or
release gates.

`pybrinson` remains a comparative implementation rather than a calculation authority.
It is not a `perfattr` dependency, test dependency, CI oracle, or source of expected
fixture values. No `pybrinson` code, fixtures, expected values, or documentation text
were copied into `perfattr`.

## Pinned environment

- `perfattr==0.12.0a1`, repository commit
  `83fd82e84fe340c799fcef874c66375fbb170fb6`
- `pybrinson==1.3.1`, repository commit
  [`529b0940937caacec3f2a30609b9ce6b86316a7b`](https://github.com/gghez/pybrinson/tree/529b094)
- Python 3.14.7
- NumPy 2.5.3
- pandas 3.0.5
- relative and absolute comparison tolerance: `1e-12`
- randomized-case seed: `20260909`

The audit harness was temporary and was intentionally not added to the repository.
The exact pinned revisions, input design, tolerance, case counts, and exceptional
boundary input are recorded here so the audit's meaning does not depend on retaining
that harness.

## Comparable scope

Only mathematically equivalent contracts were compared:

- Brinson-Fachler and Brinson-Hood-Beebower single-period effects;
- the two-effect views obtained by absorbing interaction into selection;
- Carino, Frongello, and Menchero additive multi-period effect linking;
- aggregate Bacon geometric cumulative effects; and
- strict additive parent-effect hierarchy roll-up.

The deterministic cases included the repository's `three_effect_positive`,
`multi_period_linking`, and `linking_boundaries` inputs. Randomized coverage added:

- 100 single-period cases containing 2 through 10 identifiers;
- 40 histories containing 2 through 8 periods and 2 through 8 identifiers; and
- a two-level hierarchy covering four leaves, two intermediate parents, and one root.

All ordinary randomized inputs used a common identifier universe, finite returns,
normalized long-only weights, and contributions derived as weight multiplied by
return. Those restrictions isolate the mathematical overlap instead of asking
`pybrinson` to emulate `perfattr` contracts it does not support.

## Results

| Comparison area | Values compared | Failures | Largest absolute difference |
|---|---:|---:|---:|
| Single-period BF/BHB effects and totals | 10,144 | 0 | `5.551115123125783e-17` |
| Carino, Frongello, and Menchero additive linking | 2,772 | 0 | `5.995204332975845e-15` |
| Geometric cumulative effects and totals | 805 | 0 | `6.661338147750939e-16` |
| Hierarchical effect roll-up | 18 | 0 | `1.3877787807814457e-17` |
| **Total ordinary comparisons** | **13,739** | **0** | **`5.995204332975845e-15`** |

Every ordinary comparison passed the unchanged `1e-12` relative and absolute
tolerance. The largest observed difference was roughly 167 times smaller than that
tolerance.

As independent health checks around the comparison:

- the pinned `pybrinson` test suite passed all 128 tests; and
- the current `perfattr` test suite passed all 618 tests.

## Menchero equal-horizon boundary finding

One deliberately separate boundary probe reproduced the equal-horizon case already
specified and tested by `perfattr`:

| Period | Portfolio return | Benchmark return | Active return |
|---|---:|---:|---:|
| 1 | `0.20` | `0.00` | `0.20` |
| 2 | `-0.10` | `0.08` | `-0.18` |

Both paths compound to 8%:

```text
(1.20 × 0.90) - 1 = 0.08
(1.00 × 1.08) - 1 = 0.08
```

The compounded active return is therefore zero, subject only to floating-point
rounding, even though the arithmetic sum of the period active returns is 2%.
Consequently, applying only the equal-horizon common Menchero scale cannot reconcile
the result. Nonzero period corrections remain necessary.

`perfattr` calculated the required corrections and reconciled the linked total to
`2.7755575615628914e-17`, effectively zero. `pybrinson` selected its
`abs(delta) <= 1e-12` shortcut, applied a zero correction, and then correctly rejected
its own unreconciled result:

```text
linked effect sum = 0.020784609690826544
compounded excess = 0.000000000000000013877787807814457
residual           = 0.02078460969082653
```

The behavior follows the pinned implementation's `link_menchero`
[branch](https://github.com/gghez/pybrinson/blob/529b094/src/pybrinson/linking/menchero.py).
The guard that raises rather than returning an unreconciled value is sound; the
limitation is the shortcut that suppresses necessary corrections.

This is not a `perfattr` discrepancy requiring remediation. It empirically confirms
the decision in the [specification](../docs/menchero_optimized_linking_specification.md)
to retain a continuous common-scale calculation and nonzero corrections for some
equal-horizon paths.

## Deliberate exclusions

The following were not assigned false parity expectations:

- **Currency attribution:** `pybrinson` uses a combined-segment, additive-return
  Karnosky-Singer contract. `perfattr` accepts four separate market and currency
  portfolio/benchmark frames and has different effect and reconciliation boundaries.
- **Multi-period currency-effect roll-up:** there is no equivalent `pybrinson` result
  contract to compare.
- **Authoritative contributions, zero-weight charges, and unequal identifier
  universes:** `pybrinson` derives return contribution from finite weights and returns;
  it cannot represent the broader released `perfattr` accounting contract.
- **Preparation features:** source loading, portfolio selection, calendar policy,
  period alignment and consolidation, and classification mapping have no corresponding
  `pybrinson` boundary.
- **Detailed hierarchy facts:** only common additive effects were compared.
  `pybrinson` does not return `perfattr`'s rolled weights, authoritative contributions,
  linked detail, or reconciliation frames.
- **Identifier-level geometric results:** `pybrinson` exposes aggregate linked
  geometric channels rather than `perfattr`'s identifier-period detail.
- **GRAP:** `perfattr` deliberately does not implement GRAP, so support in another
  project is not a parity target.

## Conclusion

The audit provides strong independent corroboration for every tested area of genuine
overlap. It found no ordinary numerical discrepancy at `1e-12` and identified one
Menchero boundary where `perfattr`'s previously specified treatment is more complete.
No production calculation, fixture, tolerance, dependency, or CI change is warranted.
