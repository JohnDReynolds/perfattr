# perfattr Roadmap 12: Single-Period Currency Attribution

**Status:** Implementation and release-candidate gates complete September 8, 2026.
Release `perfattr==0.11.0a1` is explicitly authorized and in progress under Step 8.

This roadmap promotes the currency-attribution candidate from roadmap 3. Its accepted
governing contract is
[`docs/currency_attribution_specification.md`][currency-spec].

[currency-spec]: ../docs/currency_attribution_specification.md

## Objective

Add one opt-in, single-period Karnosky-Singer currency-attribution family. Separate
market and currency decisions without changing the released domestic Brinson APIs,
schemas, defaults, or arithmetic and geometric methodologies.

The approved prerelease target is `perfattr==0.11.0a1`.

## User problem and corrected feature identity

A global portfolio can choose both where to invest and which currencies to hold.
Attributing market decisions from unhedged base-currency returns confounds those two
choices. Attributing them from local returns alone also leaves local cash-rate effects
inside the market decision even though those effects are part of the manageable
currency exposure.

Karnosky and Singer separate:

- market returns into local asset-return premiums over local cash; and
- currency returns into local cash returns expressed in the investor's base currency.

Their full attribution grids contain allocation, selection, and an interaction term on
both the market and currency sides. The shorthand "four-effect Karnosky-Singer" is
therefore incomplete unless the interaction policy is stated. This proposal reports
four channels by absorbing each grid's interaction into its portfolio-weighted
selection channel:

1. market allocation;
2. security selection, including market interaction;
3. currency allocation; and
4. hedge selection, including currency interaction.

This matches `perfattr`'s established compact selection convention while keeping the
currency family separate. Documentation must call it a four-channel convention, not
claim that the original monograph omitted the two cross-products.

## Smallest useful design

The first version accepts four already prepared, period-level DataFrames: separate
portfolio and benchmark market frames and separate portfolio and benchmark currency
frames. This preserves `perfattr`'s established side-separated input boundary while
recognizing that market weights and currency weights are different decision vectors.
Hosts supply net currency exposures after holdings, cash, and hedges. `perfattr`
neither reconstructs those exposures nor needs transaction-level forward-contract
data.

The calculation accepts ordinary decimal period returns and converts them internally
with `log1p` to the continuously compounded basis used by the primary methodology.
Callers therefore use the same familiar return convention as the rest of `perfattr`,
while result schemas identify every derived log-return value and log effect explicitly.
The first version calculates each supplied period independently and does not link
effects through time. Period identity and ordering use `from_date` and `thru_date`; no
unused day-count field is carried through the inputs or results.

## Scope boundary

Roadmap 12 owns only:

- a public `calculate_currency_attribution` function accepting separate prepared
  portfolio and benchmark market and currency frames;
- one separate `CurrencyAttributionResult` boundary;
- an explicit base-currency identity;
- market return premiums derived after converting local asset and local cash returns;
- net portfolio and benchmark currency exposures supplied by the caller;
- supplied base-currency cash returns converted for actual and passive strategies;
- four reported channels under the interaction-absorption policy above;
- exact modeled-return and effect reconciliation for each period;
- deterministic schemas, strict validation, and caller nonmutation;
- independently hand-calculated fixtures with extensive financial explanations;
- direct-core correctness, typing, lint, performance, and packaging gates; and
- verification that all released calculations and `ppar` behavior remain unchanged.

Roadmap 12 does not add:

- source loading, FX-rate retrieval, forward pricing, or return conversion from prices;
- inference of currency exposure from holdings, cash, derivatives, or hedge trades;
- a hedge optimizer, transaction-cost model, or choice of exposure basis;
- authoritative accounting contributions or a balancing residual;
- valuation-source, intraperiod-trading, or exchange-rate-source residuals;
- separate market or currency interaction columns;
- multi-period currency-effect linking;
- hierarchical currency attribution;
- currency attribution inside `calculate_attribution`, `AttributionMethod`, or
  `EffectLinkingMethod`;
- changes to any released result frame;
- a `ppar` adapter or presentation change;
- a generic method registry or plugin framework; or
- another runtime dependency.

## Approved public boundary

```python
result = calculate_currency_attribution(
    portfolio_markets,
    benchmark_markets,
    portfolio_currencies,
    benchmark_currencies,
    base_currency="USD",
    reconciliation_tolerance=1e-12,
)
```

