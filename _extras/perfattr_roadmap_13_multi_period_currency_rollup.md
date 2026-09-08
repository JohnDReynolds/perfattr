# perfattr Roadmap 13: Multi-Period Currency Roll-Up

**Status:** Complete September 8, 2026. Released in `perfattr==0.12.0a1`.

This roadmap promotes the next currency-attribution candidate from roadmap 3. Its
governing contract is
[`docs/multi_period_currency_rollup_specification.md`][currency-rollup-spec].

[currency-rollup-spec]: ../docs/multi_period_currency_rollup_specification.md

## Objective

Add one post-calculation operation that sums the released currency attribution's
period log returns and log effects into cumulative prefixes and full-horizon
identifier totals. Preserve the released single-period calculation and every other
public API, schema, default, and methodology.

The prerelease target is `perfattr==0.12.0a1`.

## User problem and feature identity

Roadmap 12 calculates and reconciles every supplied period independently. A user can
inspect a multi-period history, but the result does not provide cumulative or
full-horizon currency effects. Manually grouping frames is easy to do incorrectly,
especially if weights or returns are averaged across periods.

No smoothing or compounding policy is required for the effects. Roadmap 12 reports
continuously compounded returns and effects in log-return units. Sequential log
returns and their additive effects therefore roll up by direct summation:

```text
horizon log return = sum of period log returns
horizon log effect = sum of period log effects
```

This operation is a log-effect roll-up, not Carino, Frongello, Menchero, GRAP, or
geometric effect linking. It does not recalculate attribution from average weights or
returns and does not convert individual effects to simple returns.

## Smallest useful design

Add one function that accepts a completed `CurrencyAttributionResult`:

```python
rollup = roll_up_currency_attribution(
    result,
    reconciliation_tolerance=1e-12,
)
```

Return one separate result type:

```python
@dataclass
class CurrencyAttributionRollupResult:
    market_overall_detail: pd.DataFrame
    currency_overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    reconciliation: pd.DataFrame
    base_currency: str
```

`market_overall_detail` and `currency_overall_detail` contain only dates,
identifiers, and additive log effects. They deliberately omit averaged or terminal
weights and returns. `cumulative` contains one chronological prefix row per input
period. Its final row is the complete horizon, so a separate overall-summary frame
would be redundant.

The operation revalidates the portions of the supplied result on which it relies.
Ordinary dataclass construction and caller mutation mean that a value bearing the
correct Python type is not automatically trusted as valid financial output.

## Scope boundary

Roadmap 13 owns only:

- public `CurrencyAttributionRollupResult` and
  `roll_up_currency_attribution` identities;
- exact schemas for two full-horizon identifier-effect frames, one cumulative frame,
  and one reconciliation frame;
- direct chronological summation of released period log returns and effects;
- direct summation of market effects by market identifier and currency effects by
  currency identifier;
- preservation of identifiers that appear in only part of the history;
- validation of exact source schemas, dates, period sets, finite values, effect
  components, and released reconciliation evidence;
- cumulative and full-horizon reconciliation at the unchanged `1e-12` tolerance;
- deterministic ordering, caller nonmutation, independent hand calculations,
  documentation, and direct-core performance evidence; and
- verification that released calculations and `ppar` remain unchanged.

Roadmap 13 does not add:

- another currency-attribution calculation or methodology;
- recalculation from average, beginning, ending, or terminal weights and returns;
- Carino, Frongello, Menchero, GRAP, or geometric linking of currency effects;
- simple-return values for individual effects;
- separate market or currency interaction columns;
- hierarchical market or currency roll-up;
- authoritative accounting returns, an accounting residual, or external-flow
  attribution;
- spot, forward, carry, transaction-cost, or hedge-instrument decomposition;
- exposure inference, FX retrieval, source loading, presentation, or a `ppar`
  adapter;
- a method enum, generic roll-up registry, plugin framework, or callback; or
- another runtime dependency.

## Public boundary

```python
def roll_up_currency_attribution(
    result: CurrencyAttributionResult,
    *,
    reconciliation_tolerance: float = 1e-12,
) -> CurrencyAttributionRollupResult:
    ...
```

