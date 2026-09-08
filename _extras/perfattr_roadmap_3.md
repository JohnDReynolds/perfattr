# perfattr Roadmap 3: Subsequent Feature Backlog

**Status:** Noncommitted backlog as of September 5, 2026.

This document records possible work after roadmap 2. It is ordered primarily by
technical dependency, not by promised delivery. Nothing here authorizes implementation
or a public API change. An item must first be specified, approved, and promoted into an
active roadmap.

## Promotion rules

Before promoting a feature:

- state the user problem and why existing contracts do not already solve it;
- define the methodology, inputs, outputs, null behavior, and reconciliation identities;
- identify any result-schema or compatibility change;
- verify primary references, licensing, and intellectual-property considerations;
- construct independent hand-calculated fixtures; and
- define proportionate correctness and performance gates before implementation.

Prefer one small policy or methodology at a time. Add a general abstraction only when
two implemented cases demonstrate the need.

When designing relevant features, review
[`pybrinson`](https://github.com/gghez/pybrinson/) for useful ideas about methodology
boundaries, public APIs, invariants, fixtures, hierarchy, and linking. Treat it as a
comparative design reference rather than the calculation authority: verify formulas
against primary sources, make independent design decisions for `perfattr`, and complete
the required license and fixture-provenance review before reusing code or test data.

## 1. Record supported modeling conventions

**Status:** Existing conventions documented as of September 4, 2026; cash and
unexposed-charge behavior are covered by focused tests.

These are existing input representations, not future calculation features. They use
the released formulas, schemas, and reconciliation rules without special numerical
treatment. Host accounting adapters remain responsible for deciding what a source row
means and supplying the appropriate facts. The next feature selected for consideration
after roadmap 6 is the BHB two-effect reporting convention recorded below. Selection
as the next candidate does not authorize implementation.

### Explicit cash — supported

- Cash is an ordinary attributable identifier and may be mapped to a Cash
  classification like any other identifier.
- Positive, negative, and zero cash weights use the ordinary attribution and
  reconciliation formulas.
- `perfattr` does not identify or synthesize cash, calculate a separate cash-drag
  effect, or use cash as a hidden residual. Those decisions belong to host adapters.

### Fees and financing — supported

- A charge without attributable exposure is represented by zero weight, authoritative
  nonzero contribution, and null return.
- The contribution is preserved rather than reconstructed. With zero active weight,
  its allocation effect is zero and the released selection convention carries its
  active contribution so the effects reconcile.
- Financing with an attributable exposure and return may instead be represented as an
  ordinary identifier using those supplied facts.
- `perfattr` does not infer fee or financing rows from identifier text, calculate the
  charge, or add semantic labels to the stable numerical result schemas.

### Derivative exposure — supported boundary convention

- Require the host adapter to supply the selected exposure basis.
- Do not infer market value, notional, delta-adjusted exposure, or another convention.
- Record exposure-basis provenance without making it an attribution effect.

## 2. Add time-aware classification

### Effective-dated classifications

**Status:** Released in `perfattr==0.3.0a1` and promoted unchanged to stable
`perfattr==0.3.0` on September 4, 2026. The completed implementation record is roadmap
4 and its accepted specification.

- Resolve classification assignments for each source period before consolidation.
- Define overlap, gap, boundary-date, and missing-assignment behavior.
- Permit portfolio and benchmark to use different source identifiers and mappings.
- Reconcile results when an identifier changes classification inside a reporting
  period.

Roadmap 2 establishes the required pipeline order. The accepted governing contract is
in [roadmap 4](perfattr_roadmap_4_effective_dated_classification.md) and
[`effective_dated_classification_specification.md`][effective-spec].
Implementation is authorized only in the dependency order and within the boundaries
of roadmap 4.

[effective-spec]: ../docs/effective_dated_classification_specification.md

### Additive hierarchical result roll-up

**Status:** Promoted into active
[roadmap 10](perfattr_roadmap_10_hierarchical_result_rollup.md) on September 6, 2026.
Its governing
[specification](../docs/hierarchical_result_rollup_specification.md) is accepted. The
roadmap was completed and released in `perfattr==0.9.0a1` that day.

- Roll already calculated leaf-level weights, returns, contributions, and effects into
  parent classifications without recalculating attribution at each hierarchy level.
- Support a classification tree of arbitrary documented depth.
- Define leaf, parent, root, missing-parent, duplicate-parent, and cycle behavior.
- Ensure every additive child value reconciles to its reported parents, and derive
  parent-period returns under an explicitly documented effective-return identity.
- Preserve the five released `AttributionResult` frames and expose hierarchical output
  through a separate, explicitly named result boundary.
- Keep hierarchy metadata separate from numerical identifiers and presentation labels.
- Reuse the released static and effective-dated leaf-classification preparation without
  introducing speculative effective-dated hierarchy behavior in the first version.
- Preserve enough explicit parent-child identity to avoid obstructing a later
  independently calculated hierarchical methodology, but do not add its parameters or
  data structures prematurely.

Methodological context: Bacon (2008), second edition, chapter 5. Roadmap 10 records the
verified edition, comparative review, exact aggregation boundary, and provenance
requirements.

### Hierarchical attribution recalculation — deferred

Retain independently calculated attribution at every hierarchy level as a separate
future feature candidate. It is not part of the additive result-roll-up proposal and
must not be introduced implicitly under the same API or result identity.

- Establish a concrete user requirement before promotion. Additive roll-up already
  answers where leaf-level effects accumulate; recalculation must solve a distinct
  decision-analysis or reporting need.
- Specify whether each level is calculated relative to the portfolio total, its parent
  segment, or both. These are distinct financial policies, not presentation options.
- Define level-specific weight normalization, portfolio and benchmark reference
  returns, missing branches, cross-level effects, and reconciliation identities.
- Calculate from the required prepared weights and returns rather than treating rolled
  child effects as sufficient inputs.
- Decide how single-period level calculations interact with contribution and effect
  linking across time before defining an output schema.
- Keep any future recalculated result distinguishable from additive hierarchical
  roll-up so users cannot mistake one methodology for the other.

This candidate depends on experience with the additive roll-up and remains
noncommitted until its additional value justifies the larger methodology and schema
surface. Eagle's performance documentation distinguishes simple higher-level roll-up
from all-level attribution calculated to the total or to each segment; use that
distinction as comparative product evidence rather than calculation authority.

Comparative product reference:
[Eagle Performance, *Create Brinson and Fachler Options – Multicurrency
Analysis*][eagle-hierarchy].

[eagle-hierarchy]: https://eagledocs.atlassian.net/wiki/spaces/Performance2017/pages/856720063

## 3. Add explicit single-period methodology policies

### Separate interaction effect

**Status:** Promoted together with Brinson-Fachler three-effect attribution into
completed [roadmap 5](perfattr_roadmap_5_brinson_fachler_three_effect.md) and released
in `perfattr==0.4.0a1` on September 5, 2026.

- Preserve the initial policy in which portfolio-weighted selection absorbs
  interaction.
- Add an explicit policy that reports interaction separately.
- Do not silently reinterpret the released selection column.
- Approve a result-schema compatibility plan before adding an interaction column.

### Brinson-Fachler three-effect attribution

**Status:** Promoted together with a separate interaction effect into completed
[roadmap 5](perfattr_roadmap_5_brinson_fachler_three_effect.md) and released in
`perfattr==0.4.0a1` on September 5, 2026.

- Add allocation, selection, and interaction as distinct effects.
- Retain the existing Brinson-Fachler allocation convention as the baseline.
- Make the selected methodology and interaction convention explicit in results and
  reconciliation evidence.

Candidate methodological reference: Brinson and Fachler (1985).

### Brinson-Hood-Beebower three-effect attribution

**Status:** Promoted into completed
[roadmap 6](perfattr_roadmap_6_brinson_hood_beebower_three_effect.md) and released in
`perfattr==0.5.0a1` on September 5, 2026.

- Add the BHB allocation convention with separate selection and interaction.
- Share validated infrastructure with Brinson-Fachler without obscuring the different
  financial formulas.
- Require independent fixtures that make the BF and BHB allocation difference visible.

Candidate methodological reference: Brinson, Hood, and Beebower (1986).

### Brinson-Hood-Beebower two-effect reporting convention

**Status:** Promoted into
[roadmap 7](perfattr_roadmap_7_brinson_hood_beebower_two_effect.md) on September 5,
2026, and released in `perfattr==0.6.0a1` that day.

- Retain the BHB allocation and identifier-level total definitions established by
  roadmap 6.
- Absorb interaction into portfolio-weighted selection so that two-effect selection
  equals BHB three-effect selection plus interaction.
- Reuse the released two-effect result schemas without changing the default
  Brinson-Fachler method.
- Keep the method identity explicit because this is a derived reporting convention,
  not the original three-component BHB presentation.
- Verify that native two-effect output provides enough compatibility or usability
  value to justify another public method rather than requiring callers to combine two
  three-effect columns themselves.

Candidate methodology: `allocation = (wP - wB) * rB`,
`selection = wP * (rP - rB)`, with authoritative-contribution residual behavior to be
specified consistently with roadmap 6.

## 4. Add linking and geometric methods one at a time

The current baseline already includes logarithmic contribution linking and Carino
active-effect linking. Reconcile the term "Cariño log-smoothing" with the implemented
baseline before proposing additional Carino work.

Roadmap 8 is the first promoted proposal and introduces one explicit effect-linking
policy rather than a general plugin framework. Preserve each method's period effects,
full-horizon effects, and reconciliation identities.

Suggested evaluation order:

1. **Frongello recursive linking** — promoted into active
   [roadmap 8](perfattr_roadmap_8_frongello_recursive_linking.md) on September 5,
   2026. Its governing
   [specification](../docs/frongello_recursive_linking_specification.md) was accepted
   that day; the roadmap was completed and released in `perfattr==0.7.0a1` that day.
   Candidate reference: Frongello (2002).
2. **GRAP factor linking — not currently pursued.** Candidate reference: GRAP
   (1997). The Roadmap 8 methodology review found that GRAP's full-horizon factor is
   algebraically equivalent to the unrolled Frongello recursion. The public market
   review below found that GRAP is a recognized method, but did not establish that a
   separately named GRAP policy is a common purchasing or interoperability
   requirement. Do not create a duplicate numerical path merely to expose a second
   label.
3. **Menchero optimized linking** — selected next and promoted into active
   [roadmap 9](perfattr_roadmap_9_menchero_optimized_linking.md) on September 6,
   2026. Its governing
   [specification](../docs/menchero_optimized_linking_specification.md) was accepted
   that day; the roadmap was completed and released in `perfattr==0.8.0a1` that day.
   Candidate references:
   Menchero (2000, 2004).
4. **Geometric excess-return attribution** — implementation complete and prepared as
   the `perfattr==0.10.0a1` release candidate under
   [roadmap 11](perfattr_roadmap_11_geometric_attribution.md) on September 6, 2026.
   Its governing
   [specification](../docs/geometric_attribution_specification.md) was accepted on
   September 7, 2026, and records the design review's central correction: geometric
   attribution changes the single-period formulas, excess-return definition, and
   multiplicative reconciliation identity, so it is not another arithmetic
   `EffectLinkingMethod`. Candidate reference: Bacon (2008), chapter 6.

The order may change after specifications expose complexity or user value. Verify the
exact publications, formulas, licensing, and intellectual-property considerations
before implementation.

### GRAP decision record

As of September 6, 2026, do not promote GRAP into a separate roadmap or public
`EffectLinkingMethod` merely so that `perfattr` can list another supported method.

The decision is based on the following evidence and tradeoff:

- GRAP is an established and recognizable method. For example, AMINDIS and FIDA list
  it among their available multi-period attribution linkers, and the R
  `PortfolioAttribution` package exposes it as a selectable policy.
- Public product material does not provide enough evidence to call GRAP ubiquitous or
  a standard buyer requirement. The CFA Institute's attribution review also notes
  that software providers often keep their linking methods proprietary, so public
  documentation cannot establish reliable market prevalence.
- The same CFA Institute review reports that GRAP, Frongello, and Bonafede compound
  effects through time and produce identical results. Roadmap 8 independently
  confirmed the exact full-horizon equivalence between the GRAP prefix/suffix factor
  and `perfattr`'s unrolled Frongello recursion.
- A second implementation would therefore add testing and maintenance cost without
  adding new numerical capability. Documentation may accurately describe the released
  Frongello policy as mathematically equivalent to GRAP at the complete-horizon
  boundary, but must not imply that a separately selectable GRAP policy exists.

Reconsider a public `GRAP` selector only when a real client, file format, comparison,
or integration requires that method identity. If added, it must reuse the existing
factor calculation rather than introduce a duplicate algorithm, preserve `"GRAP"` in
result metadata, and include tests proving exact numerical equality with Frongello.

Market-review sources:

- [CFA Institute Research Foundation, *Performance Attribution* (2019)][cfa-grap]
- [AMINDIS, *Brinson Performance Attribution*][amindis-grap]
- [FIDA, *Stats & Quant*][fida-grap]
- [R-Finance `PortfolioAttribution` documentation][r-grap]

[cfa-grap]: https://rpc.cfainstitute.org/research/foundation/2019/performance-attribution
[amindis-grap]: https://www.amindis.com/brinson-performance-attribution
[fida-grap]: https://fidaonline.com/en/rd/stats-quant.html
[r-grap]: https://rdrr.io/github/R-Finance/PortfolioAttribution/man/Attribution.html

## 5. External-flow reconciliation — not currently pursued

As of September 6, 2026, do not promote external-flow reconciliation into a separate
roadmap or add flow fields to the portable input and result schemas.

The decision is based on the following scope and auditability considerations:

- External flows belong primarily to return measurement and portfolio accounting,
  not to the subsequent decomposition of an already measured return into attribution
  effects. A host accounting layer must apply its chosen time-weighted, Modified
  Dietz, or other flow-adjusted return policy before calling `perfattr`.
- `perfattr` receives period weights, returns, and optional authoritative
  contributions. Once those values are supplied, an external-flow amount does not
  change the Brinson calculations and must not be classified as allocation,
  selection, interaction, or a residual attribution effect.
- A flow amount by itself cannot independently reconcile a reported return. A
  defensible check would also require valuation observations, exact flow timing, sign
  conventions, the return-measurement method, and policies for transactions, fees,
  taxes, and financing. Adding only a nominal flow column would create the appearance
  of assurance without enough evidence to provide it.
- Adding that broader accounting contract would burden ordinary weights-and-returns
  users, expand stable schemas, and duplicate responsibilities intentionally left in
  host systems such as `ppar`.
- Treating an unexplained flow as a contribution or balancing residual would risk
  double counting and could conceal an upstream accounting or timing error.

Hosts may reconcile valuations, flows, and measured returns before constructing
portable attribution inputs. Reconsider an optional `perfattr` reconciliation input
only when a concrete audit workflow supplies the complete evidence and conventions
needed for an independent check. Any future result must remain diagnostic evidence,
not an attribution effect, and must not alter the ordinary weights-and-returns path.

## 6. Add currency attribution as a separate calculation family

- Specify required local, currency, and base-currency returns before adding columns.
- Define portfolio and benchmark currency exposures, hedging conventions, and
  reconciliation identities explicitly.
- Keep currency attribution separate from the existing domestic Brinson result schema.
- Reuse general validation or linking helpers only where the financial meaning remains
  identical.

Candidate methodology: Karnosky-Singer four-effect additive currency attribution.
Candidate reference: Karnosky and Singer (1994). Verify the primary methodology and
input requirements during specification.

## Deliberately deferred architecture

This backlog does not justify a plugin system, universal attribution engine, generic
method graph, or speculative columns. Calculation policies, schema variants, and shared
abstractions should emerge only from approved, independently tested implementations.
