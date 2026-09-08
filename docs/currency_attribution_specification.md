# Single-Period Currency Attribution Specification

**Status:** Accepted and implemented September 8, 2026. The complete calculation,
documentation, fixture provenance, direct performance evidence, and release-candidate
gates pass for the approved `perfattr==0.11.0a1` prerelease.

This document is the accepted governing contract for the deliberately limited
currency-attribution feature in [roadmap 12][roadmap-12]. It supplements but does not
modify the released arithmetic [`specification.md`](specification.md), geometric
[`geometric_attribution_specification.md`](geometric_attribution_specification.md), or
preparation [`preparation_specification.md`](preparation_specification.md) contracts.
The user explicitly approved this specification and Roadmap 12 on September 8, 2026.

[roadmap-12]: ../_extras/perfattr_roadmap_12_currency_attribution.md

## Methodological identity

This feature is a single-period, additive Karnosky-Singer currency-attribution family.
It separates global portfolio performance into a market component based on local
asset-return premiums over local cash and a currency component based on cash returns
expressed in the investor's base currency.

The original methodology presents parallel market and currency grids. Each grid has
allocation, selection, and a cross-product. This contract combines each cross-product
with that grid's selection effect by using portfolio weights. The public result
therefore reports four channels:

```text
market allocation
security selection, including market interaction
currency allocation
hedge selection, including currency interaction
```

This document uses `market allocation` for what the monograph also describes as
market selection across countries or markets, and `currency allocation` for its
currency-selection decision. These names distinguish allocation among markets or
currencies from selection within a market or hedge instrument.

This is not an extension of domestic Brinson output. It uses different prepared facts,
return meanings, result schemas, and reconciliation identities. It is also not a new
member of `AttributionMethod` or `EffectLinkingMethod`.

## User problem

A market holding normally creates a currency exposure, but a manager may change that
exposure with cash or hedges. The portfolio's market weight and net currency weight
can therefore differ. A useful global attribution must answer two separate questions:

- Did allocation among markets and selection within them add value after removing
  local cash returns from the market comparison?
- Did allocation among currencies and selection of hedge instruments add value after
  considering local cash returns and exchange-rate movement together?

Using unhedged base-currency asset returns for the first question embeds the currency
decision in the market result. Using local asset returns without subtracting local
cash embeds a manageable cash-market return in the market decision. This contract
keeps those effects in the currency grid.

## Deliberately limited first version

The first version calculates each supplied period independently. It requires already
prepared return and exposure facts and does not:

- load prices, FX rates, holdings, cash balances, or forward transactions;
- convert price series into returns;
- infer market weights or net currency exposures;
- infer whether an exposure is market-value, notional, delta-adjusted, or another
  basis;
- price hedges or calculate forward points;
- accept authoritative contribution fields or reconcile an accounting total;
- report exchange-rate-source, valuation, transaction-timing, or other residuals;
- expose either interaction as a separate effect;
- link currency effects through time;
- roll currency effects through a hierarchy; or
- modify `ppar`.

The host accounting or preparation layer owns those responsibilities. A later roadmap
may add one only after a concrete user need, exact contract, and independent fixtures
justify it.

## Public API

Add a public function in `perfattr.currency` and export it from the package root:

```python
def calculate_currency_attribution(
    portfolio_markets: pd.DataFrame,
    benchmark_markets: pd.DataFrame,
    portfolio_currencies: pd.DataFrame,
    benchmark_currencies: pd.DataFrame,
    *,
    base_currency: str,
    reconciliation_tolerance: float = 1e-12,
) -> CurrencyAttributionResult:
    ...
```

Add and export:

```python
@dataclass
class CurrencyAttributionResult:
    market_detail: pd.DataFrame
    currency_detail: pd.DataFrame
    period_summary: pd.DataFrame
    reconciliation: pd.DataFrame
    base_currency: str
```

The fields appear in exactly that order. Returned frames are independent from caller
inputs and from one another. Ordinary dataclass construction stores supplied values;
it does not validate, copy, or freeze them.

`base_currency` is required audit metadata. It must be a nonempty string with no
leading or trailing whitespace. It is preserved exactly; `perfattr` does not maintain
an ISO currency registry or silently change case.

The tolerance retains the released finite, positive, non-boolean rule. Invalid
argument types raise `TypeError`. Invalid frame content or failed financial
reconciliation raises `AttributionError`.

