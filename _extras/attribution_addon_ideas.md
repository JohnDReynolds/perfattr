# Brinson Attribution Add-on Ideas

## Purpose and scope

This document evaluates the commercial demand, technical feasibility, and likely upstream fit of adding or enhancing Brinson attribution in seven Python repositories: `bt`, `ffn`, LumiBot, OpenBB, QuantInvestStrats (`qis`), skfolio, and vectorbt.

The proposed scope is deliberately data-first:

- read already-computed periodic weights, returns, contributions, and classifications from pandas objects or simple files;
- calculate single-period Brinson-Fachler attribution, contribution, multi-period linking, and reconciliation diagnostics;
- return stable, machine-readable pandas datasets;
- integrate with a repository's existing portfolio objects only where their accounting semantics are strong enough;
- leave charts, PNG, HTML, dashboards, and other presentation to the target repository; and
- exclude Axys/APX ingestion and terminology.

This is a product and engineering assessment, not evidence of willingness to pay. Public GitHub activity, package positioning, existing analytics, commercial backing, and feature requests are useful demand proxies, but they cannot establish revenue by themselves.

## Research snapshot

The assessment uses the latest upstream default development branch heads verified on **2026-09-02**. Short hashes are included so that later changes do not silently invalidate the conclusions.

| Repository | Upstream branch reviewed | Commit | Approximate public reach | Current attribution-adjacent position |
|---|---:|---:|---:|---|
| [`bt`](https://github.com/pmorissette/bt) | `master` | `db6163e` | 3.0k stars | Backtest holdings, positions, security weights, results |
| [`ffn`](https://github.com/pmorissette/ffn) | `master` | `3e440f6` | 2.6k stars | Pandas-based performance measurement and evaluation |
| [LumiBot](https://github.com/Lumiwealth/lumibot) | `dev` | `7f83963` | 2.0k stars | Backtest/live strategy statistics and artifacts |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | `develop` | `3e071fc` | 72k stars | Data platform and typed analytical extensions |
| [`qis`](https://github.com/ArturSepp/QuantInvestStrats) | `main` | `d125d59` | 630 stars | Existing Brinson, performance contribution, and risk attribution |
| [skfolio](https://github.com/skfolio/skfolio) | `main` | `69c5234` | 2.3k stars | Portfolio objects plus an extensive factor-attribution namespace |
| [vectorbt](https://github.com/polakowo/vectorbt) | `master` | `34b6d59` | 9.0k stars | Multi-asset portfolio simulation, grouping, returns, and benchmarks |

Star counts are rounded snapshots, not a ranking criterion on their own. Upstream source, documentation, issue, and license links appear in the relevant sections below.

## Executive recommendation

There are two different opportunities: improve a repository that already owns the problem, or introduce the problem to a repository with suitable data but no attribution model. They should not be treated as interchangeable.

| Priority | Repository | Demand assessment | Technical feasibility | Upstream/product fit | Recommended move |
|---:|---|---|---|---|---|
| 1 | `qis` | High within its specialist audience | High | Very high | Enhance the existing implementation with explicit semantics, reconciliation, and linked datasets |
| 2 | skfolio | High | Medium-high | Very high | Propose a dedicated `BrinsonAttributionResult`; start with explicit DataFrame inputs, then add portfolio adapters |
| 3 | `bt` | Medium-high | Medium-high | High | Add a pure pandas engine and a carefully defined two-backtest adapter |
| 4 | `ffn` | Medium | High for a pure engine; low for end-to-end attribution | Medium-high | Discuss a small calculation API; do not pretend `PerformanceStats` contains holdings |
| 5 | vectorbt | Medium-high user potential, medium evidence | Medium-high | Medium, with roadmap/licensing uncertainty | Write an RFC before code; keep simulation-grid expansion opt-in |
| 6 | LumiBot | Medium, low-confidence | Medium-low for a reliable adapter | Medium-low | Add snapshot data first; defer Brinson until benchmark constituent data exists |
| 7 | OpenBB core | Large potential audience, weak feature-specific evidence | Medium for a calculator | Low-medium in the current platform | Prototype an external extension before proposing a core command |

The first practical sequence should be:

1. establish a pandas reference specification and independent golden fixtures;
2. enhance `qis`, where demand and domain fit are already demonstrated;
3. propose skfolio as the strongest new home;
4. decide whether the `bt`/`ffn` family wants the generic engine in `ffn` with a `bt` adapter, or a self-contained implementation in `bt`; and
5. approach vectorbt, LumiBot, and OpenBB only after a maintainer-facing design issue validates scope.

## Common product definition

### What “Brinson attribution” should mean here

For portfolio group (g) and period (t), the minimum reliable input contract is:

- portfolio beginning-of-period weight (W^P_{g,t});
- benchmark beginning-of-period weight (W^B_{g,t});
- portfolio group return (R^P_{g,t});
- benchmark group return (R^B_{g,t}); and
- total benchmark return (R^B_t).

The Brinson-Fachler allocation effect is:

\[
A_{g,t} = (W^P_{g,t} - W^B_{g,t})(R^B_{g,t} - R^B_t)
\]

A three-effect presentation can then use:

\[
S_{g,t} = W^B_{g,t}(R^P_{g,t} - R^B_{g,t})
\]

\[
I_{g,t} = (W^P_{g,t} - W^B_{g,t})(R^P_{g,t} - R^B_{g,t})
\]

or a two-effect presentation can absorb interaction into selection:

\[
S^{\*}_{g,t} = W^P_{g,t}(R^P_{g,t} - R^B_{g,t})
\]

The API must name the convention. “Selection” without saying whether it absorbs interaction is not a complete contract.

### What the first implementation should return

A target repository may rename fields to match its conventions, but the engine should be able to provide these pandas datasets:

- `period_detail`: one row per period and classification group, containing portfolio and benchmark weights, returns, contributions, active contribution, allocation, selection, optional interaction, total effect, and linked effects;
- `period_summary`: one row per period, including total portfolio return, benchmark return, active return, summed effects, and reconciliation residuals;
- `overall_detail`: one row per group over the requested horizon with linked contribution and attribution totals;
- `cumulative`: period-end cumulative portfolio return, benchmark return, active return, contribution, and effects; and
- `diagnostics`: validation warnings, coverage facts, unmapped identifiers, residuals, and tolerances.

A small immutable result object or frozen dataclass should hold those frames. The result is the presentation boundary: target repositories can plot it later without forcing plotting dependencies or a shared visual design into the calculator.

### Non-negotiable accounting choices

Every implementation needs an explicit policy for:

- **Return versus contribution.** A return is not a contribution. At security level, contribution is normally beginning weight times security return; at group level, return is contribution divided by group weight when that division is defined.
- **Weight timing.** The weight applied to interval return must be the beginning-of-period exposure. End-of-day or post-trade weights cannot be multiplied by same-date returns without a documented shift.
- **Cash, fees, financing, derivatives, and external flows.** The engine must either attribute them as explicit categories, calculate on a stated gross basis, or report a residual. Silently forcing them into security selection is misleading.
- **Benchmark constituents.** A benchmark total-return series is insufficient for Brinson. Group or constituent benchmark weights and returns are required.
- **Classification timing.** Static mappings are sufficient for a first PR, but the schema should not prevent point-in-time classifications later.
- **Zero and negative weights.** Long/short and hedged portfolios can have a zero net group weight with nonzero contribution. Preserve the contribution and report an undefined group return instead of dropping the group or inventing a return.
- **Multi-period linking.** Arithmetic summation of period effects does not generally reconcile to geometrically compounded active return. Linked and unlinked fields must be distinct.

## Repository assessment: `bt`

### Demand

Demand is **medium-high**. `bt` is explicitly a flexible backtesting framework, has roughly 3,000 GitHub stars, and already exposes strategy values, positions, security weights, transactions, fees, cash, and performance results. Its audience is accustomed to comparing allocation strategies, which is the use case Brinson answers.

There is also a direct, though old, public request: [issue #251 asks for performance attribution by security](https://github.com/pmorissette/bt/issues/251) for a dynamic allocation strategy. The issue was closed without an implementation, so it is evidence of user interest rather than a current maintainer commitment.

The commercial signal is primarily professional and educational usage of portfolio backtesting rather than a paid `bt` product. The feature would improve the framework's usefulness for advisers, asset allocators, and research teams, but public evidence of willingness to pay is limited.

### Technical feasibility

Feasibility is **medium-high**. [`Backtest` already calculates security weights and retains portfolio state](https://github.com/pmorissette/bt/blob/master/bt/backtest.py), and `bt` depends on pandas through `ffn`; no new numerical dependency is needed.

The hard part is not the formula. It is reconstructing a defensible attribution interval from a trading simulation:

- security weights reflect specific update and rebalance timestamps, so the adapter must prove which values are beginning-of-period;
- the portfolio and benchmark may hold different universes;
- fees, idle cash, coupons, financing, and external flows can prevent security contributions from summing to net portfolio return;
- nested strategy nodes and fixed-income notionals may not behave like simple long-only equity holdings; and
- a single benchmark price series lacks benchmark constituent weights.

The first adapter should therefore compare two completed `Backtest` objects—one portfolio and one constituent-level benchmark—or accept explicit benchmark weight and return frames. It should not infer a Brinson benchmark from `Result.prices` alone.

### Best upstream shape

The safest first contribution is a standalone pandas calculator with a narrow adapter:

```python
result = bt.brinson_attribution(
    portfolio=portfolio_backtest,
    benchmark=benchmark_backtest,
    classification=security_to_sector,
    frequency="M",
    interaction="separate",
)
```

The actual spelling should follow maintainer preference. Internally, the adapter should produce the common normalized table and call a pure engine. It should expose residuals for cash and costs, default to a gross security-return basis unless the net accounting identity is proven, and return datasets rather than charts.

### Recommendation

Open a design issue with a minimal fixture showing a strategy, a constituent-level benchmark, a classification mapping, and a residual. If maintainers want the generic math in `ffn`, split the work into an `ffn` engine followed by a `bt` adapter. Otherwise, a small self-contained `bt` implementation is less risky than coordinating two coupled PRs.

## Repository assessment: `ffn`

### Demand

Demand is **medium**. [`ffn` describes itself as a pandas-, NumPy-, and SciPy-based financial function library](https://github.com/pmorissette/ffn) spanning performance measurement, evaluation, plotting, and transformations. A Brinson calculation primitive fits that broad description and could serve both direct users and `bt`.

The constraint is that most `ffn` workflows begin with one or more price or return series. Its `PerformanceStats` and `GroupStats` abstractions compare performance series; they do not retain constituent holdings, classifications, or benchmark weights. Consequently, demand for a formula library is plausible, but end-to-end attribution demand is not demonstrated by the current object model.

### Technical feasibility

Feasibility is **high for a pure calculator** and **low for automatic attribution from existing statistics objects**. Pandas and NumPy are already present. The engine can accept normalized long-form data or aligned weight/return matrices without changing any performance accounting.

It should not be added as a method that appears to derive Brinson attribution from `PerformanceStats`. That object does not contain enough information. It also need not start as another pandas monkey-patched method; a discoverable module function and result dataclass would be clearer and easier to test.

### Best upstream shape

A credible first API would require explicit portfolio and benchmark group data:

```python
result = ffn.calc_brinson(
    portfolio_weights=portfolio_weights,
    portfolio_returns=portfolio_returns,
    benchmark_weights=benchmark_weights,
    benchmark_returns=benchmark_returns,
    classification=classification,
)
```

Alternatively, one normalized long DataFrame avoids four-way column alignment. The calculator should reject insufficient inputs instead of guessing them from a total-return series.

### Recommendation

Discuss the API before implementation. `ffn` is arguably the cleanest mathematical home in the `bt` family, but the feature is only valuable when callers already own holdings and benchmark constituent data. If maintainers prefer to keep `ffn` focused on series analytics, implement directly in `bt` rather than stretching `ffn`'s abstractions.

## Repository assessment: LumiBot

### Demand

Demand is **medium but low-confidence**. [LumiBot positions itself as a framework for backtesting and live trading](https://github.com/Lumiwealth/lumibot), while Lumiwealth/BotSpot supplies commercial backing and managed operation. Better portfolio diagnostics can help strategy developers explain why a strategy beat a benchmark.

The center of gravity, however, is trading automation, broker integration, and strategy operation—not institutional portfolio reporting. Many users run a strategy against a single-symbol benchmark, a setup in which group-level Brinson attribution adds little. The likely commercial value is greatest for multi-asset allocation strategies and managed-model workflows, which are a narrower subset of the user base.

### Technical feasibility

Feasibility is **medium-low for an honest end-to-end adapter**. LumiBot's strategy statistics are pandas DataFrames and can be exported as artifacts. Current stats include portfolio value, cash-flow-adjusted return information, and position quantities. But the normal trace does not provide a complete beginning-of-period attribution snapshot containing a stable identifier, mark, multiplier, market value, and weight for each position. Its usual benchmark is a total return series for one asset, not a constituent-level benchmark portfolio.

Those gaps cannot be repaired inside the attribution formula. Re-fetching historical marks later may use different adjustment, timezone, or data-source semantics from the simulation. Capturing every position on every intraday iteration, on the other hand, can make stats artifacts unmanageably large.

The latest requirements currently include Polars for other LumiBot functionality. That does not alter this recommendation: the analytics and stats boundary relevant to this feature is pandas, and the shared implementation should remain pandas-only so that it is portable to all seven targets.

### Best upstream shape

The prerequisite is an opt-in, backtest-only attribution snapshot at a user-selected frequency. Each snapshot should include:

- interval start and end;
- canonical asset identifier;
- quantity, mark, multiplier, market value, and beginning weight;
- security total return or enough exact simulation data to calculate it;
- fees, financing, cash, and external-flow facts; and
- a separately supplied benchmark holdings/weights table and classification map.

Once that artifact exists, a pandas Brinson postprocessor is straightforward. Results should be returned as frames and optionally written beside existing CSV or Parquet stats artifacts. Scalar “custom metrics” are not an adequate container.

### Recommendation

Do not lead with a Brinson PR. First propose the periodic position-value snapshot as a generally useful analytics primitive. Add Brinson only after the maintainers accept its storage cost and benchmark input model. Restrict version one to backtests; live attribution introduces restatements, late data, and operational controls that deserve a separate design.

## Repository assessment: OpenBB

### Demand

OpenBB has by far the largest reachable audience, but feature-specific demand is **medium at best and weakly evidenced**. [The current repository is an open data platform for analysts, quants, and AI agents](https://github.com/OpenBB-finance/OpenBB), with Python, API, Workspace, Excel, and MCP delivery surfaces. It also has a commercial enterprise product.

There are attribution-adjacent signals. The community's [Awesome OpenBB list includes a portfolio risk workflow with Fama-French attribution](https://github.com/OpenBB-finance/awesome-openbb/blob/main/README.md), and the legacy OpenBB Terminal had a holdings-oriented [portfolio toolkit](https://github.com/OpenBB-finance/OpenBB/discussions/4527). Neither establishes current demand for Brinson in the platform. Factor attribution and Brinson holdings attribution solve different questions, and the legacy portfolio module is not part of the current architecture.

### Technical feasibility

Feasibility is **medium for a typed calculator** but the fit with core is **low-medium**. The current quantitative extension contains compact performance commands such as Sharpe, Sortino, and Omega calculations. It does not own a portfolio ledger, transaction model, constituent benchmark, or classification service. OpenBB excels at acquiring and normalizing data; it should not silently manufacture portfolio accounting facts.

A command can accept already-normalized records and return an `OBBject` with typed result rows. The awkward part is the input surface: four large matrices do not fit naturally in a command-line or REST query. A single long-form request payload is more coherent, with fields such as `side`, `from_date`, `thru_date`, `identifier`, `classification`, `weight`, and `return`.

### Best upstream shape

The best first implementation is an external OpenBB extension that:

- accepts one normalized long dataset or a path/URL supported by the extension;
- validates it with OpenBB models;
- runs a dependency-neutral pandas/NumPy engine;
- returns period, overall, cumulative, and diagnostic records through the usual OpenBB result container; and
- performs no plotting.

This tests demand and API ergonomics without asking OpenBB core to become a portfolio accounting system. If users adopt it, the command can later be proposed for the quantitative extension.

### Recommendation

Prototype outside core and bring usage evidence to a maintainer RFC. A core PR written before proving the payload model is likely to spend effort on platform integration while still lacking the benchmark constituent data the calculation requires.

## Repository assessment: QuantInvestStrats (`qis`)

### Demand

Demand is **high within the repository's specialist audience**. `qis` already treats portfolio analytics and reporting as first-class domains, and its [current paper describes portfolio, optimization, backtesting, and performance layers](https://github.com/ArturSepp/QuantInvestStrats/blob/main/paper.md). Most importantly, [a Brinson implementation already exists](https://github.com/ArturSepp/QuantInvestStrats/blob/main/src/qis/portfolio/reports/brinson_attribution.py), is used by strategy-versus-benchmark reports, and has received recent fixes and interaction-convention changes in the [changelog](https://github.com/ArturSepp/QuantInvestStrats/blob/main/CHANGELOG.md).

That is stronger evidence than stars alone: the maintainer is actively spending engineering effort on attribution. The likely users are quantitatively sophisticated asset allocators, portfolio researchers, and reporting users. The feature is narrower than OpenBB's audience but much closer to a real requirement.

### Current implementation and gaps

The current function is pandas-based and returns five DataFrames, with presentation handled by adjacent report code. It already supports classification, strategy-versus-benchmark comparison, and configurable treatment of interaction.

The main opportunities are contract clarity and time aggregation:

- parameters and intermediate fields mix “P&L” terminology with Brinson weight/return formulas; a characterization test should establish whether every grouped input is a return, a return contribution, or normalized P&L before formulas are changed;
- arithmetic accumulation is useful as an ex-post contribution view but does not replace geometric multi-period linking;
- the tuple of five frames is usable but hard to evolve without positional breakage;
- reconciliation identities, unmapped identifiers, zero-weight behavior, and period coverage deserve explicit diagnostics; and
- there is no obvious reusable calculation layer independent of factsheet organization.

This is not a recommendation to delete or silently redefine the existing function. Recent interaction-policy changes mean compatibility matters.

### Technical feasibility

Feasibility is **high**. The repository is already pandas-native, owns the relevant portfolio and classification objects, and has an established reporting consumer. The engineering work is mainly to separate normalized inputs, formulas, linking, results, and rendering.

The first new kernel should accept unambiguous weights and returns—or contributions with an explicit flag and validation—and return a named result object. A compatibility wrapper can continue returning the existing five-frame tuple. Both “separate interaction” and “interaction absorbed into selection” should remain available and named in metadata.

Carino linking should be added for active effects. Portfolio and benchmark contribution series can use logarithmic linking separately. Simple, linked, and cumulative columns must have distinct names so callers cannot accidentally plot arithmetic effects as a horizon reconciliation.

### Recommendation

This is the best first enhancement target. Submit it in small steps:

1. characterize the existing formulas and outputs with golden tests;
2. add a pure single-period Brinson-Fachler kernel and reconciliation diagnostics;
3. add the structured result while keeping the tuple wrapper;
4. add Carino/log-linked datasets; and
5. migrate existing factsheets to consume the new datasets without changing their visual contract.

The earlier QIS-specific memo was directionally correct about returns-versus-contributions semantics, Carino linking, classification strength, frequency policy, and auditability. The current upstream has evolved since that memo—particularly around ticker alignment and interaction handling—so those existing capabilities should be preserved rather than re-proposed as missing.

## Repository assessment: skfolio

### Demand

Demand is **high**. skfolio is explicitly a portfolio optimization and risk-management library, has more than 2,000 stars, and offers professional support. More decisively, the current v1-era architecture already contains a substantial [`skfolio.attribution.Attribution`](https://github.com/skfolio/skfolio/blob/main/docs/user_guide/factor_models.rst) result model for predicted, realized, rolling, factor, family, asset, return, and risk attribution. Brinson is adjacent to an established product concept rather than a foreign reporting feature.

The existing [portfolio user guide](https://github.com/skfolio/skfolio/blob/main/docs/user_guide/portfolio.rst) also exposes returns, contributions, `Portfolio`, and `MultiPeriodPortfolio` concepts. This makes the likely user story clear: explain active performance of an optimized or rebalanced portfolio relative to a benchmark by sector, country, style bucket, or another classification.

### Technical feasibility

Feasibility is **medium-high**. pandas and NumPy are already core dependencies. `Portfolio` and `MultiPeriodPortfolio` expose observations, asset returns, weights, costs, and portfolio returns. A time-varying portfolio can supply much of the portfolio side of an adapter.

Three design issues remain:

- the existing `Attribution` name belongs to factor attribution, so Brinson needs a distinct result type such as `BrinsonAttributionResult`;
- a benchmark return series used for tracking error is not a constituent-level benchmark and cannot supply benchmark group weights; and
- the timing of `weights_per_observation`, transaction costs, management fees, and the `compounded` setting must be mapped explicitly to beginning-of-period gross return attribution.

The first API should therefore accept explicit aligned portfolio and benchmark weight/return data. A later convenience adapter may accept a `MultiPeriodPortfolio` for both sides after its timing and cost identities are proven.

### Best upstream shape

Place Brinson under the existing attribution namespace without forcing it into the factor-attribution dataclass:

```python
result = skfolio.attribution.brinson(
    portfolio_weights=...,
    portfolio_returns=...,
    benchmark_weights=...,
    benchmark_returns=...,
    groups=...,
    interaction="absorbed",
    linking="carino",
)
```

The result should follow skfolio conventions for names, immutable results, DataFrame access, and summary methods. Plotting can be added by maintainers later using the repository's presentation layer.

### Recommendation

This is the strongest greenfield target. Open with an API proposal that explicitly distinguishes factor attribution from holdings-based Brinson attribution. Implement the pure calculator and synthetic tests first; add `Portfolio`/`MultiPeriodPortfolio` adapters only after resolving beginning-weight and gross/net semantics.

## Repository assessment: vectorbt

### Demand

Demand is **medium-high in potential and medium in direct evidence**. [vectorbt](https://github.com/polakowo/vectorbt) has roughly 9,000 stars, a large quantitative user base, a commercial PRO line, and strong multi-asset portfolio analytics. Users can group assets, evaluate portfolios, and compare benchmark returns. Community discussions about [custom benchmarks](https://github.com/polakowo/vectorbt/discussions/247) and grouping show the adjacent need, although they are not direct requests for Brinson.

Commercially, attribution could be valuable to users exploring allocation grids and multi-strategy portfolios. The uncertainty is product placement: the public repository is the community edition and uses a Commons Clause license, while advanced analytics may be part of the commercial roadmap. A technically good unsolicited PR could still be out of scope.

### Technical feasibility

Feasibility is **medium-high for a calculator** and **medium for a native portfolio adapter**. [`Portfolio`](https://github.com/polakowo/vectorbt/blob/master/vectorbt/portfolio/base.py) already exposes asset values, portfolio values, cash flows, returns, asset returns, benchmark values/returns, grouping, and pandas-oriented wrappers.

The standard benchmark data still does not provide constituent benchmark weights. A reliable adapter must compare two compatible `Portfolio` objects or accept explicit benchmark matrices. Existing `group_by` is also not automatically an attribution classification: simulation groups can govern cash sharing and array layout, while the analytical classification may be sector or country. A separate mapping is necessary.

vectorbt's broadcasted parameter grids create another risk. Automatically expanding attribution across every parameter, asset, group, and time dimension can produce enormous intermediate frames. Version one should require the caller to select one portfolio/group configuration or explicitly opt into a batch dimension. The Brinson arithmetic itself does not need to be rewritten in Numba before semantics are stable.

### Best upstream shape

Provide a small pandas result for a deliberately selected slice:

```python
result = portfolio.brinson_attribution(
    benchmark=benchmark_portfolio,
    classification=classification,
    frequency="M",
)
```

or start with a namespace-level function using explicit arrays/frames. Internally it should use vectorbt's wrappers only at the adapter boundary, normalize to the common table, calculate once, and return named pandas datasets.

### Recommendation

Begin with a maintainer RFC covering benchmark constituents, independent classification grouping, grid selection, and whether the feature belongs in Community or PRO. Do not invest in Numba optimization or broad broadcasting until maintainers validate the product location and a pandas reference implementation passes reconciliation tests.

## Extracting the reusable attribution core from `ppar`

### Boundary of the reuse

`ppar` contains useful, mature ideas for generic performance ingestion, period alignment, classification rollup, contribution calculation, Brinson-Fachler effects, Carino linking, and audit identities. The relevant source boundaries are:

- [`performance.py`](https://github.com/JohnDReynolds/ppar/blob/main/src/ppar/performance.py): normalized periodic performance records and validation;
- [`classification.py`](https://github.com/JohnDReynolds/ppar/blob/main/src/ppar/classification.py) and [`mapping.py`](https://github.com/JohnDReynolds/ppar/blob/main/src/ppar/mapping.py): mappings and classification rollup;
- [`core.py`](https://github.com/JohnDReynolds/ppar/blob/main/src/ppar/core.py): period alignment, consolidation, contribution linking, and reconciliation;
- [`attribution.py`](https://github.com/JohnDReynolds/ppar/blob/main/src/ppar/attribution.py): universe alignment, Brinson-Fachler calculation, Carino linking, cumulative data, and result tables; and
- [`schema.py`](https://github.com/JohnDReynolds/ppar/blob/main/src/ppar/schema.py): stable output field names.

The extraction should stop at the dataset boundary. Do **not** move:

- HTML generation, charts, color systems, templates, or report layout;
- CLI orchestration;
- Axys/APX readers, schemas, setup helpers, fixtures, or terminology;
- unrelated risk analytics; or
- Polars objects in a target repository's public or internal runtime API.

### Licensing and provenance gate

As of this review, `ppar` is distributed under a **proprietary evaluation license**, while the seven targets use MIT, BSD, GPL/AGPL, or Commons-Clause terms. Literal copying from `ppar` into an upstream open-source contribution is therefore not authorized by the public `ppar` license.

The current history appears to be authored by John Reynolds, which may make dual licensing possible, but authorship and the right to relicense must be confirmed for every copied line, test fixture, and document. The safe choices are:

1. **Preferred:** write a fresh pandas implementation from the published mathematical specification and independently designed fixtures, using `ppar` only to identify requirements and as a private differential oracle;
2. explicitly release a clearly bounded, self-authored `ppar` core under a target-compatible outbound license before copying it; or
3. obtain written permission covering the exact code and target license, and record that provenance in the PR.

The target's contributor agreement, developer certificate of origin, and license must also be checked. Reusing the financial formulas is different from copying proprietary expression, organization, comments, and fixtures. This document is not legal advice; the outbound-license decision should be made before implementation, not during PR review.

### Target-neutral data contract

The reusable core should normalize every source into one long pandas DataFrame:

| Field | Required | Meaning |
|---|---:|---|
| `from_date` | Yes | Inclusive or effective interval start, normalized consistently |
| `thru_date` | Yes | Interval end |
| `side` | Yes | `portfolio` or `benchmark` |
| `identifier` | Yes | Stable security or sleeve identifier |
| `classification` | Yes after mapping | Sector, country, asset class, or other group |
| `weight` | Yes | Beginning-of-period weight |
| `return` | Usually | Security or sleeve total return for the interval |
| `contribution` | Optional alternative | Explicit contribution when return cannot be represented safely |
| `name` | No | Display label, never a join key |

If both return and contribution are supplied, validate their relationship where it is mathematically defined. If only contribution is supplied, group return may be recovered as summed contribution divided by group weight except at zero net weight. Preserve an undefined return and the valid contribution in that case.

The first reader needs only:

- an in-memory pandas DataFrame constructor;
- a CSV reader with explicit dtype/date normalization; and
- repository-specific adapters that construct the same frame.

Parquet can be supported when the target already has a Parquet engine; it should not become a required dependency. URLs, database readers, and provider clients belong to the host repository, not the calculation core.

### Decomposition into reusable layers

Do not translate the large `ppar.Attribution` class line by line. Separate six small layers:

1. **Normalize and validate.** Canonicalize dates and identifiers; reject non-finite numeric data, duplicate period/side/identifier keys, overlapping periods, conflicting mappings, and unsupported weight totals.
2. **Align periods and universes.** Intersect valid portfolio/benchmark coverage, equalize missing identifiers with explicit zero exposures, and reject ambiguous gaps. Never use an unconstrained outer join followed by blanket `fillna(0)`.
3. **Consolidate frequency.** When requested, compound returns and use documented exposure weighting. Only combine differing native partitions when both sides fully cover the same target bucket.
4. **Roll up classifications.** Sum weights and contributions by period/group; derive group return only when group weight permits it.
5. **Calculate and link.** Produce simple contribution, Brinson-Fachler effects, logarithmically linked portfolio/benchmark contributions, Carino-linked active effects, and cumulative paths.
6. **Package results and audit.** Return named pandas frames plus machine-readable diagnostics; enforce reconciliation within configured absolute and relative tolerances.

This separation lets each repository replace only the adapter. The calculation fixtures and accounting identities can remain conceptually identical without imposing a shared package dependency.

### Multi-period linking to preserve

For active attribution, use the Carino coefficient for period (t):

\[
k_t = \frac{\ln(1+R^P_t)-\ln(1+R^B_t)}{R^P_t-R^B_t}
\]

and the analogous full-horizon coefficient (K). A linked period effect is the simple effect multiplied by (k_t/K). Use the analytic equal-return limit (1/(1+R_t)) when portfolio and benchmark returns are equal or numerically close. Reject returns at or below -100% because the logarithm is undefined.

For contribution to one portfolio's compounded return, use logarithmic smoothing based on `log1p` and the overall compounded return. Use stable `log1p`, `expm1`, and near-zero branches rather than direct formulas that lose precision.

Always retain both simple and linked columns. Simple period effects explain the period; linked effects reconcile the full horizon. They answer related but different questions.

### Audit identities

At minimum, tests and optional runtime validation should establish:

- security contributions sum to each side's period return;
- group contributions sum to total contributions;
- allocation plus selection plus optional interaction sums to period active return;
- linked portfolio contributions sum to compounded portfolio return;
- linked benchmark contributions sum to compounded benchmark return;
- linked active effects sum to compounded portfolio return minus compounded benchmark return;
- overall group totals equal the sum of linked period/group effects;
- cumulative final values equal overall values; and
- any unexplained difference is returned as a residual, never hidden by rounding.

## Building the additional fully pandas implementation

### Recommendation: reimplement the specification, not the Polars syntax

The best portable design is a fresh pandas orchestration layer around small NumPy numerical helpers. It should reproduce the financial contract and invariants of `ppar`, not its Polars expression tree. This avoids a new dependency, reduces licensing ambiguity, and results in code that target maintainers can read in their native stack.

All seven repositories already expose pandas at the relevant boundary or depend on it. LumiBot now also happens to include Polars elsewhere, but relying on that would make the implementation non-portable and would not help the other six.

### Pandas implementation pattern

Use operations that are conventional across supported pandas versions:

- normalize keys once with `assign`, explicit dtype conversion, and `to_datetime`;
- use validated `merge` operations for mappings and portfolio/benchmark pairing;
- use a sorted `MultiIndex` or stable long keys for period/group alignment;
- use `groupby(...).agg(...)` for weights and contributions;
- use `reindex` only against a deliberately constructed complete universe;
- use NumPy masks and `np.divide(..., where=...)` for zero-weight cases;
- calculate cumulative returns with `np.expm1(np.log1p(r).cumsum())` when appropriate;
- avoid `iterrows`, chained assignment, implicit categorical behavior, and blanket missing-value replacement; and
- never mutate caller-owned frames.

Return ordinary pandas DataFrames with stable column order and documented index names. Do not expose internal merge suffixes or depend on incidental group ordering.

### Proposed internal API

The exact package path should match each target, but a small implementation can be organized around these responsibilities:

```python
@dataclass(frozen=True)
class BrinsonAttributionResult:
    period_detail: pd.DataFrame
    period_summary: pd.DataFrame
    overall_detail: pd.DataFrame
    cumulative: pd.DataFrame
    diagnostics: pd.DataFrame


def read_performance_csv(path: PathLike, *, side: str) -> pd.DataFrame: ...

def normalize_performance(
    data: pd.DataFrame,
    *,
    side: str,
    classification: pd.Series | pd.DataFrame | None = None,
) -> pd.DataFrame: ...

def brinson_attribution(
    portfolio: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    interaction: Literal["separate", "absorbed"] = "absorbed",
    linking: Literal["none", "carino"] = "carino",
    frequency: str | None = None,
) -> BrinsonAttributionResult: ...
```

For repositories that prefer matrices, provide a thin matrix-to-long adapter. Keep the long normalized representation inside the engine because it makes period, universe, and classification keys explicit.

### Validation strategy

Build tests from hand-calculable fixtures before comparing with `ppar`:

- one period, two groups, equal universes;
- underweight outperformer and overweight underperformer;
- separate versus absorbed interaction;
- portfolio-only and benchmark-only securities;
- unmapped classification;
- duplicate key and conflicting mapping errors;
- zero, negative, and leveraged weights;
- zero net group weight with nonzero contribution;
- equal portfolio/benchmark returns for the Carino limit;
- zero return and near-zero return precision;
- a return close to, equal to, and below -100%;
- mismatched but consolidatable native period partitions;
- gaps and overlaps that must be rejected;
- costs/cash residual; and
- multi-period examples where arithmetic effects visibly fail to reconcile but linked effects succeed.

After independent expected values are locked, run a temporary differential suite against `ppar` on randomized valid cases. `ppar` should be a development oracle only: it must not be imported, installed, or required by the target package or its distributed tests. Investigate every difference rather than automatically blessing `ppar` output.

### Performance strategy

Correctness and contracts come before compilation. A vectorized pandas implementation should be adequate for periodic attribution across ordinary institutional universes. Benchmark it with realistic shapes—for example 2,000 securities, 120 monthly periods, and 20 groups—before optimizing.

If performance is inadequate:

1. measure normalization, joins, grouping, and linking separately;
2. reduce repeated index construction and intermediate copies;
3. move only scalar coefficient calculations to NumPy arrays; and
4. consider target-native acceleration only after the pandas result is the reference.

Do not add Numba, Polars, PyArrow, or another engine solely for this feature. vectorbt may later choose its existing accelerated infrastructure, but that should be an internal optimization with identical pandas outputs.

## Suggested PR program

### Phase 0: portable specification

Create a non-distributed reference fixture set, field dictionary, formulas, and reconciliation checklist. Decide outbound licensing before any source reuse. This phase prevents seven subtly incompatible meanings of “selection” and “linked contribution.”

### Phase 1: `qis` enhancement

Characterize compatibility, introduce the pure kernel/result object, add audits, and then add Carino-linked data. Keep existing reports visually unchanged and retain the current tuple interface through a wrapper.

### Phase 2: skfolio addition

Submit a design issue followed by a pure explicit-input implementation. Name the result so it cannot be confused with factor attribution. Add `MultiPeriodPortfolio` conveniences in a later PR.

### Phase 3: `bt`/`ffn`

Ask maintainers where the generic engine belongs. If the answer is `ffn`, land the pure function first and the `bt` adapter second. If not, keep the implementation self-contained in `bt`. In either case, prove beginning-weight and residual semantics.

### Phase 4: validate the remaining markets

- vectorbt: resolve Community-versus-PRO location and batch-grid scope before code;
- LumiBot: land an opt-in periodic position-value snapshot before attribution; and
- OpenBB: publish an external extension and collect usage before proposing core inclusion.

## Final judgment

The opportunity is real, but “one implementation copied into seven repositories” is the wrong product strategy. The durable common asset is a precise pandas data contract, formula convention, linking method, and fixture suite. Each repository then needs a small adapter that respects its own portfolio accounting and result conventions.

`qis` is the best immediate enhancement because attribution is already an actively maintained product feature. skfolio is the best new upstream target because attribution is already part of its public conceptual model. `bt` is the best backtest-native opportunity, provided weight timing and residuals are explicit. `ffn` is a plausible shared mathematical home but cannot provide end-to-end attribution from its current objects. vectorbt has meaningful reach but needs roadmap agreement. LumiBot first needs richer periodic portfolio facts, and OpenBB should validate the idea as an extension rather than rebuilding a portfolio ledger in core.

Across all seven, the strongest contribution is a small, fully pandas, auditable calculation layer that delivers datasets and gets out of the presentation layer's way.
