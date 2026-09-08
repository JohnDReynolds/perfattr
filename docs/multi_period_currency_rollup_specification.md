# Multi-Period Currency Roll-Up Specification

**Status:** Accepted September 8, 2026; implementation and release-candidate evidence
complete through Roadmap 13 Step 7; `perfattr==0.12.0a1` release authorized.

This document is the accepted governing contract for the deliberately limited
multi-period currency roll-up in [roadmap 13][roadmap-13]. It supplements but does
not modify the released single-period
[`currency_attribution_specification.md`](currency_attribution_specification.md) or
any domestic attribution contract. The user explicitly approved this specification
and Roadmap 13 on September 8, 2026.

[roadmap-13]: ../_extras/perfattr_roadmap_13_multi_period_currency_rollup.md

## Methodological identity

Roadmap 12 reports continuously compounded market and currency returns and four
effects in log-return units. Those values are additive across sequential valuation
periods. The approved operation therefore calculates every cumulative and
full-horizon value by direct summation.

This is not an arithmetic effect-linking method. Carino, Frongello, Menchero, and
GRAP modify arithmetic period effects so they reconcile to a compounded arithmetic
active return. The released currency effects already reconcile to an active log
return, and log returns add through time without a smoothing coefficient.

This is also not geometric attribution. The operation does not multiply individual
effect channels or create compounding cross-products. It preserves the released
Karnosky-Singer four-channel convention exactly.

## User problem

`calculate_currency_attribution` can calculate many periods in one call, but each
period remains independent. Users still need:

- cumulative modeled market, currency, and total log returns;
- cumulative market allocation, security selection, currency allocation, and hedge
  selection;
- full-horizon effect totals by market and currency identifier; and
- explicit evidence that those values reconcile at every prefix and at the horizon.

A manual solution can accidentally average weights or returns, treat log effects as
simple returns, omit identifiers that appear during only part of the history, or
silently fill date gaps. The public operation makes the one accepted rule explicit
and auditable.

## Public API

Add a module `perfattr.currency_rollup` and export these names from the package root:

```python
def roll_up_currency_attribution(
    result: CurrencyAttributionResult,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> CurrencyAttributionRollupResult:
    ...
```

```python
@dataclass
class CurrencyAttributionRollupResult:
    market_overall_detail: pd.DataFrame
    currency_overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
    base_currency: str
```

The result fields occur in exactly that order. Returned frames are independently
owned and do not share mutable state with the source result or one another. Ordinary
direct dataclass construction stores supplied objects; it does not validate or freeze
them.

The function requires an actual `CurrencyAttributionResult`. Another object raises
`TypeError`. The tolerance follows the released positive finite non-boolean rule.
Invalid tolerance or financial content raises `AttributionError` before any partial
result is returned.

No method or linker enum is added. Direct addition is the only financially valid
policy within this result basis.

## Source-result contract

The operation consumes the five released `CurrencyAttributionResult` fields:

```text
market_detail
currency_detail
period_summary
reconciliation
base_currency
```

It does not require the original four input frames and does not recalculate the
single-period attribution formulas. It revalidates the existing result because the
source dataclass and its DataFrames are intentionally mutable after construction.

### Structural validation

Require:

- the exact released columns and canonical dtypes in all four source frames;
- at least one period;
- timezone-naive normalized dates with `from_date <= thru_date`;
- unique period-identifier keys in both detail frames;
- unique period rows in `period_summary` and source `reconciliation`;
- identical period sets across all four frames;
- non-overlapping periods in chronological order after normalization;
- finite, non-null numerical result values;
- nonempty base-currency identity without surrounding whitespace; and
- all three source reconciliation flags to be true for every period.

Input row order is not significant. The operation works from independently copied,
stably sorted frames. It must not mutate or silently repair caller frames.

### Independent financial revalidation

Stored source reconciliation flags are evidence, not authority. Recalculate at least
these released identities from the detail and summary values:

```text
market detail row total
    = market allocation + security selection

currency detail row total
    = currency allocation + hedge selection

market detail channel sums
    = period market channels
    = active market log return

currency detail channel sums
    = period currency channels
    = active currency log return

portfolio total log return
    = portfolio market + portfolio currency

benchmark total log return
    = benchmark market + benchmark currency

active total log return
    = portfolio total - benchmark total
    = active market + active currency
    = all four effect channels
```

Use the roll-up call's `reconciliation_tolerance` for this validation. A source result
created with a wider tolerance may therefore require that same explicit tolerance at
the roll-up boundary.

The operation does not rederive market premiums, currency cash returns, exposures, or
single-period effects. Those calculations remain owned by Roadmap 12.

## Period sequence and gaps

Sort distinct periods by `thru_date`, then `from_date`, using stable ordering. Periods
must not overlap. Adjacent periods need not touch.

A gap means that no return was supplied for the missing interval. The operation does
not insert a zero-return row, stretch another period, or fail merely because a caller
selected a non-contiguous observation history. Documentation must state that the
result covers the supplied periods only.

For cumulative prefix `t`:

```text
from_date = first supplied period from_date
thru_date = period t thru_date
```