No method enum is added while only one currency methodology exists.

## Return basis

Every input return is an ordinary simple period return expressed as a decimal, such as
`0.05` for 5 percent. This is the familiar convention used by the rest of `perfattr`.
Every return must be finite and strictly greater than `-1`.

The function converts each supplied return internally to a continuously compounded,
or log, return:

```text
log_return = log1p(simple_return)
```

The use of `log1p` is part of the governed calculation, not a caller responsibility or
configurable policy. It is numerically stable for returns close to zero.

Derived return and effect columns include `log_return` or `log_effect` in their names.
Supplied simple-return columns retain their ordinary `return` names. This prevents a
simple input from being mistaken for a log result.

For a modeled log return `r`, a caller may calculate its simple-return equivalent as:

```text
simple_return = exp(r) - 1
```

The function does not convert individual log effects back to simple-return values.
Applying `expm1` to every effect separately would destroy their additive identity.
Only an aggregate modeled log return has an unambiguous simple-return equivalent.

The modeled portfolio values below are weighted sums of internally derived log-return
components. They reconcile the Karnosky-Singer model exactly. They are not asserted
to equal an independently measured accounting return, which may reflect intraperiod
trading, valuation-source differences, fees, or other facts outside this contract.

## Exact input schemas

The four frames preserve the released convention that portfolio and benchmark are
separate inputs. Market and currency facts remain in different frames because their
weights are independent decision vectors and multiple markets may share one currency.
The function aligns the four frames internally; callers do not merge portfolio and
benchmark records before calculation.

### `portfolio_markets` and `benchmark_markets`

```text
from_date
thru_date
market_identifier
market_weight
local_asset_return
local_cash_return
```

Each row contains one side's facts for one market and period. `local_cash_return` is
the passive local cash reference used to remove the cash component from that side's
local asset return after both returns are converted with `log1p`.

For an aligned market and period, portfolio and benchmark must supply exactly the same
`local_cash_return`. It is one shared reference duplicated across two independent
input files, not an active portfolio decision. Exact equality prevents the
calculation from silently choosing between conflicting cash benchmarks. A host must
choose and document the cash instrument, tenor, and return convention before
constructing both frames.

Strategic cash may be an ordinary market row. When its supplied asset and reference
cash returns are equal, their converted log returns are equal and the local return
premium is zero. It receives no special numerical treatment.

### `portfolio_currencies` and `benchmark_currencies`

```text
from_date
thru_date
currency_identifier
currency_weight
base_currency_cash_return
```

Each row contains one side's facts for one currency and period. `currency_weight` is
that side's total net exposure after noncash holdings, strategic cash, and hedges.
Only the net exposure enters this calculation. A hedge notional is not required and
cannot be used to reconstruct the currency weight inside `perfattr`.

The portfolio and benchmark `base_currency_cash_return` values represent the ordinary
simple period returns of the actual and passive cash or hedge instruments selected for
that currency. The function converts both with `log1p`. When the portfolio uses the
same instrument and term as the benchmark, the supplied returns are equal and hedge
selection is zero. This common case still permits active currency allocation through
different net currency weights.

The base currency itself is an ordinary currency row when it has exposure. Its
base-currency cash return includes its local cash return and no exchange-rate change.

## Input validation and normalization

All four arguments must be pandas DataFrames and must contain exactly their governed
columns with no missing or extra column. The applicable released date meanings apply:

- dates normalize to midnight `datetime64[ns]` values;
- `from_date <= thru_date`;
- periods do not overlap within an input; and
- all four frames contain exactly the same period keys.

`quantity_of_days` is deliberately absent. The function receives already calculated
period returns and neither annualizes them nor accrues an interest rate, so elapsed or
business-day counts do not enter any governed formula. `from_date` and `thru_date`
provide all required period identity and ordering.

Identifiers normalize to `string[python]`, must be non-null and nonempty after
trimming, and must be unique within each period and frame. Portfolio and benchmark
market identifiers must form the same universe in each period. Portfolio and
benchmark currency identifiers must likewise form the same universe. Market and
currency identifiers occupy separate namespaces and need not match.

Every weight and return is a real, finite, non-boolean numeric value stored as
`float64`. Null, positive infinity, and negative infinity are invalid. Every return
must be strictly greater than `-1`, so `log1p` has a finite real result. Signed and
zero individual weights are allowed.