The market frames carry each side's market weights, local asset returns, and local
cash references. The currency frames carry each side's net currency weights and
base-currency cash returns. Portfolio and benchmark frames use identical schemas, as
they do at the released calculation boundary.

The two market sides must supply the same local cash reference for each aligned market
and period. The market universes and currency universes must also match explicitly;
zero weight represents a side with no exposure. The core does not synthesize a
missing counterfactual return.

The result owns independent values in this order:

```python
@dataclass
class CurrencyAttributionResult:
    market_detail: pd.DataFrame
    currency_detail: pd.DataFrame
    period_summary: pd.DataFrame
    reconciliation: pd.DataFrame
    base_currency: str
```

Do not add a methodology enum until a second approved currency methodology creates a
real selection problem.

## Approved financial policy

For each period, market `g`, and currency `c`, define:

```text
rP[g] = log1p(portfolio local asset return)
rB[g] = log1p(benchmark local asset return)
k[g]  = log1p(local cash return)
qP[c] = log1p(portfolio base-currency cash return)
qB[c] = log1p(benchmark base-currency cash return)

pP[g] = rP[g] - k[g]
pB[g] = rB[g] - k[g]
```

Portfolio and benchmark market weights each sum to one. Portfolio and benchmark net
currency weights each sum to one; signed individual exposures are permitted. The
four effects are:

```text
market allocation log effect[g] =
    (wP[g] - wB[g]) * (pB[g] - benchmark market premium)
security selection log effect[g] = wP[g] * (pP[g] - pB[g])

currency allocation log effect[c] =
    (xP[c] - xB[c]) * (qB[c] - benchmark currency return)
hedge selection log effect[c] = xP[c] * (qP[c] - qB[c])
```

Portfolio-weighted security and hedge selection absorb their respective interaction
terms. The four period totals are reported in log-return units and reconcile
additively to the difference between the portfolio's and benchmark's modeled total
log returns. The governing specification defines the exact schemas, validation, null
behavior, terminology, and identities.

## Compatibility plan

- Do not add, remove, rename, reorder, or reinterpret any released result column.
- Do not change `calculate_attribution`, `calculate_geometric_attribution`, their
  result types, enums, defaults, or reconciliation identities.
- Keep currency inputs and outputs under separately named boundaries.
- Retain the unchanged `1e-12` default relative and absolute reconciliation tolerance.
- Keep pandas and NumPy as the only runtime dependencies.
- Do not require `ppar` changes. Any later host adoption needs separately approved
  scope after the portable contract is released and verified.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 8, 2026.

- Approve the primary-source correction to the four-channel identity.
- Approve ordinary decimal return inputs and explicit internal `log1p` conversion.
- Approve four side-separated portfolio and benchmark input frames.
- Approve net currency exposure as a caller-supplied fact.
- Approve portfolio-weighted interaction absorption on both attribution grids.
- Approve independent period calculation with no multi-period linker.
- Approve the exact result schemas, unchanged released APIs, unchanged `ppar`, and the
  `0.11.0a1` target.

**Gate:** No source, test, fixture, version, or public API implementation begins before
explicit user approval of this roadmap and its governing specification.

**Approval evidence:** On September 8, 2026, the user explicitly approved Roadmap 12
and its governing specification. This approval includes the primary-source correction
to the four-channel identity; ordinary decimal return inputs with internal `log1p`
conversion; four side-separated input frames; caller-supplied net currency exposure;
portfolio-weighted interaction absorption; independent period calculation without a
multiperiod linker; exact result schemas; unchanged released APIs and `ppar`; and the
`0.11.0a1` prerelease target.

**Gate:** Passed. Step 2 is authorized; later steps remain dependency-gated.

### 2. Establish the public identity and exact schemas

**Status:** Complete September 8, 2026.

- Add and export `CurrencyAttributionResult` and
  `calculate_currency_attribution`.
- Establish exact input and output schemas, dtypes, ordering, and ownership tests.
- Add strict argument and direct-construction tests.
- Temporarily reject otherwise valid calculations until normalization and the
  financial helper pass independent tests.

**Gate:** Identity and schema tests pass, the temporary guard cannot be bypassed, and
no released API or schema changes.

**Implementation evidence:** `CurrencyAttributionResult` and
`calculate_currency_attribution` are exported from `perfattr.currency` and the package
root. The result has exactly the five approved fields in order and remains separate
from `AttributionResult` and `GeometricAttributionResult`; no methodology enum was
added.