The source result may contain one or more non-overlapping periods. Gaps remain gaps;
the operation neither invents zero-return periods nor claims that unsupplied dates
were observed. The cumulative `from_date` is the first included period's
`from_date`, and each `thru_date` is the current prefix endpoint.

The function accepts no start date, end date, frequency, linker, methodology, or
hierarchy argument. A caller selects and calculates the desired period history before
requesting this roll-up.

## Financial policy

For chronological periods `t = 1 ... T`, each cumulative log-return or log-effect
value is:

```text
cumulative_value[t] = sum(i=1..t, period_value[i])
```

The same rule applies independently to:

- portfolio, benchmark, and active market log returns;
- portfolio, benchmark, and active currency log returns;
- portfolio, benchmark, and active total log returns;
- market allocation and security-selection log effects;
- currency allocation and hedge-selection log effects; and
- total log effect.

For market identifier `g` and currency identifier `c`:

```text
overall market effect[g] = sum_t(period market effect[g,t])
overall currency effect[c] = sum_t(period currency effect[c,t])
```

An identifier absent from a period contributes nothing in that period. No row is
synthesized and no missing return is inferred.

Every cumulative prefix must retain the released identities:

```text
active market log return = portfolio market - benchmark market
                         = market allocation + security selection

active currency log return = portfolio currency - benchmark currency
                           = currency allocation + hedge selection

active total log return = portfolio total - benchmark total
                        = active market + active currency
                        = all four effect channels
```

The overall identifier frames must sum to the final cumulative channel totals. The
governing specification defines the exact schemas, checks, dtypes, and ordering.

## Compatibility plan

- Do not add fields or columns to released `CurrencyAttributionResult` frames.
- Do not change `calculate_currency_attribution`, its formulas, input contract,
  output schemas, base-currency behavior, or reconciliation evidence.
- Keep the new frames under a separate result type and function.
- Do not change domestic arithmetic, geometric, hierarchy, preparation, or linking
  behavior.
- Retain the finite positive non-boolean tolerance rule and unchanged `1e-12`
  default.
- Keep pandas and NumPy as the only runtime dependencies.
- Require no `ppar` change. A later host adapter needs separate approval.

## Implementation sequence

### 1. Approve the contract

**Status:** Complete September 8, 2026.

- Approve direct addition as the only multi-period policy.
- Approve the post-calculation source boundary and separate result type.
- Approve exact schemas and the omission of averaged weights and returns.
- Approve one-period behavior, gap behavior, identifier disappearance, and cumulative
  reconciliation.
- Approve unchanged released APIs, unchanged `ppar`, and the `0.12.0a1`
  target.

**Gate:** No source, test, fixture, version, or public API implementation begins
before explicit approval of this roadmap and its governing specification.

**Approval evidence:** On September 8, 2026, the user explicitly approved Roadmap 13
and its governing specification. This approval includes direct addition as the only
multi-period policy; the post-calculation source boundary and separate result type;
the exact result schemas without averaged weights or returns; the specified period,
gap, identifier, validation, and reconciliation behavior; unchanged released APIs
and `ppar`; and the `0.12.0a1` prerelease target.

**Gate:** Passed. Step 2 is authorized; later steps remain dependency-gated.

### 2. Establish the public identity and exact schemas

**Status:** Complete September 8, 2026.

- Add and export `CurrencyAttributionRollupResult` and
  `roll_up_currency_attribution`.
- Establish exact schemas, dtypes, field order, deterministic ordering, and ownership
  tests.
- Add strict argument and direct-construction tests.
- Temporarily reject otherwise valid roll-ups until source validation and financial
  helpers pass independent tests.

**Gate:** Identity and schema tests pass, no partial result escapes, and no released
API or schema changes.

**Implementation evidence:** `CurrencyAttributionRollupResult` and
`roll_up_currency_attribution` are exported from `perfattr.currency_rollup` and the
package root. The result has exactly the five approved fields in order and remains
separate from `CurrencyAttributionResult`.