For every period, each of these frame-specific sums must equal `1.0` within
`reconciliation_tolerance`:

```text
sum(portfolio_markets.market_weight)
sum(benchmark_markets.market_weight)
sum(portfolio_currencies.currency_weight)
sum(benchmark_currencies.currency_weight)
```

The calculation does not renormalize a failed sum. Currency hedges normally net to
zero across currencies, so total net currency exposure remains one even when
individual exposures are negative or greater than one.

Every market or currency required by either side must be supplied as an explicit row
in both corresponding side frames. Zero weight is the representation of no exposure.
The function does not synthesize a missing side because its counterfactual return
would be unknowable.

After aligning the market frames, `local_cash_return` must be exactly equal between
portfolio and benchmark for every market and period. A mismatch raises
`AttributionError`; the function does not average the values, apply a tolerance, or
choose one side as authoritative.

Each normalized input and result detail frame is sorted stably by `thru_date`,
`from_date`, then identifier. Caller frames are never mutated.

## Notation

For market `g`, currency `c`, and period `t`:

- `wP[g,t]`, `wB[g,t]` are portfolio and benchmark market weights;
- `RP[g,t]`, `RB[g,t]` are supplied portfolio and benchmark local asset returns;
- `K[g,t]` is the supplied common local cash return;
- `rP[g,t] = log1p(RP[g,t])` and `rB[g,t] = log1p(RB[g,t])`;
- `k[g,t] = log1p(K[g,t])`;
- `pP[g,t] = rP[g,t] - k[g,t]` is the portfolio local log-return premium;
- `pB[g,t] = rB[g,t] - k[g,t]` is the benchmark local log-return premium;
- `xP[c,t]`, `xB[c,t]` are portfolio and benchmark net currency weights;
- `QP[c,t]`, `QB[c,t]` are supplied portfolio and benchmark base-currency cash
  returns; and
- `qP[c,t] = log1p(QP[c,t])` and `qB[c,t] = log1p(QB[c,t])` are their log returns.

All sums below are within one period. The period subscript is omitted where clear.

## Modeled market and currency components

The portfolio and benchmark market components are:

```text
MP = sum_g(wP[g] * pP[g])
MB = sum_g(wB[g] * pB[g])
```

The portfolio and benchmark currency components are:

```text
CP = sum_c(xP[c] * qP[c])
CB = sum_c(xB[c] * qB[c])
```

The modeled total log returns and their active difference are:

```text
TP = MP + CP
TB = MB + CB
TA = TP - TB
```

`TA` is the exact total governed by this function. No unrelated accounting residual is
forced into an attribution channel.

## Market grid

Market allocation for market `g` is the Brinson-Fachler-style comparison of active
market weight with the benchmark market's return premium relative to the benchmark
aggregate premium:

```text
market_allocation_log_effect[g] = (wP[g] - wB[g]) * (pB[g] - MB)
```

Security selection uses portfolio market weight:

```text
security_selection_log_effect[g] = wP[g] * (pP[g] - pB[g])
```

This is the sum of benchmark-weighted security selection and the market
allocation-selection cross-product:

```text
wB[g] * (pP[g] - pB[g])
+ (wP[g] - wB[g]) * (pP[g] - pB[g])
= wP[g] * (pP[g] - pB[g])
```

Therefore, interaction is present but deliberately absorbed. The row total is:

```text
market_total_log_effect[g] = market_allocation_log_effect[g]
                           + security_selection_log_effect[g]
```

Because both market-weight vectors sum to one:

```text
sum_g(market_total_log_effect[g]) = MP - MB
```

## Currency grid

Currency allocation for currency `c` compares active net currency exposure with the
benchmark currency return relative to the benchmark aggregate currency return:

```text
currency_allocation_log_effect[c] = (xP[c] - xB[c]) * (qB[c] - CB)
```

Hedge selection uses portfolio net currency weight:

```text
hedge_selection_log_effect[c] = xP[c] * (qP[c] - qB[c])
```

This absorbs the currency allocation-selection cross-product by the same algebra used
for security selection. The name describes selection of the actual cash or hedge
instrument relative to the passive instrument; it does not imply that `perfattr`
prices or identifies a hedge transaction.

The row total is:

```text
currency_total_log_effect[c] = currency_allocation_log_effect[c]
                             + hedge_selection_log_effect[c]
```

Because both currency-weight vectors sum to one:

```text
sum_c(currency_total_log_effect[c]) = CP - CB
```

## Complete four-channel identity

For every period:

```text
market_log_effect = sum_g(
    market_allocation_log_effect[g] + security_selection_log_effect[g]
)
currency_log_effect = sum_c(
    currency_allocation_log_effect[c] + hedge_selection_log_effect[c]
)

total_log_effect = market_log_effect + currency_log_effect
                 = (MP - MB) + (CP - CB)
                 = TP - TB
                 = TA
```

All market, currency, and total equalities use the same unchanged relative and
absolute `reconciliation_tolerance`. An equality failure raises `AttributionError` and
returns no partial result.

## Exact result schemas

### `market_detail`

```text
from_date
thru_date
market_identifier
portfolio_market_weight
portfolio_local_asset_return
benchmark_market_weight
benchmark_local_asset_return
local_cash_return
portfolio_local_log_return_premium
benchmark_local_log_return_premium
active_market_weight
active_local_log_return_premium
market_allocation_log_effect
security_selection_log_effect
total_log_effect
```

### `currency_detail`

```text
from_date
thru_date
currency_identifier
portfolio_currency_weight
portfolio_base_currency_cash_return
benchmark_currency_weight
benchmark_base_currency_cash_return
portfolio_base_currency_cash_log_return
benchmark_base_currency_cash_log_return
active_currency_weight
active_base_currency_cash_log_return
currency_allocation_log_effect
hedge_selection_log_effect
total_log_effect
```

