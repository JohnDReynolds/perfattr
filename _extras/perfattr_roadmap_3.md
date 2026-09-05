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

### Multi-level hierarchical roll-up

- Support a classification tree of arbitrary documented depth.
- Define leaf, parent, root, missing-parent, and cycle behavior.
- Ensure child effects reconcile exactly to every reported parent.
- Keep hierarchy metadata separate from numerical identifiers and presentation labels.

Candidate methodological reference: Bacon (2008), chapter 5. Verify the exact edition
and applicable formulas during specification.

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

**Status:** Selected as the next feature to address after roadmap 6 is complete. It
remains a noncommitted candidate and requires its own approved roadmap and governing
specification before implementation.

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

## 4. Add linking methods one at a time

The current baseline already includes logarithmic contribution linking and Carino
active-effect linking. Reconcile the term "Cariño log-smoothing" with the implemented
baseline before proposing additional Carino work.

When the first additional method is promoted, introduce one explicit linking-method
policy rather than a general plugin framework. Preserve each method's period effects,
full-horizon effects, and reconciliation identities.

Suggested evaluation order:

1. **Frongello recursive linking** — candidate reference: Frongello (2002).
2. **GRAP factor linking** — candidate reference: GRAP (1997).
3. **Geometric linking** — candidate reference: Bacon (2008), chapter 6.
4. **Menchero optimized linking** — candidate references: Menchero (2000, 2004).

The order may change after the specifications expose complexity or user value. Verify
the exact publications, formulas, and intellectual-property status—particularly for
Menchero—before implementation.

## 5. Add external-flow reconciliation evidence

- Keep flow-adjusted return measurement in the host accounting layer.
- Define an optional reconciliation input that discloses external-flow components.
- Do not silently classify flows as allocation, selection, interaction, or residual
  attribution effects.
- Add this only when the evidence improves an actual audit workflow without burdening
  ordinary weights-and-returns users.

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