Dedicated constants establish the exact market-overall, currency-overall,
cumulative, and reconciliation schemas together with both stable reconciliation-
check orders. Tests record canonical date, identifier, numerical, string, and boolean
dtypes; zero-based indexes; ordinary direct-construction ownership; and the deliberate
absence of horizon weights and returns.

The staged function strictly requires a `CurrencyAttributionResult` and the released
positive finite, non-boolean tolerance. Every call that passes those public argument
checks reaches an unconditional `NotImplementedError` before source validation or
financial calculation and without mutating any source frame. No enum or speculative
policy argument was added.

**Gate:** Passed. All 581 tests pass, including 15 focused currency-roll-up boundary
tests. Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages
across `src`, `tests`, and `scripts`; the complete Python line-length check and
`git diff --check` report no errors. No released calculation, result schema, default,
version, dependency, tolerance, threshold, or invariant changed.

Step 3 is authorized; later steps remain dependency-gated.

### 3. Validate the source result independently

**Status:** Complete September 8, 2026.

- Require the exact `CurrencyAttributionResult` identity and canonical frame schemas.
- Validate dates, period sets, ordering-independent uniqueness, finite values, base
  currency, and reconciliation tolerance.
- Recalculate source effect-component and return identities rather than trusting
  stored boolean flags alone.
- Reject caller-mutated or directly constructed inconsistent results.

**Gate:** Focused and randomized invalid-result tests fail before roll-up, while valid
one-period and multi-period results reach the temporary financial guard unchanged.

**Implementation evidence:** A dedicated internal source boundary independently
copies all four `CurrencyAttributionResult` frames before sorting or validation. It
requires the exact released columns and dtypes; canonical dates and identities;
nonempty, unique, aligned, and non-overlapping period keys; finite values; an exact
base-currency identity; and true released reconciliation flags. Caller row and index
order are immaterial, gaps remain unsupplied gaps, and normalized copies use stable
chronological and identifier ordering with zero-based indexes.

Validation independently reconstructs each detail row's effect components, each
period's market and currency channel totals, portfolio-minus-benchmark active returns,
market-plus-currency total returns, the four-channel total effect, and every numerical
value carried by the released reconciliation evidence. It does not repeat the
Roadmap 12 market-premium, currency-return, exposure, or effect formulas.

**Gate:** Passed. All 607 tests pass, including 26 focused source-validation tests and
fixed-seed corruptions across a 24-period history. Valid shuffled histories with date
gaps reach the unchanged temporary financial guard without source mutation. Pyright
reports no errors or warnings; Pylint reports 10.00/10 with no messages across `src`,
`tests`, and `scripts`; the complete Python line-length check and `git diff --check`
report no errors. No released calculation, schema, default, version, dependency,
tolerance, threshold, or invariant changed.

Step 4 is authorized; later steps remain dependency-gated.

### 4. Implement cumulative and overall log-effect roll-up

**Status:** Complete September 8, 2026.

- Sum chronological period values directly into cumulative prefixes.
- Sum market and currency effects independently by identifier across the full
  horizon.
- Preserve partial-history identifiers without synthesizing period rows.
- Reject non-finite output before returning a result.

**Gate:** Independently hand-calculated one-, two-, and three-period fixtures match
every output value at `1e-12` without averaging weights or returns.

**Implementation evidence:** The staged calculation directly applies `float64`
cumulative addition to all fourteen chronological period-summary values. It separately
groups the three market effect columns by market identifier and the three currency
effect columns by currency identifier across the supplied horizon. Horizon dates come
from the first and last supplied periods; an identifier contributes only where it has
source rows. No weight, return, or day count is averaged, and no period or identifier
row is synthesized.

An independently derived fixture begins with four side-separated Roadmap 12 inputs
and uses ordinary simple returns converted from explicitly selected log-return facts.
It covers one, two, and three periods, changing market and currency universes, signed
currency exposure, and nonzero values in all four effect channels. Every cumulative
prefix and full-horizon identifier effect matches literal expected values at `1e-12`.
The three calculated frames are canonical and independently owned, and non-finite
aggregation is rejected.