### `period_summary`

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
from_date
thru_date
market_log_effect_sum
active_market_log_return
market_reconciled
currency_log_effect_sum
active_currency_log_return
currency_reconciled
total_log_effect_sum
active_total_log_return
total_reconciled
```

Dates use `datetime64[ns]`; identifiers use `string[python]`; every other numerical
column uses `float64`; and reconciliation flags use `bool`.

Detail rows sort by `thru_date`, `from_date`, and their identifier using stable
ordering. Summary and reconciliation rows sort by `thru_date` then `from_date`. Every
frame has a zero-based `RangeIndex`.

No cumulative or overall-detail frame exists. Adding one would require an approved
currency-effect linking policy rather than an ordinary sum.

## Interpretation boundaries

### Net currency exposure

The source of a currency exposure does not change the formula. A market holding,
strategic cash position, forward, future, option, or another instrument can contribute
to the net weight supplied by the host. `perfattr` receives only the chosen aggregate
exposure. The host must document the exposure basis and must not expect the core to
infer it.

### Cash

Strategic cash can appear in the market grid and also contributes to the host's net
currency exposure. This is not double counting: its return premium belongs to the
market decision, while the cash return expressed in base currency belongs to the
currency decision. Cash is not a hidden residual.

### Hedge selection

Hedge selection measures return differences between actual and passive currency cash
or hedge instruments. If a host has only net currency weights and passive currency
returns, it may set the supplied portfolio and benchmark base-currency cash returns
equal. The result then reports zero hedge selection without fabricating active
instrument data.

### Fees, financing, and flows

This first input contract has no authoritative contribution field and no undefined
effective-return convention. Fees, financing, and external flows remain in the host's
accounting return and are not inserted into these four modeled effects. Adding an
accounting residual merely to force agreement would conceal rather than explain a
boundary difference.

## Independent test requirements

Expected results must be constructed independently from literal inputs, with extensive
docstrings and comments explaining every nontrivial calculation, financial meaning,
sign convention, and reconciliation step. Production output, `ppar`, `pybrinson`, or
another library must not generate expected values.

At minimum, fixtures cover:

1. two markets and two currencies with all four effects nonzero;
2. a benchmark-relative market allocation sign that differs from absolute-return BHB;
3. security selection with interaction visibly absorbed into portfolio weighting;
4. currency allocation with equal actual and passive cash returns and zero hedge
   selection;
5. active hedge selection with zero active currency weight;
6. an unhedged portfolio whose market and currency weights agree;
7. partially hedged, fully hedged, and cross-hedged net exposures;
8. signed and greater-than-one currency weights that still sum to one;
9. strategic cash with a zero local return premium;
10. the base currency as an ordinary currency row;
11. multiple independent periods with no linking or cumulative output;
12. invalid schemas, periods, identifiers, null or nonfinite values, returns at or
    below `-1`, weight sums, and metadata;
13. mismatched portfolio/benchmark identifier universes, conflicting local cash
    references, and mismatched period sets across the four frames;
14. caller nonmutation and deterministic row ordering across all four inputs; and
15. randomized market, currency, and complete-identity checks at `1e-12`.

At least one fixture should reproduce a small, independently recalculated subset of
the primary monograph's hypothetical example. Because the source reports log returns,
the fixture must convert those source values with `expm1` into ordinary input returns
and independently verify that the governed `log1p` transformation recovers the source
basis. Numerical facts may be transcribed only after documenting their source and
checking the project's MIT outbound-license requirements. Most fixtures should use
original project-authored numbers to keep provenance simple.

## Implemented fixture provenance

The calculation tests use original project-authored inputs and literal expectations
evaluated independently from this specification. Their docstrings show the nontrivial
premium, allocation, selection, hedge, and reconciliation arithmetic. No production
output, `ppar`, `pybrinson`, or another implementation generated an expected value.

One deliberately small primary-source check uses Australia, Japan, and the United
States from Karnosky and Singer (1994), Table 21, printed page 66. It transcribes only
the table's passive weights, active weights, and U.S.-dollar cash returns. The three
selected weights are divided by their respective subset totals because the complete
table contains twenty currencies and its displayed values are rounded. Reported
returns are not changed: `expm1` converts the source log returns to the public simple-
return input basis, and the test independently requires `log1p` to recover the source
values. Actual and passive instrument returns are equal because the table supplies
one cash-return series, so hedge selection is independently expected to be zero.

These limited numerical facts and the cited methodology are used for verification;
no source code, fixture, table image, or prose was copied into the MIT-licensed
package. The remaining currency tests and every market-grid fixture are original
project material.

## Performance and quality gates

- Keep pandas and NumPy as the only runtime dependencies.
- Measure elapsed time and peak memory directly for realistic selected-input sizes.
- Establish thresholds only after the correct implementation produces repeatable
  evidence; once established, do not relax them without explicit approval.
- Require all supported-Python tests, Pyright/Pylance, Pylint, line-length, build,
  metadata, clean-wheel installation, and public-import checks to pass.
- Run all released arithmetic, geometric, hierarchy, and preparation regression tests.
- Verify `ppar` compatibility separately without importing it into `perfattr` or adding
  a currency adapter.
- Do not weaken a tolerance, invariant, test, or warning policy to make a gate pass.

## Compatibility contract

This feature adds a separate module, function, result type, and schemas. It does not
change:

- either released attribution function;
- `AttributionResult` or `GeometricAttributionResult`;
- `AttributionMethod` or `EffectLinkingMethod`;
- arithmetic, geometric, preparation, or hierarchy inputs and outputs;
- existing defaults, tolerances, or null policies;
- dependency metadata; or
- `ppar` output or integration behavior.

Any later accounting-integrated, multi-period, separate-interaction, hierarchical, or
host-adapter extension requires another approved compatibility plan.

## Primary reference and research conclusions

Denis S. Karnosky and Brian D. Singer, *Global Asset Management and Performance
Attribution*, Research Foundation of the Institute of Chartered Financial Analysts,
1994.

The primary-source review supports these contract decisions:

- local asset-return premiums separate market decisions from local cash effects;
- base-currency cash returns combine the local cash and currency components relevant
  to manageable currency exposure;
- market and net currency weights are distinct decision vectors;
- only total net currency exposures are needed for the attribution calculation;
- unhedged, partially hedged, fully hedged, and cross-hedged policies fit one boundary;
- the market and currency grids each contain allocation, selection, and interaction;
- the monograph demonstrates a single-period calculation before discussing practical
  multiperiod residuals; and
- its simplifying derivation uses continuously compounded returns for additive
  decomposition.

- [Official publication page][ks-page]
- [Official monograph PDF][ks-pdf]

[ks-page]: https://rpc.cfainstitute.org/research/foundation/1994/global-asset-management-and-performance-attribution
[ks-pdf]: https://rpc.cfainstitute.org/-/media/documents/book/rf-publication/1994/rf-v1994-n3-4444-pdf.pdf
