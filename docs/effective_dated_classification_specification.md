# perfattr Effective-Dated Classification Specification

## Status

**Status:** Accepted September 4, 2026.

**Implementation:** Complete and released in `perfattr==0.3.0a1` on September 4, 2026.
Mapping normalization, source-period assignment, end-to-end preparation composition,
reconciliation verification, canonical CSV support, cross-version performance
verification, and the approved narrow `ppar` generic adapter exposure all satisfy
roadmap 4.

The user approved this specification and roadmap 4 on September 4, 2026. This document
supplements `docs/preparation_specification.md`; unchanged preparation and calculation
contracts continue to govern. Implementation follows the ordered roadmap 4 gates.

The words **must**, **must not**, **should**, and **may** have their ordinary technical
meanings.

## User problem

A source identifier can belong to different classifications at different times. The
released static mapping assigns one classification to an identifier for all source
periods, so it cannot accurately prepare a history containing a legitimate
classification change.

The preparation layer already resolves classification before reporting-frequency
consolidation. Effective-dated mapping should extend that stage without changing the
attribution formulas, prepared result schemas, or host responsibilities.

## Design principles

- Preserve the existing static mapping contract exactly.
- Resolve each retained source-period row to at most one classification.
- Reject a classification change inside a source period rather than inventing a split.
- Preserve the existing mapping, consolidation, and reconciliation mathematics.
- Keep effective-dated display names, vendor extraction, and accounting policy outside
  the numerical preparation layer.
- Add no runtime dependency beyond pandas, NumPy, and the Python standard library.

## Scope

This feature adds:

- a canonical effective-dated mapping DataFrame and CSV form;
- validation of dates, identities, duplicates, conflicts, overlaps, and relevant gaps;
- independent effective-dated assignment for portfolio and benchmark source rows;
- mapping and roll-up at source-period granularity before consolidation; and
- focused reconciliation, compatibility, and performance verification.

This feature does not add:

- automatic classification extraction from a vendor or security master;
- security-identity construction;
- open-ended mapping intervals;
- transaction-time or “as known on” history;
- automatic splitting or prorating of source-period financial values;
- effective-dated classification names or hierarchy metadata;
- multi-level classification roll-up; or
- a new attribution method or result column.

The caller or host adapter remains responsible for selecting the desired mapping
snapshot and converting source-specific effective dates to this contract.

## Public API

The signatures of `prepare_attribution`, `normalize_mapping`, and `read_mapping_csv`
remain unchanged. The existing `portfolio_mapping` and `benchmark_mapping` arguments
accept either one static mapping or one effective-dated mapping. A single mapping must
use exactly one of the two schemas; static and effective-dated rows cannot be mixed in
one frame.

No new public class, policy enum, or mapping-specific preparation entry point is added.

## Mapping schemas

### Static mapping

The released static schema remains:

```text
identifier
classification_identifier
```

Its validation, identity fallback, normalization, and roll-up behavior remain
unchanged.

### Effective-dated mapping

An effective-dated mapping DataFrame contains exactly these columns:

```text
from_date
thru_date
identifier
classification_identifier
```

Each row says that `identifier` maps to `classification_identifier` throughout the
inclusive interval from `from_date` through `thru_date`.

Normalization must:

- apply the preparation specification's date normalization rules;
- require both dates to be present and require `from_date <= thru_date`;
- apply the existing identity normalization rules to both identifier columns;
- reject duplicate column labels and missing or additional columns;
- collapse exact duplicate normalized rows;
- reject every overlap between intervals for the same source identifier, even when
  the overlapping rows name the same classification; and
- return independently owned rows ordered by source identifier, `from_date`,
  `thru_date`, and classification identifier.

Two intervals are adjacent, not overlapping, when the later `from_date` is the
calendar day immediately after the earlier `thru_date`. Mapping intervals need not be
globally continuous because a source may have no performance during a gap.

Open-ended intervals are deliberately deferred. A caller can continue using a static
mapping for a permanent assignment or provide explicit effective dates covering the
requested history.

## Assignment contract

Effective-dated assignment operates independently on portfolio and benchmark after
normalization and public date-window filtering, and before reporting-frequency
consolidation.

For a retained performance row `p` and a mapping row `m` with the same source
identifier, `m` covers `p` only when:

```text
m.from_date <= p.from_date
and
p.thru_date <= m.thru_date
```

The following rules apply:

1. If the performance identifier never appears in the effective-dated mapping, it
   maps to itself. This preserves the released partial-mapping behavior.
2. If the identifier appears in the mapping, every retained source period for that
   identifier must be fully covered by exactly one interval.
3. No matching interval is a mapping-gap error.
4. More than one matching interval is an overlap error, although normalization should
   normally detect the overlap before assignment.
5. One or more intervals that cover only part of a source period produce a
   source-period-boundary error. Preparation must not select an endpoint convention,
   split the row, prorate its weight or contribution, or compound a partial return.
6. Mapping rows for identifiers absent from performance are still normalized and
   validated, consistent with the released static contract.

A host with a classification change inside a source period must obtain more granular
performance rows or make an explicit source-specific accounting decision before
calling `perfattr`.

## Roll-up and consolidation

After assignment, the existing static mapping roll-up applies without modification in
financial meaning. For each side, source period, and resolved classification:

```text
mapped_weight       = sum(constituent weights)
mapped_contribution = sum(constituent contributions)

mapped_return = mapped_contribution / mapped_weight
                when mapped_weight != 0
mapped_return = 0
                when mapped_weight == 0 and mapped_contribution == 0
mapped_return = null
                when mapped_weight == 0 and mapped_contribution != 0
```

If an identifier changes classification between source periods inside one reporting
period, each source period is first assigned to its applicable classification. The
existing consolidation stage then independently consolidates every resulting
classification. Both the old and new classifications may therefore appear in the
reporting-period output.

The implementation must not compound intermediate mapped effective returns. It must
continue deriving the reporting-period mapped return from the final consolidated
weight and linked contribution.

## Reconciliation

Effective-dated mapping must use the existing preparation reconciliation schema and
check names. It adds no reconciliation columns or new result frame.

For each retained source period and side, mapping must preserve:

```text
sum(mapped weights)       == sum(source weights)
sum(mapped contributions) == sum(source contributions)
```

Both identities use the caller's existing reconciliation tolerance. Assignment gaps,
overlaps, and boundary cuts are structural errors and are not tolerance-based.

All existing reporting-period weight, linked-contribution, prepared-output, and
calculation-core reconciliations remain required.

## Canonical CSV

The existing headerless two-column mapping CSV remains valid. `read_mapping_csv`
additionally accepts a headerless four-column effective-dated mapping in this order:

```text
from_date,thru_date,identifier,classification_identifier
```

Every nonblank record in one file must have the same supported width. A width other
than two or four, mixed widths, a header row, or an invalid value is an error. The
reader returns the normalized schema corresponding to the file width.

File and URL discovery remain outside `perfattr`; the reader accepts only an existing
local canonical CSV path under the established I/O contract.

## Compatibility and schema stability

- Existing two-column DataFrames and CSV files retain their exact behavior.
- `prepare_attribution` receives no new argument.
- Prepared portfolio, benchmark, and reconciliation column schemas do not change.
- Calculation-core inputs, outputs, formulas, null rules, and ordering do not change.
- Effective-dated mapping is an additive public-input capability suitable for a minor
  prerelease version increment.
- Deterministic ordering and non-mutation requirements apply to both mapping forms.

The normalized output of `normalize_mapping` and `read_mapping_csv` has either the
canonical two-column static schema or canonical four-column effective-dated schema,
according to the input form.

## Error behavior

Errors must identify the mapping boundary and include a small deterministic sample of
the affected source identifiers and dates. They must not dump an entire input frame.

At minimum, focused errors distinguish:

- unsupported or mixed schemas;
- invalid or missing dates;
- reversed intervals;
- invalid identities;
- exact duplicates, which are harmless and collapse;
- overlapping intervals;
- a relevant gap for an identifier that has dated mappings; and
- a classification boundary inside a source period.

## Verification requirements

Implementation must add tests for:

- static mapping regression parity, including identity fallback;
- normalization, ownership, dtypes, and deterministic ordering;
- exact duplicates and adjacent inclusive intervals;
- overlapping intervals with equal and different target classifications;
- gaps before, between, and after dated assignments;
- a source period exactly equal to, strictly inside, and spanning an assignment;
- a classification boundary that falls inside a source period;
- one identifier changing classification between source periods inside one reporting
  period;
- mapping collisions involving both changing and unchanged identifiers;
- independent portfolio and benchmark effective histories;
- returns-only and authoritative-contribution inputs;
- zero-weight, nonzero-contribution rows and null effective returns;
- unused but invalid mapping rows;
- two-column and four-column canonical CSV files plus invalid widths; and
- all established reconciliation, non-mutation, typing, lint, build, and import gates.

The classification-change fixture must be calculated independently by hand. Its test
docstring and comments must show the source-period assignments, mapped weight and
contribution sums, linking coefficients when consolidation is nontrivial, final
effective returns, and conservation identities. Expected values must not be generated
from `ppar` or the production implementation.

After a correct prototype exists, measure elapsed time and peak memory on realistic
selected-input histories with static and effective-dated mappings. Establish a new
performance threshold only from repeatable evidence and with explicit approval.

Run the 500x `ppar` release-candidate workflow only if the host adapter or another
cross-cutting integration boundary changes.

## Comparative design review and provenance

`pybrinson` was reviewed as requested by roadmap 3. Its public boundary starts from
already prepared period segments and keeps attribution formulas and hierarchy
invariants explicit. It does not provide the effective-dated preparation contract
needed here. This specification adopts only the general lesson of keeping preparation
separate from attribution mathematics; it copies no source, fixture, or formula.

- Repository: <https://github.com/gghez/pybrinson/>
- Reviewed implementation plan:
  <https://github.com/gghez/pybrinson/blob/main/docs/implementation-v1.md>

Effective-dated assignment is a temporal data contract, not a new financial
methodology. The existing mapping and consolidation formulas remain governed by the
accepted preparation specification. Any future methodology change still requires its
own primary-source review.

## Approved decisions

The user approved:

- the exact four-column schema;
- required, inclusive, closed intervals;
- identity fallback only for identifiers absent from the dated mapping;
- errors for relevant gaps and source-period boundary cuts;
- unchanged output and reconciliation schemas; and
- the implementation sequence and gates in roadmap 4.