The public function executes source validation and the complete staged calculation
but still raises `NotImplementedError` before returning anything. Step 5 must build
and validate reconciliation evidence before a complete public result may escape.

**Gate:** Passed. All 611 tests pass, including four independent Step 4 calculation
tests and 45 combined currency-roll-up tests. Pyright reports no errors or warnings;
Pylint reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; the
complete Python line-length check and `git diff --check` report no errors. No released
calculation, schema, default, version, dependency, tolerance, threshold, or invariant
changed.

Step 5 is authorized; later steps remain dependency-gated.

### 5. Complete reconciliation and edge-case coverage

**Status:** Complete September 8, 2026.

- Reconcile every cumulative prefix and both overall identifier frames.
- Cover zero effects, negative log returns, signed exposures, changing universes,
  period gaps, row-order permutations, long histories, and overflow.
- Prove caller nonmutation and independence of every returned frame.
- Explain all nontrivial financial calculations and expected values in tests.

**Gate:** Literal and randomized tests pass every cumulative and full-horizon identity
at the unchanged tolerance, and invalid inputs return no partial result.

**Implementation evidence:** Every cumulative prefix now emits the accepted fifteen
checks in stable order. Six full-horizon checks follow, comparing each market and
currency identifier-frame channel with the final cumulative channel or grid total.
Each overall identifier row is also validated against its two component effects
before reconciliation is built. Reconciliation records `actual - expected`, the
explicit tolerance, and positive boolean evidence in the exact accepted schema; any
non-finite value or failed check raises before a result escapes.

The public function now returns the complete five-field
`CurrencyAttributionRollupResult`. Returned frames are independently owned and the
base-currency identity is preserved exactly. One-, two-, and three-period literal
fixtures, a fixed-seed 60-period randomized history, and a 300-period history pass
every cumulative and horizon identity. Coverage includes exact zeros, negative log
returns, signed exposures, identifiers that start, stop, and reappear, different
period universes, date gaps, row and index permutations, non-ASCII base currency,
explicit tolerance, source mutation, and finite source values whose cumulative sum
overflows.

**Gate:** Passed. All 618 tests pass, including seven focused Step 5 tests and 52
combined currency-roll-up tests. Pyright reports no errors or warnings; Pylint reports
10.00/10 with no messages across `src`, `tests`, and `scripts`; the complete Python
line-length check and `git diff --check` report no errors. No released calculation,
schema, default, version, dependency, tolerance, threshold, or invariant changed.

Step 6 is authorized; later steps remain dependency-gated.

### 6. Complete documentation and direct-core performance evidence

**Status:** Complete September 8, 2026.

- Document why log effects add without an arithmetic smoothing policy.
- Document that the final cumulative row is the complete horizon.
- Warn against averaging weights and returns across valuation periods.
- Add a small hand-calculated example and record fixture provenance.
- Benchmark realistic histories for elapsed time and peak memory.

**Gate:** Documentation, examples, provenance, and repeatable performance evidence are
complete without adding a dependency or speculative threshold.

**Implementation evidence:** The README and public function docstring now identify
the completed source-result boundary, direct log addition, final cumulative horizon,
effect-only identifier totals, gap semantics, and the prohibitions against averaging
weights or returns and independently converting effects with `expm1`. They also state
the accounting, interaction, hierarchy, and host-integration exclusions. The
specification retains its hand-calculated two-period summary and now records the exact
origin and independence of the implemented one-, two-, and three-period fixtures.

A dedicated direct benchmark reuses the four deterministic Roadmap 12 history shapes,
constructs each completed currency result outside measurement, and reports elapsed
time, source-result memory, returned-result memory, and incremental Python-traced peak
allocation. Two consecutive five-sample runs on Python 3.11.9, pandas 3.0.5, and NumPy
2.4.6 produced paired medians of 0.0171/0.0170, 0.0318/0.0318, 0.0480/0.0482, and
0.0256/0.0265 seconds. Returned frames used 0.2 to 0.9 MiB; traced peaks used 1.2 to
22.0 MiB.