Dedicated constants establish the exact shared market-input schema, shared
currency-input schema, and four output schemas. The tests record their canonical date,
identifier, numerical, and boolean dtypes; zero-based indexes; ordinary direct-
construction ownership; the explicit simple-return input names; the explicit
log-return and log-effect output names; and the deliberate absence of
`quantity_of_days`.

The staged function strictly requires four pandas inputs, a nonempty unpadded
base-currency string, and the released positive finite, non-boolean tolerance. Every
call that passes those public argument checks reaches an unconditional
`NotImplementedError` before input-content normalization or financial calculation,
without mutating any caller frame. The accepted six-parameter public signature has a
narrowly documented Pylint design exception; no project-wide lint threshold changed.

**Gate:** Passed. All 513 tests pass, including 28 focused currency-boundary tests.
Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages across
`src`, `tests`, and `scripts`; the complete Python line-length check and
`git diff --check` report no errors. No released calculation, result schema, enum,
default, version, dependency, tolerance, threshold, or invariant changed.

Step 3 is authorized; later steps remain dependency-gated.

### 3. Normalize and validate prepared currency inputs

**Status:** Complete September 8, 2026.

- Validate the exact four market and currency input schemas.
- Validate date-based period identity, identifier uniqueness, finite returns greater
  than `-1`, weight totals, matching side universes, common local cash references, and
  matching market/currency period sets.
- Preserve signed market and currency exposures while enforcing each side's unit-sum
  identity.
- Normalize deterministic dtypes and ordering without mutating caller frames.
- Reject null returns rather than inventing missing local cash, market, or hedge facts.

**Gate:** Focused boundary and randomized validation tests pass with no partial result
escaping on invalid input.

**Evidence:** All four inputs are independently copied and normalized to exact schemas,
canonical dtypes, and deterministic ordering. Validation covers dates, identifiers,
finite simple returns greater than `-1`, signed unit-sum weights, duplicate and
overlapping periods, exact four-frame period alignment, matching side universes, and
exact portfolio/benchmark local-cash references. Invalid inputs fail before the
temporary financial guard, while valid inputs cannot yet return a partial result. All
551 tests pass, including 66 focused currency tests and a randomized case with 24
periods and signed exposures. Pyright reports no errors or warnings; Pylint reports
10.00/10 with no messages across `src`, `tests`, and `scripts`; the complete Python
line-length check and `git diff --check` report no errors. No released calculation,
result schema, enum, default, version, dependency, tolerance, threshold, or invariant
changed.

Step 4 is authorized; later steps remain dependency-gated.

### 4. Implement and independently verify the market grid

**Status:** Complete September 8, 2026.

- Derive portfolio and benchmark local return premiums from the common cash reference.
- Calculate market allocation and portfolio-weighted security selection.
- Cover zero, signed, and absent economic exposures represented by explicit zero-weight
  rows.
- Explain every nontrivial fixture and construct literal expected values independently.

**Gate:** Market effects reconcile exactly within the unchanged tolerance for hand
calculations and randomized cases.