Both overall-detail frames use the first supplied `from_date` and final supplied
`thru_date` for every row.

## Cumulative calculation

Let `v[t]` denote any numerical column of the released `period_summary`. For each
chronological prefix:

```text
cumulative_v[t] = sum(i=1..t, v[i])
```

Apply this rule independently to all fourteen numerical period-summary columns:

```text
portfolio_market_log_return
benchmark_market_log_return
active_market_log_return
portfolio_currency_log_return
benchmark_currency_log_return
active_currency_log_return
portfolio_total_log_return
benchmark_total_log_return
active_total_log_return
market_allocation_log_effect
security_selection_log_effect
currency_allocation_log_effect
hedge_selection_log_effect
total_log_effect
```

The list above contains fourteen numerical columns; together with `from_date` and
`thru_date`, they form the exact cumulative schema below. No average weight, average
return, day count, or synthetic period enters this calculation.

The final cumulative row is the complete supplied horizon. Do not return another
overall-summary frame containing the same values.

### Simple-return interpretation

The output remains in log-return units. A caller may convert an aggregate portfolio
or benchmark horizon log return `L` to a simple return with:

```text
simple return = exp(L) - 1
```

Do not apply `expm1` separately to effect channels and then add them. That would
destroy their additive reconciliation. Do not report a standard arithmetic active
return without separately converting portfolio and benchmark totals and subtracting
them; that value has a different additive basis from the log effects.

## Full-horizon identifier effects

For each market identifier `g`, sum these columns over every row bearing `g`:

```text
market_allocation_log_effect
security_selection_log_effect
total_log_effect
```

For each currency identifier `c`, sum:

```text
currency_allocation_log_effect
hedge_selection_log_effect
total_log_effect
```

An identifier may appear in only part of the history. Its absence contributes no
effect, and no period row is synthesized. Identifier strings are preserved exactly.

Do not report horizon weights or returns. Beginning, ending, terminal, arithmetic-
average, and geometric-average values answer different questions and none is required
to sum already calculated log effects.

## Exact result schemas

### `market_overall_detail`

```text
from_date
thru_date
market_identifier
market_allocation_log_effect
security_selection_log_effect
total_log_effect
```

### `currency_overall_detail`

```text
from_date
thru_date
currency_identifier
currency_allocation_log_effect
hedge_selection_log_effect
total_log_effect
```

### `cumulative`

```text
from_date
thru_date
portfolio_market_log_return
benchmark_market_log_return
active_market_log_return
portfolio_currency_log_return
benchmark_currency_log_return
active_currency_log_return
portfolio_total_log_return
benchmark_total_log_return
active_total_log_return
market_allocation_log_effect
security_selection_log_effect
currency_allocation_log_effect
hedge_selection_log_effect
total_log_effect
```

### `reconciliation`

```text
scope
from_date
thru_date
check
actual
expected
difference
tolerance
passed
```

Dates use `datetime64[ns]`. Identifiers, `scope`, and `check` use `string[python]`.
Every financial number and tolerance uses `float64`; `passed` uses `bool`. Frames use
zero-based `RangeIndex` values.

Overall-detail rows sort by identifier using stable ordering. Cumulative rows sort by
`thru_date`, then `from_date`. Reconciliation rows follow cumulative prefix order and
the stable check order below, followed by the six overall checks.

## Reconciliation contract

Every returned reconciliation row must pass at the requested tolerance. A failure or
non-finite result raises `AttributionError` before the result escapes.

Use `scope == "cumulative"` for each prefix and these stable checks in order:

```text
portfolio_market_rollup
benchmark_market_rollup
active_market_identity
market_effect_identity
portfolio_currency_rollup
benchmark_currency_rollup
active_currency_identity
currency_effect_identity
portfolio_total_rollup
benchmark_total_rollup
portfolio_total_components
benchmark_total_components
active_total_identity
active_total_components
total_effect_identity
```

The three `*_rollup` pairs compare the returned cumulative values with direct sums of
the source period values. The active checks compare portfolio minus benchmark. The
total-component checks compare total returns with market plus currency returns. The
effect checks compare the accepted channel sums with the corresponding active log
return.

After the cumulative rows, use `scope == "overall"` and these stable checks:

```text
market_allocation_detail
security_selection_detail
market_total_detail
currency_allocation_detail
hedge_selection_detail
currency_total_detail
```

Each overall check compares the sum of the corresponding identifier frame with the
final cumulative channel or grid total. Validate every identifier row's `total_log_effect`
against its component columns before building the reconciliation frame.

`difference` is `actual - expected`. `tolerance` records the explicit call value.
Successful results contain only true `passed` values; the frame is positive audit
evidence rather than a warning channel.

## Hand-calculated summary example

Suppose two already reconciled periods have these log-return summaries:

```text
                                      Period 1   Period 2   Horizon
portfolio market                         .056       .010      .066
benchmark market                         .040       .015      .055
active market                            .016      -.005      .011
portfolio currency                       .0325      .005      .0375
benchmark currency                       .020       .006      .026
active currency                          .0125     -.001      .0115
portfolio total                          .0885      .015      .1035
benchmark total                          .060       .021      .081
active total                             .0285     -.006      .0225
market allocation                        .002      -.002      .000
security selection                       .014      -.003      .011
currency allocation                      .004      -.0004     .0036
hedge selection                          .0085     -.0006     .0079
total effect                             .0285     -.006      .0225
```