**Gate:** Passed. All four deterministic workloads completed successfully, paired
medians differed by at most 0.0009 seconds, and no workload exceeded 0.05 seconds in
this environment. The evidence provides no reason for optimization, another
dependency, or a machine-specific threshold. Successful execution of all four shapes
is the direct performance gate; absolute measurements remain diagnostic. Documentation
and independently authored fixture provenance are complete. All 618 tests pass;
Pyright reports no errors or warnings; Pylint reports 10.00/10 with no messages across
`src`, `tests`, and `scripts`; and the complete Python line-length and diff checks are
clean. No dependency, formula, tolerance, invariant, warning policy, or established
threshold changed.

Step 7 is authorized; Step 8 remains dependency-gated.

### 7. Run compatibility and release-candidate gates

**Status:** Complete September 8, 2026.

- Run the complete suite on every supported Python version.
- Require clean Pyright/Pylance, Pylint, line-length, and diff checks.
- Build and validate the sdist and wheel and smoke-test the installed public boundary.
- Run the direct performance gate established in Step 6.
- Verify all released behavior and the unchanged `ppar` integration and 500x gate.

**Gate:** The complete release-candidate gate passes without relaxing any tolerance,
threshold, invariant, warning policy, or compatibility requirement.

**Evidence:** The complete 618-test suite passes in isolated Python 3.11.9, 3.12.1,
3.13.1, and 3.14.7 environments. This includes every released arithmetic, geometric,
hierarchy, preparation, linking, and single-period currency test together with all 52
focused multi-period currency-roll-up tests. Pyright reports no errors or warnings;
Pylint reports 10.00/10 with no messages across `src`, `tests`, and `scripts`; and the
complete Python line-length and `git diff --check` gates pass.

A fresh source distribution and universal wheel build successfully from the source
tree at the unchanged prerelease version `0.11.0a1`; Twine validates both artifacts.
Archive inspection confirms the roll-up modules, tests, benchmark, governing
specification, fixture provenance, MIT license, README, and project metadata are
present as applicable. Clean wheel installations under all four supported Python
versions pass dependency checks, import `perfattr` from `site-packages`, report the
built version, and execute a representative two-period public roll-up. Every installed
run returns two cumulative prefixes and all 36 reconciliation rows pass.

The direct Roadmap 13 performance gate completes all four deterministic workloads
with production source validation and reconciliation active. Release-candidate median
elapsed times are 0.0158, 0.0300, 0.0470, and 0.0244 seconds; incremental Python-traced
peak allocations are 1.2, 11.0, 22.0, and 6.2 MiB. No machine-specific threshold is
introduced.

Inspection confirms that `ppar` neither imports nor calls the new opt-in roll-up
boundary. The locally built candidate wheel was installed without dependencies into
`ppar`'s Python 3.12.1 release-candidate environment, where `pip check` passes. The
complete established host gate passes 305 tests and 477 subtests, all static,
documentation, image, package, wheel, and installed-demo checks, and its unchanged
500x workflow. That workflow retains byte-identical large-site output and observes
1.037x large-site and 2.044x selected-input elapsed-time ratios without numeric
thresholds; long history observes 1.480x, below the unchanged 1.58x warning and 1.65x
failure boundaries. No `ppar` source or pre-existing user worktree change was altered.

No released calculation, schema, enum, default, version, dependency, tolerance,
threshold, warning, invariant, adapter call, or presentation behavior changed.

Step 8 remains unauthorized until the user reviews this evidence and gives separate
explicit release approval.

### 8. Release `perfattr==0.12.0a1`

**Status:** Complete September 8, 2026.

- Update the version and release documentation for `0.12.0a1`.
- Commit and push only after the user reviews the final evidence.
- Tag, create a GitHub prerelease, publish to PyPI, and verify the public artifact only
  after explicit release approval.

**Gate:** Public release verification succeeds from a clean environment.

**Approval evidence:** On September 8, 2026, after reviewing the complete Step 7
evidence, the user explicitly approved the release and instructed the project to
proceed on GPT-5.6 Sol High. That approval authorizes the version update, commit,
push, annotated tag, GitHub prerelease, trusted PyPI publication, and public-package
verification described above.