**Evidence:** The internal market grid converts ordinary simple asset and common-cash
returns with `log1p`, derives local log-return premiums, calculates
Brinson-Fachler-style market allocation and portfolio-weighted security selection,
and reconciles their total to the modeled active market log return. Independently
calculated literal expectations cover ordinary, negative, and explicit zero market
weights, including a zero-weight market whose selection effect remains zero. A
36-period randomized signed-weight fixture verifies the aggregate identity directly,
and finite inputs whose weighted calculation overflows are rejected without returning
a partial result. All 556 tests pass, including 71 focused currency tests. Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`,
`tests`, and `scripts`; the complete Python line-length check and `git diff --check`
report no errors. No released calculation, result schema, enum, default, version,
dependency, tolerance, threshold, or invariant changed.

Step 5 is authorized; later steps remain dependency-gated.

### 5. Implement and independently verify the currency grid

**Status:** Complete September 8, 2026.

- Calculate currency allocation and portfolio-weighted hedge selection from net
  currency exposures.
- Cover unhedged, partially hedged, fully hedged, and cross-hedged configurations using
  explicit net exposures.
- Verify the zero hedge-selection case when actual and passive cash returns match.
- Reconcile both grids to the four-channel period total.

**Gate:** Market, currency, and complete modeled-return identities pass independently
at `1e-12`, including signed-exposure and randomized tests.

**Evidence:** The currency grid converts each side's ordinary base-currency cash
returns with `log1p`, calculates benchmark-relative currency allocation and portfolio-
weighted hedge selection, and reconciles their sum to the modeled active currency log
return. The public calculation now combines the independently reconciled market and
currency grids into the accepted four-channel period summary and three explicit
reconciliation identities. Original literal fixtures cover all four nonzero channels,
equal actual/passive returns, active hedge selection at zero active currency weight,
zero, signed, and greater-than-one exposures, and unhedged, partially hedged, fully
hedged, and cross-hedged configurations. A three-country subset of Karnosky and Singer
(1994), Table 21, converts reported log returns with `expm1` and recovers them with
`log1p`; selected weights are transparently rescaled within the subset. A 48-period
randomized signed-exposure fixture verifies currency and complete identities directly,
and currency-grid overflow returns no partial result. All 566 tests pass, including 81
focused currency tests. Pyright reports no errors or warnings; Pylint reports 10.00/10
with no messages across `src`, `tests`, and `scripts`; the complete Python line-length
check and `git diff --check` report no errors. No released domestic calculation,
result schema, enum, default, version, dependency, tolerance, threshold, or invariant
changed.

Step 6 is authorized; later steps remain dependency-gated.

### 6. Complete documentation and direct-core performance evidence

**Status:** Complete September 8, 2026.

- Document the simple-return input basis, log-effect output basis, exposure boundary,
  effect interpretation, and limitations in the README and public docstrings.
- Add a small end-to-end example whose expected effects are derived by hand.
- Record fixture provenance and the primary financial reference.
- Benchmark realistic selected-input sizes for elapsed time and peak memory.
- Establish performance thresholds only after repeatable evidence from the correct
  implementation.

**Gate:** Documentation, provenance, examples, and repeatable benchmark evidence are
complete without adding a runtime dependency.

**Evidence:** The README now lists the separate currency family, explains the four
side-specific input frames, simple-return inputs, log-effect outputs, caller-supplied
net-exposure boundary, absorbed interactions, and deliberate omissions, and includes
a two-market/two-currency example with all four hand-derived effects. The public
docstring records the same return basis, exposure ownership, interaction policy, and
absence of linking, hierarchy, exposure inference, and accounting residuals. The
governing specification and fixture-provenance notes document all original expected
values and the limited Karnosky-Singer Table 21 transcription, including subset-weight
rescaling and the `expm1`/`log1p` basis check.

The direct public-boundary benchmark uses the four established market-history shapes
with twenty currency rows per period. Two consecutive five-sample runs on Apple arm64,
Python 3.11.9, pandas 3.0.5, and NumPy 2.4.6 produced paired medians of 0.0458/0.0439,
0.1079/0.1082, 0.1659/0.1671, and 0.0797/0.0776 seconds. Prepared inputs ranged from
1.6 to 26.2 MiB, results from 1.3 to 21.5 MiB, and incremental Python-traced peak
allocation from 3.5 to 64.2 MiB. The observations are repeatable and support the
simple pandas/NumPy implementation. They do not justify a machine-specific numeric
threshold; the direct Step 7 performance gate is successful completion of all four
deterministic workloads through the public, production-reconciled boundary.

All 566 tests pass. Pyright reports no errors or warnings; Pylint reports 10.00/10
with no messages across `src`, `tests`, and `scripts`; the complete Python line-length
check and `git diff --check` report no errors. Runtime dependencies remain pandas and
NumPy. No released domestic calculation, result schema, enum, default, version,
dependency, tolerance, threshold, warning, or invariant changed.

Step 7 is authorized; Step 8 remains dependency-gated and requires separate user
approval.

### 7. Run compatibility and release-candidate gates

**Status:** Complete September 8, 2026.

- Run the complete functional suite on every supported Python version.
- Require clean Pyright/Pylance and Pylint output and enforce the 99-character limit.
- Build the sdist and wheel, validate metadata, install the wheel into a clean
  environment, and smoke-test public imports and a representative calculation.
- Run the direct currency performance gates established in Step 6.
- Verify all released arithmetic, geometric, hierarchy, and preparation behavior.
- Verify the existing `ppar` integration without adding a currency adapter.

**Gate:** The complete release-candidate gate passes without relaxing any tolerance,
threshold, invariant, warning policy, or compatibility requirement.

**Evidence:** The complete 566-test suite passes in isolated Python 3.11.9, 3.12.1,
3.13.1, and 3.14.7 environments. This includes every released arithmetic,
geometric, hierarchy, preparation, and linking test together with all 81 focused
currency tests. Pyright reports no errors or warnings, Pylint reports 10.00/10 with
no messages across `src`, `tests`, and `scripts`, and the complete Python line-length
check and `git diff --check` report no errors.

A fresh source distribution and universal wheel build successfully from the source
tree at the unchanged prerelease version `0.10.0a1`; Twine validates both artifacts.
Archive inspection confirms the currency module, tests, benchmark, governing
specification, fixture provenance, license, README, and project metadata are present
as applicable. Clean wheel installations under all four supported Python versions
pass dependency checks, import `perfattr` from `site-packages`, report the built
version, and complete the same representative public currency calculation with all
three reconciliation flags passing.

The direct currency performance gate completes all four deterministic public-boundary
workloads with production reconciliation active. The release-candidate observation
medians are 0.0475, 0.1230, 0.1728, and 0.0837 seconds, and incremental Python-traced
peak allocation remains 3.5, 32.2, 64.2, and 16.6 MiB. No machine-specific numeric
threshold is introduced.

Inspection confirms that `ppar` neither imports nor calls the new currency boundary;
its adapter continues to call only the released arithmetic boundary. The exact
`0.11.0a1` candidate wheel was installed without dependencies into `ppar`'s Python 3.12.1
release-candidate environment, where `pip check` passes. The complete established
`ppar` gate passes 305 tests and 477 subtests, all static, documentation, image,
package, wheel, and installed-demo checks, and its unchanged 500x workflow. That
workflow retains large-site equivalence and observes 1.074x large-site and 2.054x
selected-input elapsed-time ratios without numeric thresholds; long history observes
1.470x, below the unchanged 1.58x warning and 1.65x failure boundaries. No `ppar`
source or pre-existing user worktree change was altered.

No released domestic calculation, schema, enum, default, version, dependency,
tolerance, threshold, warning, invariant, adapter call, or presentation behavior
changed.

Step 8 was separately authorized after the user reviewed this evidence.

### 8. Release `perfattr==0.11.0a1`

**Status:** In progress; explicitly authorized September 8, 2026.

- Update the version and release documentation for `0.11.0a1`.
- Commit and push only after the user reviews the final evidence.
- Tag, create a GitHub prerelease, publish to PyPI, and verify the public artifact only
  after explicit release approval.

**Gate:** Public release verification succeeds from a clean environment.

**Approval evidence:** On September 8, 2026, after reviewing the complete Step 7
evidence, the user explicitly instructed the project to proceed with this release.
That approval authorizes the version update, commit, push, annotated tag, GitHub
prerelease, trusted PyPI publication, and public-package verification described above.

**Prepublication evidence:** The package and its public version test identify
`perfattr==0.11.0a1`. The README, governing specification, and feature backlog identify
single-period currency attribution as the release candidate. The exact versioned
wheel passes dependency checks, imports from `site-packages`, and passes all 566 tests
under Python 3.11.9, 3.12.1, 3.13.1, and 3.14.7. The final complete `ppar` gate against
that wheel passes with the unchanged integration boundary and thresholds.

An isolated Hatchling build produced `perfattr-0.11.0a1.tar.gz` and the universal
`perfattr-0.11.0a1-py3-none-any.whl`; Twine accepts both artifacts. The wheel SHA-256
is `ad6a24a3eae0bcfc83205569270afaa04219785acb68907b6bb1de44ce45e30f`; the source-
distribution SHA-256 is
`ec5e0d34ba4b35da7296858147730be5ddf333f31d83c429931b5c3edd80036e`.
Metadata and archive inspection confirm the MIT license, Python 3.11 minimum, pandas
and NumPy runtime dependencies, universal wheel, currency source, benchmark, tests,
specification, and fixture-provenance documentation.

At this checkpoint, neither the remote tag nor GitHub release `v0.11.0a1` exists, and
the public PyPI project does not contain `0.11.0a1`. No release operation preceded the
explicit approval recorded above.

## Primary methodology reference

Denis S. Karnosky and Brian D. Singer, *Global Asset Management and Performance
Attribution*, Research Foundation of the Institute of Chartered Financial Analysts,
1994. The methodology review used the publisher's official monograph, especially its
market/currency return decomposition, parallel attribution grids, interaction terms,
net currency-exposure discussion, and single-period example.

- [Official publication page][ks-page]
- [Official monograph PDF][ks-pdf]

[ks-page]: https://rpc.cfainstitute.org/research/foundation/1994/global-asset-management-and-performance-attribution
[ks-pdf]: https://rpc.cfainstitute.org/-/media/documents/book/rf-publication/1994/rf-v1994-n3-4444-pdf.pdf
