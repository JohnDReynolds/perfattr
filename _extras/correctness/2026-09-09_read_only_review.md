# Read-Only Correctness Review

**Status:** Complete September 9, 2026.

**Reviewed revision:** `9e03a69` (`main` and `origin/main` before this report was
added).

## Conclusion

No incorrect ordinary-domain financial formula was found. The Brinson-Fachler and
Brinson-Hood-Beebower methods, all three effect linkers, geometric attribution,
currency attribution, multi-period currency roll-up, hierarchy roll-up, mapping, and
consolidation calculations matched their governing specifications and independent
formula probes.

The review found three confirmed boundary defects:

| ID | Severity | Finding |
|---|---|---|
| COR-001 | Moderate | Preparation can return frames that its documented downstream calculator rejects |
| COR-002 | Low | The headerless classification CSV reader accepts a conventional header as data |
| COR-003 | Low | Out-of-range day counts are silently saturated to `int64` and can distort horizon weights |

COR-001 is the only finding likely to matter for plausible accounting-integrated
data. It fails loudly in the downstream calculation rather than returning an
incorrect attribution result, but it violates the public composition contract and
makes preparation report success for unusable output. COR-002 can add a phantom
metadata row. COR-003 requires economically impossible day counts, so its practical
risk is very small despite the silent numerical change.

No production source, test, configuration, tolerance, or threshold was changed during
this review.

## Review method

The review traced public APIs into their normalization, calculation, aggregation, and
reconciliation paths and compared them with the accepted specifications. Particular
attention was given to:

- authoritative contribution and undefined effective-return branches;
- signed and missing-side weights;
- Brinson-Fachler and Brinson-Hood-Beebower two- and three-effect formulas;
- Carino, Frongello, and Menchero effect-linking coefficients;
- logarithmic contribution consolidation;
- geometric successive-notional identities;
- market and currency log-return grids;
- multi-period log-effect addition;
- static and effective-dated classification mapping;
- calendar alignment and inclusive-day weighting;
- parent and forest-root hierarchy conservation; and
- CSV and pandas boundary normalization.

Temporary randomized probes independently restated the governing formulas rather than
calling package-private calculation helpers. They covered:

- 40 five-period, seven-identifier arithmetic cases under all four attribution
  methods and all three linkers: 480 complete policy calculations;
- 40 four-period, six-identifier geometric cases;
- 40 three-period, five-identifier four-frame currency cases;
- 100 three-month, eight-identifier quarterly preparation cases, both unmapped and
  statically mapped;
- 20 four-period hierarchy histories, rotating through the attribution methods and
  linkers and checking immediate-parent and root sums; and
- 20 four-period multi-period currency roll-ups, checking every cumulative prefix and
  identifier horizon sum.

All probes passed at the unchanged `1e-12` relative and absolute tolerance.

## Findings

### COR-001: preparation can return frames rejected by calculation

**Severity:** Moderate  
**Confidence:** Confirmed by two minimal public-API reproductions

`prepare_attribution` documents that its returned portfolio and benchmark frames can
be passed directly to `calculate_attribution`. That is not true for every input the
preparation boundary accepts.

Two distinct cases demonstrate the same contract break.

#### Case A: exact authoritative period total at or below -100%

An exact native period with two 50% weights, defined input returns of zero, and
authoritative contributions of `-0.60` and `-0.50` is accepted by preparation. Its
prepared period contribution is `-1.10`. Passing the returned frames directly to
`calculate_attribution` raises:

```text
AttributionError: portfolio input period return must be greater than -1.0
```

The preparation source-total check requires only finiteness. The calculation core
correctly requires a strictly positive period wealth base because its multi-period
linking uses `log1p`.

#### Case B: exact mapped effective return at or below -100%

An exact native period with weights `[0.50, 0.50]`, defined input returns `[0, 0]`,
and authoritative contributions `[-0.60, 0.70]` has a valid positive total return of
10%. Mapping the two rows separately produces:

```text
identifier  weight  return  contribution
X             0.5    -1.2          -0.6
Y             0.5     1.4           0.7
```

Preparation accepts this result, but `calculate_attribution` immediately rejects
`X` because every supplied input return must be greater than `-1.0`.

#### Cause

True consolidation validates final defined returns and linked period returns.
Exact-period paths are copied before that validation. This occurs both when the
complete source-period sequence equals the aligned sequence and when an exact period
is copied beside other periods that require consolidation.

This exposes a specification tension as well: the preparation specification requires
a source-period contribution total greater than `-1.0` only “when logarithmic
consolidation is required,” while the calculation specification requires that bound
for every period because calculation always performs horizon linking.

#### Recommendation

Make the public composition promise the governing rule. Validate every final prepared
reporting period, including copied exact periods, against the calculation input
domain before returning a `PreparationResult`:

- every prepared period contribution total must be finite and greater than `-1.0`;
- every defined prepared `return` must be finite and greater than `-1.0`; and
- every nonzero prepared weight must still have a defined return.

Add focused public regression tests for both cases above and align the preparation
specification with the downstream period wealth-base requirement. This should be a
small validation change; no financial formula, tolerance, or output schema needs to
change.

Relevant locations:

- `src/perfattr/prepare.py`, `prepare_attribution` return contract;
- `src/perfattr/preparation.py`, `_validate_period_totals`;
- `src/perfattr/consolidation.py`, `_validate_consolidated_values`, the complete
  exact-sequence return, and mixed exact-period copying; and
- `src/perfattr/attribution.py`, `_normalize_input` and `_validate_matched_periods`.

### COR-002: classification CSV header is accepted as metadata

**Severity:** Low  
**Confidence:** Confirmed by a minimal public-API reproduction

The classification CSV contract says the file is headerless. Supplying the ordinary
header below does not raise:

```csv
classification_identifier,classification_name
EQ,Equity
```

Instead, `read_classification_csv` returns two metadata rows, one of which is the
header text itself. The mapping CSV reader explicitly rejects its conventional static
and effective-dated headers, but the shared two-column reader used for classification
metadata checks only row width.

The result does not enter numerical attribution directly, so the usual effect is an
unused phantom display row. It could become visible if a host presents the complete
classification table or if a real classification identifier happens to equal the
header label.

#### Recommendation

Reject a normalized row equal to
`("classification_identifier", "classification_name")`, matching the documented
headerless contract and the mapping-reader behavior. Add one reader regression test.

Relevant locations:

- `src/perfattr/io.py`, `_read_pair_csv` and `read_classification_csv`; and
- `docs/preparation_specification.md`, Classification CSV contract.

### COR-003: out-of-range day counts silently change value

**Severity:** Low  
**Confidence:** Confirmed by a minimal public-API reproduction

The calculation boundary first converts `quantity_of_days` to `float64`, checks that
it is positive and integral, and then casts it to `int64`. Values above the maximum
`int64` value pass the first checks and are silently saturated to
`9223372036854775807` by the pandas cast in the reviewed environment.

For two periods with requested day counts `1e19` and `2e19`, and an identifier held at
100% only in the first period, the economically implied horizon average weight is
one third. Both day counts saturate to the same value, so the returned horizon weight
is `0.5`.

Real reporting-period day counts cannot approach this range, which makes the practical
risk negligible. It is nevertheless silent alteration of an accepted mathematical
input.

#### Recommendation

Reject day counts outside the representable positive `int64` range before conversion.
A dedicated day-count normalizer can also avoid unnecessary float conversion for
integer-typed inputs and verify exact round-trip conversion. Add a two-period
regression test proving that an out-of-range value raises instead of affecting weight
averaging.

Relevant location: `src/perfattr/attribution.py`, `_normalize_input`.

## Passed gates and positive evidence

The repository's complete current gate passed:

```text
pytest:  641 passed in 10.57s
pyright: 0 errors, 0 warnings, 0 informations
pylint:  10.00/10
git diff --check: clean
```

No skipped or expected-failure tests were found. The test suite contains extensive
hand-explained fixtures and reconciliation assertions. The randomized independent
checks additionally found no discrepancy in:

- period or horizon Brinson effects;
- Carino, Frongello, or Menchero linked total effects;
- geometric allocation, selection, and wealth ratios;
- currency allocation and selection effects on either grid; or
- quarterly weight, return, authoritative-contribution, mapping, and logarithmic
  consolidation behavior.

## Areas reviewed with no finding

- Missing identifiers are neutralized without losing authoritative contributions.
- Zero-weight, nonzero-contribution rows retain undefined effective returns and finite
  attribution effects.
- Both three-effect methods make interaction explicit while the two-effect methods
  absorb it into portfolio-weighted selection as specified.
- Frongello preserves chronological path dependence; Menchero is order independent
  and uses the continuous difference-of-powers common scale.
- Geometric period and cumulative channels reconcile multiplicatively through the
  successive-notional portfolio.
- Currency period grids and multi-period log-effect totals reconcile additively.
- Hierarchy values are direct descendant-leaf sums, not recursive recalculations, and
  parent/root evidence conserves the released additive columns.
- Effective-dated mappings use inclusive, nonoverlapping assignments and preserve the
  intended gap-versus-boundary diagnostics.
- Fixed-frequency consolidation uses gapless inclusive source coverage and
  observed-day-weighted exposures.

## Limits of this review

This is a code review plus finite dynamic sampling, not a formal proof. It did not
change code to inject faults, run external proprietary systems as oracles, assess
economic suitability of a caller's chosen exposure basis, or re-litigate already
approved product conventions. Vendor loading, accounting, holiday discovery,
classification construction, presentation, and host-adapter behavior remain outside
the portable core and outside this review.