**Prepublication evidence:** The package and its public version test identify
`perfattr==0.12.0a1`. The README, governing specification, and feature backlog identify
multi-period currency roll-up as the release candidate. The exact versioned wheel
passes dependency checks, imports from `site-packages`, and executes a representative
two-period roll-up under Python 3.11.9, 3.12.1, 3.13.1, and 3.14.7. The complete
618-test suite passes in each versioned environment, and the final complete `ppar`
gate passes against that exact wheel with the unchanged integration boundary and
thresholds.

An isolated Hatchling build produced `perfattr-0.12.0a1.tar.gz` and the universal
`perfattr-0.12.0a1-py3-none-any.whl`; Twine accepts both artifacts. The wheel SHA-256
is `db87a628b9ada1d17e3dc5f788eaa9708cceeed34e9ce4fc259898abddcae52f`; the source-
distribution SHA-256 is
`b8e3a477a9fe857bac7f1788d53352cb0501f7c438033b1aabcbc06d12f177ef`.
Metadata and archive inspection confirm the MIT license, Python 3.11 minimum, pandas
and NumPy runtime dependencies, universal wheel, roll-up sources, benchmark, tests,
specification, and fixture-provenance documentation.

The exact-wheel `ppar` gate passed 305 tests and 477 subtests plus every static,
documentation, image, packaging, and installed-demo check. Its unchanged 500x check
retained byte-identical large-site output and measured 1.066x large-site, 1.960x
selected-input, and 1.511x long-history ratios. The long-history result remains below
the unchanged 1.58x warning and 1.65x failure boundaries. No `ppar` file or
pre-existing worktree change was altered.

At this checkpoint, neither the remote tag nor GitHub release `v0.12.0a1` exists, and
the public PyPI project contains versions only through `0.11.0a1`. No release operation
preceded the explicit approval recorded above.

**Release evidence:** Clean release commit
`0e8286ac694550c4045ae87a63690dba4480fc27` was pushed to `main`. GitHub Actions CI
run `34290833304` passed the complete suite on Python 3.11, 3.12, 3.13, and 3.14 and
independently built, validated, installed, and imported the distributions.

The release commit was tagged with annotated tag `v0.12.0a1` and published as a
[GitHub prerelease](https://github.com/JohnDReynolds/perfattr/releases/tag/v0.12.0a1).
Trusted-publisher run `34291024643` built the tagged source and wheel distributions,
verified that their metadata matched the tag, and published both artifacts to PyPI.
The public wheel SHA-256 is
`db87a628b9ada1d17e3dc5f788eaa9708cceeed34e9ce4fc259898abddcae52f`, exactly
matching the locally validated wheel. The public source-distribution SHA-256 is
`b8e3a477a9fe857bac7f1788d53352cb0501f7c438033b1aabcbc06d12f177ef`, also exactly
matching its locally validated artifact.

Fresh no-cache Python 3.11.9, 3.12.1, 3.13.1, and 3.14.7 environments installed
`perfattr==0.12.0a1` from `https://pypi.org/simple`. Every module resolved from its
environment's `site-packages`; dependency checks, representative public two-period
roll-ups, and the complete 618-test suite passed in all four environments. Python
3.11's first request preceded PyPI index propagation; its unchanged no-cache retry
completed the same full gate.

**Gate:** Passed. The approved prerelease is published on GitHub and PyPI and is
independently installable and usable across every supported Python version.

## Primary methodology reference

Denis S. Karnosky and Brian D. Singer, *Global Asset Management and Performance
Attribution*, Research Foundation of the Institute of Chartered Financial Analysts,
1994. The approved design relies on its continuously compounded return basis, its
period attribution framework, and its warning that average weights and returns across
multiple valuation periods can conceal changing strategies.

- [Official publication page][ks-page]
- [Official monograph PDF][ks-pdf]

[ks-page]: https://rpc.cfainstitute.org/research/foundation/1994/global-asset-management-and-performance-attribution
[ks-pdf]: https://rpc.cfainstitute.org/sites/default/files/-/media/documents/book/rf-publication/1994/rf-v1994-n3-4444-pdf.pdf