Every horizon value is the literal sum of its two period values. At the horizon:

```text
.011 market active + .0115 currency active = .0225 total active
.000 + .011 + .0036 + .0079 = .0225 total effect
```

Implementation fixtures must derive their source periods independently from valid
four-frame Roadmap 12 inputs. Expected roll-up values must be literal hand calculations,
not values copied from the implementation under test.

### Implemented fixture provenance

The deterministic one-, two-, and three-period cases in
`tests/test_currency_rollup_calculation.py` were authored specifically for this MIT-
licensed repository from the formulas in this specification. They were not copied
from `ppar`, `pybrinson`, or another implementation. Their four input frames start
with independently selected weights and log-return facts, convert those facts to the
public simple-return inputs, and state every expected cumulative and identifier value
as a literal hand calculation. Randomized tests supplement those fixtures only by
checking the same independently stated conservation identities.

## Edge cases

The accepted contract must cover:

- one period, where cumulative values equal period values;
- two and many periods;
- exact zero returns and effects;
- negative but finite log returns;
- signed and greater-than-one source exposures already accepted by Roadmap 12;
- identifiers that start late, end early, or reappear;
- different identifier universes across different periods;
- periods with date gaps;
- row-order permutations;
- a base-currency identifier containing valid non-ASCII text;
- caller-mutated source values or false reconciliation evidence;
- non-finite input or output values;
- cumulative floating-point overflow; and
- default and explicit valid reconciliation tolerances.

No test may relax `1e-12` merely because a calculation fails. Expected values must be
constructed independently and nontrivial financial calculations must have extensive
docstrings and comments explaining intent, formulas, signs, and edge behavior.

## Accounting and presentation boundaries

The roll-up reconciles the released modeled returns. It does not claim that those
returns equal authoritative accounting returns affected by intraperiod trades,
valuation-source differences, exchange-rate timing, fees, or flows.

A future modeled-to-accounting diagnostic may accept authoritative portfolio and
benchmark base-currency returns and disclose residuals. It must not force a residual
into market allocation, security selection, currency allocation, or hedge selection.
That proposal requires its own roadmap and a decision about whether it belongs in
`perfattr` or a host such as `ppar`.

Separate interaction effects and hierarchical currency attribution also remain
outside this contract. The released interaction-absorption policy is unchanged.

## Documentation requirements

The README and public docstrings must state:

- the operation consumes a completed currency result;
- log returns and effects add directly through time;
- the final cumulative row is the complete supplied horizon;
- overall identifier rows contain effects only;
- weights and returns are never averaged;
- date gaps represent omitted observations, not zero-return periods;
- individual effects must not be converted independently with `expm1`; and
- accounting reconciliation, interactions, hierarchy, and host integration are not
  included.

## Performance boundary

Benchmark the public roll-up using Roadmap 12's normal, selected-input, monthly, and
25-year history shapes. Measure elapsed time, source-result memory, returned-result
memory, and incremental Python-traced peak allocation.

The expected implementation is direct pandas/NumPy grouping and cumulative addition.
Do not add an optimization, cache, parallel executor, or dependency without repeatable
evidence of a real bottleneck. Establish a numeric threshold only after a correct
prototype produces stable measurements.

## Compatibility and release gates

Before release:

- all functional tests pass on Python 3.11 through 3.14;
- Pyright reports no errors or warnings;
- Pylint reports no messages across `src`, `tests`, and `scripts`;
- Python lines remain within 99 characters and diff checks are clean;
- source and wheel distributions build and pass metadata and archive inspection;
- clean wheel installations import and execute the public roll-up;
- direct performance gates pass without changing an established threshold;
- all released arithmetic, geometric, hierarchy, preparation, linking, and currency
  tests remain unchanged and passing; and
- `ppar` passes its established release-candidate workflow and 500x check without a
  new roll-up adapter.

No release operation is authorized until the user reviews those results and gives
separate explicit approval.

## Primary reference and research conclusion

Karnosky and Singer use continuously compounded returns to make the market and
currency components additive. Their practical portfolio discussion also warns that
average weights and returns across multiple valuation periods may hide changes in
market and currency strategy and become increasingly tenuous as the horizon grows.

This specification therefore aggregates already calculated valuation periods and
never attempts to recreate a horizon attribution from averaged inputs.

Denis S. Karnosky and Brian D. Singer, *Global Asset Management and Performance
Attribution*, Research Foundation of the Institute of Chartered Financial Analysts,
1994.

- [Official publication page][ks-page]
- [Official monograph PDF][ks-pdf]

[ks-page]: https://rpc.cfainstitute.org/research/foundation/1994/global-asset-management-and-performance-attribution
[ks-pdf]: https://rpc.cfainstitute.org/sites/default/files/-/media/documents/book/rf-publication/1994/rf-v1994-n3-4444-pdf.pdf
